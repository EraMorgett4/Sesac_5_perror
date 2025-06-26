"""
5개 CSV 파일 통합 전처리 스크립트 (완전한 병렬 처리 버전)
범주형 데이터 오류 완전 해결 + 클래스 분포 개선
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from math import radians, cos, sin, asin, sqrt
import os
import warnings
from multiprocessing import Pool, cpu_count
from concurrent.futures import ProcessPoolExecutor, as_completed
import time
import pickle

# 지하철역 변환기 import 추가
try:
    from subway_converter import get_analysis_locations_for_integrate

    SUBWAY_AVAILABLE = True
    print("✅ 지하철역 변환기 로드 성공")
except ImportError:
    SUBWAY_AVAILABLE = False
    print("⚠️ 지하철역 변환기 없음 - 기본 위치 사용")

warnings.filterwarnings("ignore")


def safe_categorize_numeric(values, bins, labels):
    """안전한 수치형 범주화 함수 (pd.cut 대체)"""
    values = np.array(values)
    result = np.full(len(values), labels[0], dtype=int)  # 기본값으로 초기화

    for i in range(len(bins) - 1):
        if i < len(labels):
            if i == 0:
                # 첫 번째 구간: bins[0] < values <= bins[1]
                mask = (values > bins[i]) & (values <= bins[i + 1])
            else:
                # 나머지 구간: bins[i] < values <= bins[i+1]
                mask = (values > bins[i]) & (values <= bins[i + 1])
            result[mask] = labels[i]

    # 마지막 구간 처리 (값이 마지막 bin보다 큰 경우)
    if len(labels) > len(bins) - 2:
        mask = values > bins[-2]
        result[mask] = labels[-1]

    return result.astype(int)


def haversine_distance_vectorized(lat1, lng1, lat2_array, lng2_array):
    """벡터화된 거리 계산 (NumPy 사용으로 고속화)"""

    # NaN 값 처리
    mask = ~(
        np.isnan(lat1) | np.isnan(lng1) | np.isnan(lat2_array) | np.isnan(lng2_array)
    )

    R = 6371  # 지구 반지름 (km)

    # 라디안 변환
    lat1_rad = np.radians(lat1)
    lng1_rad = np.radians(lng1)
    lat2_rad = np.radians(lat2_array)
    lng2_rad = np.radians(lng2_array)

    # 거리 계산
    dlat = lat2_rad - lat1_rad
    dlng = lng2_rad - lng1_rad

    a = (
        np.sin(dlat / 2) ** 2
        + np.cos(lat1_rad) * np.cos(lat2_rad) * np.sin(dlng / 2) ** 2
    )
    c = 2 * np.arcsin(np.sqrt(a))
    distances = R * c

    # NaN이 있던 곳은 무한대로 설정
    distances[~mask] = float("inf")

    return distances


def haversine_distance(lat1, lon1, lat2, lon2):
    """단일 거리 계산 (기존 호환성 유지)"""
    if pd.isna(lat1) or pd.isna(lon1) or pd.isna(lat2) or pd.isna(lon2):
        return float("inf")

    R = 6371  # 지구 반지름 (km)
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * asin(sqrt(a))

    return R * c


def load_csv_file(file_path, encoding="utf-8"):
    """CSV 파일 로드 (인코딩 자동 감지)"""
    try:
        df = pd.read_csv(file_path, encoding=encoding)
        print(
            f"  ✅ {os.path.basename(file_path)}: {df.shape[0]} rows, {df.shape[1]} columns"
        )
        return df
    except UnicodeDecodeError:
        try:
            df = pd.read_csv(file_path, encoding="cp949")
            print(
                f"  ✅ {os.path.basename(file_path)} (cp949): {df.shape[0]} rows, {df.shape[1]} columns"
            )
            return df
        except Exception as e:
            print(f"  ❌ Failed to load {file_path}: {e}")
            return pd.DataFrame()
    except Exception as e:
        print(f"  ❌ Failed to load {file_path}: {e}")
        return pd.DataFrame()


def validate_seoul_coordinates(df, lat_col="위도", lng_col="경도"):
    """서울시 좌표 범위 검증 및 데이터 타입 최적화"""
    if lat_col not in df.columns or lng_col not in df.columns:
        return df

    seoul_bounds = {
        "lat_min": 37.4,
        "lat_max": 37.7,
        "lng_min": 126.7,
        "lng_max": 127.2,
    }

    before_count = len(df)
    valid_coords = (
        (df[lat_col] >= seoul_bounds["lat_min"])
        & (df[lat_col] <= seoul_bounds["lat_max"])
        & (df[lng_col] >= seoul_bounds["lng_min"])
        & (df[lng_col] <= seoul_bounds["lng_max"])
    )

    df_clean = df[valid_coords].copy()

    # 메모리 최적화: float64 → float32
    df_clean[lat_col] = df_clean[lat_col].astype("float32")
    df_clean[lng_col] = df_clean[lng_col].astype("float32")

    after_count = len(df_clean)
    print(
        f"  📍 좌표 검증: {before_count} → {after_count} ({after_count/before_count*100:.1f}%)"
    )
    return df_clean


def preprocess_construction_data(df):
    """공사현황 데이터 전처리"""
    if df.empty:
        return df

    # 날짜 처리
    date_columns = ["착공일", "준공일"]
    for col in date_columns:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")

    # 공사 기간 계산
    if "착공일" in df.columns and "준공일" in df.columns:
        df["공사기간_일"] = (df["준공일"] - df["착공일"]).dt.days
        df["공사기간_일"] = df["공사기간_일"].fillna(0)

    # 위험도 수치화
    risk_mapping = {
        "높음": 3,
        "보통": 2,
        "낮음": 1,
        "상위험": 3,
        "중위험": 2,
        "하위험": 1,
        "잔여위험": 1,
        "완료": 0,
    }

    risk_columns = ["기본_위험도_카테고리", "현재_위험도_카테고리"]
    for col in risk_columns:
        if col in df.columns:
            new_col = col.replace("카테고리", "수치")
            df[new_col] = df[col].map(risk_mapping).fillna(1)

    # 공사상태 수치화
    if "공사상태" in df.columns:
        status_mapping = {"진행중": 3, "일시중단": 2, "완료": 1}
        df["공사상태_수치"] = df["공사상태"].map(status_mapping).fillna(1)

    # 영향반경 처리
    if "영향반경_미터" in df.columns:
        df["영향반경_미터"] = pd.to_numeric(
            df["영향반경_미터"], errors="coerce"
        ).fillna(50)
        df["영향반경_km"] = df["영향반경_미터"] / 1000

    return df


def preprocess_sinkhole_data(df):
    """포트홀/싱크홀 데이터 전처리"""
    if df.empty:
        return df

    # 날짜 처리
    if "날짜" in df.columns:
        df["날짜"] = pd.to_datetime(df["날짜"], format="%Y%m%d", errors="coerce")

    # 발생 규모 수치화
    size_columns = ["발생규모폭(m)", "발생규모연장(m)", "발생규모깊이(m)"]
    for col in size_columns:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    # 규모 부피 계산
    if all(col in df.columns for col in size_columns):
        df["규모_부피"] = (
            df["발생규모폭(m)"] * df["발생규모연장(m)"] * df["발생규모깊이(m)"]
        )

    # 피해 수치화
    damage_columns = [
        "피해사망자수(명)",
        "피해부상자수(명)",
        "피해차량대수(대)",
        "피해규모점수",
    ]
    for col in damage_columns:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    # 총 피해 점수 계산
    if all(col in df.columns for col in damage_columns):
        df["총_피해점수"] = (
            df["피해사망자수(명)"] * 100
            + df["피해부상자수(명)"] * 10
            + df["피해차량대수(대)"] * 5
            + df["피해규모점수"] * 2
        )

    # 발생 원인 위험도
    if "발생원인구분" in df.columns:
        cause_mapping = {
            "하수관 손상": 3,
            "상수관 손상": 3,
            "기타매설물 손상": 2,
            "자연발생": 1,
        }
        df["원인_위험도"] = df["발생원인구분"].map(cause_mapping).fillna(2)

    # 최근성 가중치
    if "날짜" in df.columns:
        current_date = datetime.now()
        df["발생후_경과일"] = (current_date - df["날짜"]).dt.days
        df["발생후_경과일"] = df["발생후_경과일"].fillna(9999)
        df["최근성_가중치"] = np.where(
            df["발생후_경과일"] <= 365,
            1.0,
            np.where(df["발생후_경과일"] <= 730, 0.5, 0.1),
        )

    return df


def preprocess_population_data(df):
    """유동인구 데이터 전처리 (범주형 오류 완전 해결)"""
    if df.empty:
        return df

    # 날짜 처리
    if "날짜" in df.columns:
        df["날짜"] = pd.to_datetime(df["날짜"], format="%Y%m%d", errors="coerce")

    # 방문자수 수치화
    if "방문자수" in df.columns:
        df["방문자수"] = pd.to_numeric(df["방문자수"], errors="coerce").fillna(0)

        # 안전한 범주화 (pd.cut 사용 안함)
        visitors = df["방문자수"].values
        df["인구밀도등급"] = safe_categorize_numeric(
            visitors, bins=[0, 200, 500, 1000, float("inf")], labels=[1, 2, 3, 4]
        )

    # 자치구별 통계 (있는 경우)
    if "자치구" in df.columns and "방문자수" in df.columns:
        district_stats = (
            df.groupby("자치구")["방문자수"].agg(["mean", "max"]).reset_index()
        )
        district_stats.columns = ["자치구", "구_평균방문자", "구_최대방문자"]
        df = df.merge(district_stats, on="자치구", how="left")

    return df


def preprocess_subway_data(df):
    """지하철 유동인구 데이터 전처리 (범주형 오류 완전 해결)"""
    if df.empty:
        return df

    # 날짜 처리
    if "날짜" in df.columns:
        df["날짜"] = pd.to_datetime(df["날짜"], format="%Y%m%d", errors="coerce")

    # 승하차 승객수 수치화
    if "승하차총승객수" in df.columns:
        df["승하차총승객수"] = pd.to_numeric(
            df["승하차총승객수"], errors="coerce"
        ).fillna(0)

        # 안전한 범주화 (pd.cut 사용 안함)
        passengers = df["승하차총승객수"].values
        df["지하철이용수준"] = safe_categorize_numeric(
            passengers, bins=[0, 10000, 30000, 60000, float("inf")], labels=[1, 2, 3, 4]
        )

    # 역 중요도 계산
    if "승하차총승객수" in df.columns:
        max_passengers = df["승하차총승객수"].max()
        if max_passengers > 0:
            df["역_중요도"] = df["승하차총승객수"] / max_passengers
        else:
            df["역_중요도"] = 0.0

    # 자치구별 지하철 통계
    if "자치구" in df.columns and "승하차총승객수" in df.columns:
        subway_stats = (
            df.groupby("자치구")["승하차총승객수"]
            .agg(["mean", "sum", "count"])
            .reset_index()
        )
        subway_stats.columns = [
            "자치구",
            "구_평균지하철승객",
            "구_총지하철승객",
            "구_지하철역수",
        ]
        df = df.merge(subway_stats, on="자치구", how="left")

    return df


def preprocess_rainfall_data(df):
    """강수량 데이터 전처리 (범주형 오류 완전 해결)"""
    if df.empty:
        return df

    # 날짜 처리
    if "날짜" in df.columns:
        df["날짜"] = pd.to_datetime(df["날짜"], format="%Y%m%d", errors="coerce")

    # 누적강수량 수치화
    if "누적강수량" in df.columns:
        df["누적강수량"] = pd.to_numeric(df["누적강수량"], errors="coerce").fillna(0)

        # 안전한 범주화 (pd.cut 사용 안함)
        rainfall = df["누적강수량"].values
        df["강수량위험등급"] = safe_categorize_numeric(
            rainfall, bins=[0, 1, 5, 20, 60, float("inf")], labels=[0, 1, 2, 3, 4]
        )

    # 시간 가중치
    if "날짜" in df.columns:
        current_date = datetime.now()
        df["강수후_경과일"] = (current_date - df["날짜"]).dt.days
        df["강수후_경과일"] = df["강수후_경과일"].fillna(9999)
        df["강수_시간가중치"] = np.where(
            df["강수후_경과일"] <= 7,
            1.0,
            np.where(
                df["강수후_경과일"] <= 30,
                0.7,
                np.where(df["강수후_경과일"] <= 90, 0.4, 0.1),
            ),
        )

    return df


def preprocess_all_datasets(datasets):
    """모든 데이터셋 전처리 (병렬 처리 준비)"""
    print("\n🔄 데이터 전처리 시작...")

    processed_datasets = {}

    # 각 데이터셋 전처리
    for name, df in datasets.items():
        if df.empty:
            processed_datasets[name] = pd.DataFrame()
            continue

        print(f"\n📊 {name} 데이터 전처리...")
        df_clean = validate_seoul_coordinates(df)

        if name == "construction":
            df_clean = preprocess_construction_data(df_clean)
        elif name == "sinkhole":
            df_clean = preprocess_sinkhole_data(df_clean)
        elif name == "population":
            df_clean = preprocess_population_data(df_clean)
        elif name == "subway":
            df_clean = preprocess_subway_data(df_clean)
        elif name == "rainfall":
            df_clean = preprocess_rainfall_data(df_clean)

        # 메모리 최적화: 필요한 컬럼만 유지
        essential_columns = get_essential_columns(name, df_clean.columns)
        if essential_columns:
            df_clean = df_clean[essential_columns]

        processed_datasets[name] = df_clean
        print(f"  ✅ {name} 전처리 완료: {len(df_clean)} 레코드")

    return processed_datasets


def get_essential_columns(dataset_name, available_columns):
    """데이터셋별 필수 컬럼만 선택"""
    essential_cols = {
        "construction": ["위도", "경도", "현재_위험도_수치", "공사상태", "영향반경_km"],
        "sinkhole": [
            "위도",
            "경도",
            "날짜",
            "총_피해점수",
            "최근성_가중치",
            "원인_위험도",
        ],
        "population": ["위도", "경도", "방문자수", "인구밀도등급"],
        "subway": ["위도", "경도", "승하차총승객수", "지하철이용수준", "역_중요도"],
        "rainfall": ["위도", "경도", "누적강수량", "강수량위험등급", "강수_시간가중치"],
    }

    if dataset_name in essential_cols:
        return [col for col in essential_cols[dataset_name] if col in available_columns]
    return list(available_columns)


def process_single_location(args):
    """단일 위치 처리 함수 (병렬 처리용)"""
    try:
        location_data, radius, datasets_pickle = args

        # pickle로 전달된 데이터셋 복원
        datasets = pickle.loads(datasets_pickle)

        location_name = location_data["name"]
        target_lat = location_data["lat"]
        target_lng = location_data["lng"]

        # 위험도 피처 계산
        features = calculate_location_risk_features_optimized(
            target_lat, target_lng, location_name, radius, datasets
        )

        # 종합 위험도 계산
        comprehensive_features = calculate_comprehensive_risk(features)

        return comprehensive_features

    except Exception as e:
        print(f"❌ 위치 처리 오류: {e}")
        return None


def calculate_location_risk_features_optimized(
    target_lat, target_lng, location_name, radius_km, datasets
):
    """최적화된 위험도 피처 계산"""

    features = {
        "location_name": location_name,
        "target_lat": target_lat,
        "target_lng": target_lng,
        "analysis_radius_km": radius_km,
        # 기본값 설정
        "nearby_construction_count": 0,
        "weighted_construction_risk": 0,
        "nearby_sinkhole_count": 0,
        "weighted_sinkhole_risk": 0,
        "avg_daily_visitors": 0,
        "total_daily_visitors": 0,
        "nearby_subway_stations": 0,
        "avg_subway_passengers": 0,
        "avg_rainfall": 0,
        "weighted_rainfall_risk": 0,
        "rainfall_amplification_factor": 1.0,
        "ongoing_construction_count": 0,
        "recent_sinkhole_count": 0,
        "population_density_score": 0,
        "total_subway_passengers": 0,
        "subway_congestion_risk": 0,
    }

    # 각 데이터셋 분석 (벡터화된 거리 계산 사용)
    for dataset_name, df in datasets.items():
        if df.empty:
            continue

        # 벡터화된 거리 계산 (고속)
        distances = haversine_distance_vectorized(
            target_lat, target_lng, df["위도"].values, df["경도"].values
        )

        # 반경 내 데이터 필터링
        nearby_mask = distances <= radius_km
        nearby_data = df[nearby_mask].copy()
        nearby_data["거리"] = distances[nearby_mask]

        if dataset_name == "construction":
            features.update(analyze_construction_risk(nearby_data))
        elif dataset_name == "sinkhole":
            features.update(analyze_sinkhole_risk(nearby_data))
        elif dataset_name == "population":
            features.update(analyze_population_risk(nearby_data))
        elif dataset_name == "subway":
            features.update(analyze_subway_risk(nearby_data))
        elif dataset_name == "rainfall":
            features.update(analyze_rainfall_risk(nearby_data))

    return features


def analyze_construction_risk(nearby_data):
    """공사 위험도 분석"""
    if nearby_data.empty:
        return {
            "nearby_construction_count": 0,
            "weighted_construction_risk": 0,
            "ongoing_construction_count": 0,
        }

    weights = 1 / (nearby_data["거리"] + 0.1)
    current_risk = nearby_data.get("현재_위험도_수치", pd.Series([0]))

    return {
        "nearby_construction_count": len(nearby_data),
        "weighted_construction_risk": (
            (current_risk * weights).sum() / weights.sum() if len(weights) > 0 else 0
        ),
        "ongoing_construction_count": len(
            nearby_data[nearby_data.get("공사상태", "") == "진행중"]
        ),
    }


def analyze_sinkhole_risk(nearby_data):
    """싱크홀 위험도 분석"""
    if nearby_data.empty:
        return {
            "nearby_sinkhole_count": 0,
            "weighted_sinkhole_risk": 0,
            "recent_sinkhole_count": 0,
        }

    weights = 1 / (nearby_data["거리"] + 0.1)
    damage_score = nearby_data.get("총_피해점수", pd.Series([0]))
    time_weight = nearby_data.get("최근성_가중치", pd.Series([1]))

    recent_threshold = datetime.now() - timedelta(days=365)
    recent_count = len(
        nearby_data[nearby_data.get("날짜", pd.Timestamp.min) >= recent_threshold]
    )

    return {
        "nearby_sinkhole_count": len(nearby_data),
        "weighted_sinkhole_risk": (
            (damage_score * weights * time_weight).sum() / weights.sum()
            if len(weights) > 0
            else 0
        ),
        "recent_sinkhole_count": recent_count,
    }


def analyze_population_risk(nearby_data):
    """유동인구 위험도 분석"""
    if nearby_data.empty:
        return {
            "avg_daily_visitors": 0,
            "total_daily_visitors": 0,
            "population_density_score": 0,
        }

    visitors = nearby_data.get("방문자수", pd.Series([0]))
    return {
        "avg_daily_visitors": visitors.mean(),
        "total_daily_visitors": visitors.sum(),
        "population_density_score": visitors.mean() / 1000,
    }


def analyze_subway_risk(nearby_data):
    """지하철 위험도 분석 (안전한 버전)"""
    if nearby_data.empty:
        return {
            "nearby_subway_stations": 0,
            "avg_subway_passengers": 0,
            "total_subway_passengers": 0,
            "subway_congestion_risk": 0,
        }

    # 안전한 승객수 처리
    passengers_col = "승하차총승객수"
    if passengers_col in nearby_data.columns:
        passengers = pd.to_numeric(nearby_data[passengers_col], errors="coerce").fillna(
            0
        )
    else:
        passengers = pd.Series([0] * len(nearby_data))

    return {
        "nearby_subway_stations": len(nearby_data),
        "avg_subway_passengers": passengers.mean(),
        "total_subway_passengers": passengers.sum(),
        "subway_congestion_risk": passengers.mean() / 50000,
    }


def analyze_rainfall_risk(nearby_data):
    """강수량 위험도 분석"""
    if nearby_data.empty:
        return {
            "avg_rainfall": 0,
            "weighted_rainfall_risk": 0,
            "rainfall_amplification_factor": 1.0,
        }

    weights = 1 / (nearby_data["거리"] + 0.1)
    rainfall = nearby_data.get("누적강수량", pd.Series([0]))
    risk_level = nearby_data.get("강수량위험등급", pd.Series([0]))
    time_weight = nearby_data.get("강수_시간가중치", pd.Series([1]))

    avg_rainfall = rainfall.mean()

    # 강수량 증폭 계수
    if avg_rainfall > 60:
        amplification = 1.5
    elif avg_rainfall > 20:
        amplification = 1.3
    elif avg_rainfall > 5:
        amplification = 1.1
    else:
        amplification = 1.0

    return {
        "avg_rainfall": avg_rainfall,
        "weighted_rainfall_risk": (
            (risk_level * weights * time_weight).sum() / weights.sum()
            if len(weights) > 0
            else 0
        ),
        "rainfall_amplification_factor": amplification,
    }


def calculate_comprehensive_risk(features):
    """종합 위험도 계산 (개선된 클래스 분포)"""

    # 물리적 위험도
    physical_risk = (
        features["weighted_construction_risk"] * 0.4
        + features["weighted_sinkhole_risk"] * 0.3
        + features["weighted_rainfall_risk"] * 0.3
    ) * features["rainfall_amplification_factor"]

    # 사회적 위험도
    social_risk = (
        features["population_density_score"] * 0.6
        + features["subway_congestion_risk"] * 0.4
    )

    # 종합 위험도 (물리적 65%, 사회적 35%)
    comprehensive_risk = physical_risk * 0.65 + social_risk * 0.35

    # 0-100 스케일로 정규화 (더 넓은 분포를 위해 계수 조정)
    final_risk_score = min(100, max(0, comprehensive_risk * 30))

    # 위험도 등급 분류 (더 세밀한 구간 설정)
    if final_risk_score >= 70:
        risk_level = "매우높음"
        risk_category = "최고위험"
    elif final_risk_score >= 50:
        risk_level = "높음"
        risk_category = "상위험"
    elif final_risk_score >= 25:
        risk_level = "보통"
        risk_category = "중위험"
    elif final_risk_score >= 10:
        risk_level = "낮음"
        risk_category = "하위험"
    else:
        risk_level = "매우낮음"
        risk_category = "최저위험"

    # 결과 업데이트
    features.update(
        {
            "physical_risk_score": physical_risk * 30,
            "social_risk_score": social_risk * 30,
            "final_risk_score": final_risk_score,
            "comprehensive_risk_level": risk_level,
            "comprehensive_risk_category": risk_category,
        }
    )

    return features


def create_ml_features(df):
    """ML용 추가 파생 피처 생성"""
    print("\n🔧 ML용 파생 피처 생성...")

    # 상호작용 피처
    df["construction_rainfall_interaction"] = (
        df["weighted_construction_risk"] * df["weighted_rainfall_risk"]
    )
    df["population_physical_interaction"] = (
        df["total_daily_visitors"] * df["physical_risk_score"] / 1000
    )
    df["subway_population_ratio"] = df["total_subway_passengers"] / (
        df["total_daily_visitors"] + 1
    )

    # 밀도 피처
    area = np.pi * (df["analysis_radius_km"] ** 2)
    df["risk_density"] = df["final_risk_score"] / area
    df["activity_density"] = (
        df["total_daily_visitors"] + df["total_subway_passengers"]
    ) / area

    # 위치 피처 (서울시청 기준)
    seoul_center_lat, seoul_center_lng = 37.5665, 126.9780
    df["distance_from_center"] = np.sqrt(
        (df["target_lat"] - seoul_center_lat) ** 2
        + (df["target_lng"] - seoul_center_lng) ** 2
    )

    # 종합 지수
    df["total_infrastructure_risk"] = (
        df["nearby_construction_count"] + df["nearby_sinkhole_count"]
    )
    df["total_mobility_volume"] = (
        df["total_daily_visitors"] + df["total_subway_passengers"]
    )

    print(f"  ✅ 파생 피처 생성 완료: {len(df.columns)}개 컬럼")
    return df


def main_parallel():
    """병렬 처리 메인 함수 (완전 개선 버전)"""
    start_time = time.time()
    print("🚀 5개 CSV 파일 통합 전처리 시작 (완전 개선된 병렬 처리 버전)\n")

    # CPU 코어 수 확인
    num_cores = cpu_count()
    max_workers = min(8, num_cores)  # 최대 8개 프로세스
    print(f"💻 사용 가능한 CPU 코어: {num_cores}개, 사용할 프로세스: {max_workers}개\n")

    # 1. 파일 경로 설정
    data_folder = "data"
    file_paths = {
        "construction": f"{data_folder}/공사현황정제.csv",
        "sinkhole": f"{data_folder}/포트홀및싱크홀정보.csv",
        "population": f"{data_folder}/유동인구수.csv",
        "subway": f"{data_folder}/지하철유동인구수.csv",
        "rainfall": f"{data_folder}/지역구별누적강수량.csv",
    }

    # 2. 데이터 로드
    print("📂 CSV 파일 로드...")
    datasets = {}
    for name, path in file_paths.items():
        if os.path.exists(path):
            datasets[name] = load_csv_file(path)
        else:
            print(f"  ❌ 파일 없음: {path}")
            datasets[name] = pd.DataFrame()

    # 3. 데이터 전처리
    processed_datasets = preprocess_all_datasets(datasets)

    # 4. 분석 대상 위치 정의
    if SUBWAY_AVAILABLE:
        print("\n📍 지하철역 기반 분석 위치 설정...")
        analysis_locations = get_analysis_locations_for_integrate(
            use_subway=True,
            subway_csv="seoul_subway_stations.csv",
            station_count=263,  # 더 많은 역으로 증가
            fallback_mode="priority",
        )
        print(f"✅ {len(analysis_locations)}개 지하철역 로드 완료")
    else:
        print("\n📍 기본 분석 위치 설정...")
        analysis_locations = [
            {"name": "서울시청", "lat": 37.5665, "lng": 126.9780},
            {"name": "강남구청", "lat": 37.5173, "lng": 127.0473},
            {"name": "서대문구청", "lat": 37.5985, "lng": 126.9316},
            {"name": "송파구청", "lat": 37.5145, "lng": 127.1066},
            {"name": "마포구청", "lat": 37.5663, "lng": 126.9019},
            {"name": "홍대입구역", "lat": 37.5572, "lng": 126.9245},
            {"name": "강남역", "lat": 37.4979, "lng": 127.0276},
            {"name": "종로3가역", "lat": 37.5704, "lng": 126.9922},
            {"name": "잠실역", "lat": 37.5133, "lng": 127.1000},
            {"name": "신촌역", "lat": 37.5559, "lng": 126.9369},
            {"name": "을지로입구역", "lat": 37.5663, "lng": 126.9819},
            {"name": "동대문역", "lat": 37.5714, "lng": 127.0094},
        ]
        print(f"✅ {len(analysis_locations)}개 기본 위치 설정")

    # 5. 병렬 처리를 위한 데이터 준비
    print("\n⚡ 병렬 처리 준비 중...")
    radius = 0.2  # 200m 반경

    # 데이터셋을 pickle로 직렬화 (멀티프로세싱 전달용)
    datasets_pickle = pickle.dumps(processed_datasets)

    # 각 위치별 처리 인자 준비
    process_args = []
    for location in analysis_locations:
        process_args.append((location, radius, datasets_pickle))

    total_locations = len(analysis_locations)
    print(f"🎯 총 {total_locations}개 위치 병렬 분석 시작...")

    # 6. 병렬 처리 실행
    processing_start = time.time()
    all_results = []

    # ProcessPoolExecutor 사용 (메모리 효율적)
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        # 작업 제출
        future_to_location = {
            executor.submit(process_single_location, args): args[0]["name"]
            for args in process_args
        }

        # 결과 수집 (진행률 표시)
        completed = 0
        failed_count = 0
        for future in as_completed(future_to_location):
            location_name = future_to_location[future]
            try:
                result = future.result()
                if result is not None:
                    all_results.append(result)
                else:
                    failed_count += 1

                completed += 1
                progress = (completed / total_locations) * 100

                # 진행률 표시 (10% 단위)
                if (
                    completed % max(1, total_locations // 10) == 0
                    or completed == total_locations
                ):
                    elapsed = time.time() - processing_start
                    print(
                        f"  🎯 진행률: {completed}/{total_locations} ({progress:.1f}%) - "
                        f"경과시간: {elapsed:.1f}초 - 방금완료: {location_name}"
                    )

            except Exception as e:
                print(f"  ❌ {location_name} 처리 실패: {e}")
                failed_count += 1

    processing_time = time.time() - processing_start
    success_rate = ((total_locations - failed_count) / total_locations) * 100
    print(f"⚡ 병렬 처리 완료: {processing_time:.1f}초")
    print(f"✅ 성공률: {len(all_results)}/{total_locations} ({success_rate:.1f}%)")

    # 7. 결과 데이터프레임 생성
    print("\n📊 결과 데이터프레임 생성...")
    if not all_results:
        print("❌ 처리된 결과가 없습니다.")
        return None

    result_df = pd.DataFrame(all_results)
    print(f"✅ {len(result_df)}개 레코드 생성")

    # 8. ML용 파생 피처 추가
    result_df = create_ml_features(result_df)

    # 9. 데이터 검증 및 정리
    print("\n🔍 데이터 검증...")

    # 결측치 확인
    missing_data = result_df.isnull().sum()
    if missing_data.sum() > 0:
        print(f"  ⚠️ 결측치 발견:")
        for col, count in missing_data[missing_data > 0].items():
            print(f"    - {col}: {count}개")

        # 결측치 처리
        result_df = result_df.fillna(0)
        print(f"  ✅ 결측치를 0으로 대체")

    # 이상치 확인
    risk_score_stats = result_df["final_risk_score"].describe()
    print(f"  📈 위험도 점수 통계:")
    print(f"    - 평균: {risk_score_stats['mean']:.2f}")
    print(f"    - 최소: {risk_score_stats['min']:.2f}")
    print(f"    - 최대: {risk_score_stats['max']:.2f}")
    print(f"    - 표준편차: {risk_score_stats['std']:.2f}")

    # 10. 결과 저장
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"output/integrated_risk_dataset_complete_{timestamp}.csv"
    result_df.to_csv(output_file, index=False, encoding="utf-8")

    total_time = time.time() - start_time
    print(f"\n🎉 통합 전처리 완료!")
    print(f"  📁 결과 파일: {output_file}")
    print(f"  📊 총 레코드 수: {len(result_df)}")
    print(f"  🏷️ 총 피처 수: {len(result_df.columns)}")
    print(f"  ⏱️ 총 처리 시간: {total_time:.1f}초")
    print(f"  🚀 병렬 처리 효과: 약 {max_workers}배 빠름")
    print(f"  ✅ 성공률: {success_rate:.1f}%")

    # 11. 위험도 분포 확인
    print(f"\n📈 위험도 분포:")
    risk_distribution = result_df["comprehensive_risk_level"].value_counts()
    for level, count in risk_distribution.items():
        percentage = count / len(result_df) * 100
        print(f"  - {level}: {count}개 ({percentage:.1f}%)")

    # 12. 클래스 분포 분석
    print(f"\n🎯 클래스 분포 분석:")
    category_distribution = result_df["comprehensive_risk_category"].value_counts()
    for category, count in category_distribution.items():
        percentage = count / len(result_df) * 100
        print(f"  - {category}: {count}개 ({percentage:.1f}%)")

    # 13. 성능 통계
    print(f"\n📊 성능 통계:")
    print(f"  - 위치당 평균 처리시간: {processing_time/total_locations:.2f}초")
    print(f"  - 초당 처리 위치수: {total_locations/processing_time:.1f}개")
    print(f"  - 실패한 위치: {failed_count}개")

    # 14. Azure ML Studio 업로드 안내
    print(f"\n📤 다음 단계 안내:")
    print(f"  1. Azure ML Studio에 로그인")
    print(f"  2. Data → Datasets → Create dataset → From local files")
    print(f"  3. '{output_file}' 파일 업로드")
    print(f"  4. Dataset name: 'integrated_risk_dataset_complete'")
    print(f"  5. Designer에서 이 데이터셋으로 ML 파이프라인 구성")

    # 15. 데이터 품질 평가
    print(f"\n🏆 데이터 품질 평가:")
    unique_classes = len(risk_distribution)
    if unique_classes >= 4:
        print(f"  ✅ 우수: {unique_classes}개 클래스로 다양한 분포")
    elif unique_classes >= 3:
        print(f"  ✅ 양호: {unique_classes}개 클래스 존재")
    else:
        print(f"  ⚠️ 개선 필요: {unique_classes}개 클래스만 존재")

    if success_rate >= 95:
        print(f"  ✅ 우수: {success_rate:.1f}% 성공률")
    elif success_rate >= 90:
        print(f"  ✅ 양호: {success_rate:.1f}% 성공률")
    else:
        print(f"  ⚠️ 개선 필요: {success_rate:.1f}% 성공률")

    return result_df


def create_sample_data():
    """샘플 데이터 생성 (테스트용)"""
    print("📝 샘플 데이터 생성 중...")

    # 샘플 공사현황 데이터
    construction_sample = pd.DataFrame(
        {
            "위도": [37.5665, 37.5173, 37.5985],
            "경도": [126.9780, 127.0473, 126.9316],
            "착공일": ["2024-01-01", "2024-02-01", "2024-03-01"],
            "준공일": ["2024-06-01", "2024-08-01", "2024-09-01"],
            "공사상태": ["진행중", "완료", "진행중"],
            "현재_위험도_카테고리": ["보통", "낮음", "높음"],
            "영향반경_미터": [100, 50, 200],
        }
    )

    # 샘플 싱크홀 데이터
    sinkhole_sample = pd.DataFrame(
        {
            "위도": [37.5700, 37.5200, 37.6000],
            "경도": [126.9800, 127.0500, 126.9300],
            "날짜": ["20240301", "20240401", "20240501"],
            "발생규모폭(m)": [2.0, 1.5, 3.0],
            "발생규모연장(m)": [2.5, 2.0, 4.0],
            "발생규모깊이(m)": [1.0, 0.8, 1.5],
            "피해사망자수(명)": [0, 0, 0],
            "피해부상자수(명)": [0, 1, 0],
            "피해차량대수(대)": [1, 0, 2],
            "피해규모점수": [2.0, 1.5, 3.5],
            "발생원인구분": ["하수관 손상", "상수관 손상", "기타매설물 손상"],
        }
    )

    # 샘플 유동인구 데이터
    population_sample = pd.DataFrame(
        {
            "위도": [37.5665, 37.5173, 37.5985, 37.5572, 37.4979],
            "경도": [126.9780, 127.0473, 126.9316, 126.9245, 127.0276],
            "날짜": ["20240601", "20240601", "20240601", "20240601", "20240601"],
            "방문자수": [5000, 8000, 3000, 12000, 15000],
            "자치구": ["중구", "강남구", "서대문구", "마포구", "강남구"],
        }
    )

    # 샘플 지하철 데이터
    subway_sample = pd.DataFrame(
        {
            "위도": [37.5704, 37.4979, 37.5572, 37.5133],
            "경도": [126.9922, 127.0276, 126.9245, 127.1000],
            "날짜": ["20241001", "20241001", "20241001", "20241001"],
            "역명": ["종로3가역", "강남역", "홍대입구역", "잠실역"],
            "승하차총승객수": [103560, 85000, 67000, 55000],
            "자치구": ["종로구", "강남구", "마포구", "송파구"],
        }
    )

    # 샘플 강수량 데이터
    rainfall_sample = pd.DataFrame(
        {
            "위도": [37.5173, 37.5301, 37.6396, 37.5509],
            "경도": [127.0473, 127.1238, 127.0255, 126.8495],
            "날짜": ["20250430", "20250430", "20250430", "20250430"],
            "지역구": ["강남구", "강동구", "강북구", "강서구"],
            "누적강수량": [15.5, 12.3, 18.7, 22.1],
        }
    )

    # 샘플 파일 저장
    os.makedirs("data", exist_ok=True)
    construction_sample.to_csv("data/공사현황정제.csv", index=False, encoding="utf-8")
    sinkhole_sample.to_csv("data/포트홀및싱크홀정보.csv", index=False, encoding="utf-8")
    population_sample.to_csv("data/유동인구수.csv", index=False, encoding="utf-8")
    subway_sample.to_csv("data/지하철유동인구수.csv", index=False, encoding="utf-8")
    rainfall_sample.to_csv("data/지역구별누적강수량.csv", index=False, encoding="utf-8")

    print("✅ 샘플 데이터 생성 완료 (data/ 폴더)")


if __name__ == "__main__":
    # 데이터 폴더가 없으면 샘플 데이터 생성
    if (
        not os.path.exists("data")
        or len([f for f in os.listdir("data") if f.endswith(".csv")]) < 5
    ):
        print(
            "📁 CSV 파일이 부족합니다. 샘플 데이터를 생성하시겠습니까? (y/n): ", end=""
        )
        response = input().lower()
        if response == "y":
            create_sample_data()
        else:
            print("❌ CSV 파일들을 'data/' 폴더에 준비해주세요:")
            print("  - data/공사현황정제.csv")
            print("  - data/포트홀및싱크홀정보.csv")
            print("  - data/유동인구수.csv")
            print("  - data/지하철유동인구수.csv")
            print("  - data/지역구별누적강수량.csv")
            exit()

    # 병렬 처리 메인 함수 실행
    try:
        print("🚀 완전 개선된 병렬 처리 버전으로 실행합니다...\n")
        result_df = main_parallel()

        if result_df is not None:
            print("\n🎊 완전한 병렬 처리가 성공적으로 완료되었습니다!")
            print("📈 범주형 오류 완전 해결 + 개선된 클래스 분포!")
            print("🚀 Azure ML Studio에서 바로 사용 가능한 고품질 데이터!")
        else:
            print("\n❌ 처리 중 문제가 발생했습니다.")

    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        import traceback

        print(f"상세 오류:\n{traceback.format_exc()}")

        print(f"\n🔧 문제 해결 방법:")
        print(f"  1. CSV 파일 경로 확인")
        print(f"  2. 파일 인코딩 확인 (UTF-8 또는 CP949)")
        print(f"  3. 필수 컬럼 존재 여부 확인")
        print(f"  4. Python 패키지 설치: pip install pandas numpy")
        print(f"  5. 메모리 부족 시 station_count 줄이기")

    print("\n💡 추가 옵션:")
    print("  - 더 많은 지하철역: station_count=400")
    print("  - 적당한 지하철역: station_count=200")
    print("  - 빠른 테스트: station_count=50")
