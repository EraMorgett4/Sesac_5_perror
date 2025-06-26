"""
5개 CSV 파일 통합 전처리 스크립트
- 공사현황.csv
- 포트홀_싱크홀.csv
- 유동인구수.csv
- 지하철유동인구.csv
- 지역구별_강수량.csv
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from math import radians, cos, sin, asin, sqrt
import os
import warnings

warnings.filterwarnings("ignore")


def haversine_distance(lat1, lon1, lat2, lon2):
    """두 지점 간 거리 계산 (km)"""
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
        print(f"Loading {file_path}...")
        df = pd.read_csv(file_path, encoding=encoding)
        print(f"  ✅ Success: {df.shape[0]} rows, {df.shape[1]} columns")
        return df
    except UnicodeDecodeError:
        try:
            print(f"  ⚠️ UTF-8 failed, trying cp949...")
            df = pd.read_csv(file_path, encoding="cp949")
            print(f"  ✅ Success with cp949: {df.shape[0]} rows, {df.shape[1]} columns")
            return df
        except Exception as e:
            print(f"  ❌ Failed to load {file_path}: {e}")
            return pd.DataFrame()
    except Exception as e:
        print(f"  ❌ Failed to load {file_path}: {e}")
        return pd.DataFrame()


def validate_seoul_coordinates(df, lat_col="위도", lng_col="경도"):
    """서울시 좌표 범위 검증"""
    if lat_col not in df.columns or lng_col not in df.columns:
        print(f"  ⚠️ 좌표 컬럼 없음: {lat_col}, {lng_col}")
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
    after_count = len(df_clean)

    print(
        f"  📍 좌표 검증: {before_count} → {after_count} ({after_count/before_count*100:.1f}%)"
    )
    return df_clean


def preprocess_construction_data(df):
    """공사현황 데이터 전처리"""
    print("\n🏗️ 공사현황 데이터 전처리...")

    if df.empty:
        return df

    df_clean = validate_seoul_coordinates(df)

    # 날짜 처리
    date_columns = ["착공일", "준공일"]
    for col in date_columns:
        if col in df_clean.columns:
            df_clean[col] = pd.to_datetime(df_clean[col], errors="coerce")
            print(f"  📅 {col} 처리완료")

    # 공사 기간 계산
    if "착공일" in df_clean.columns and "준공일" in df_clean.columns:
        df_clean["공사기간_일"] = (df_clean["준공일"] - df_clean["착공일"]).dt.days
        df_clean["공사기간_일"] = df_clean["공사기간_일"].fillna(0)
        print(f"  ⏱️ 공사기간 계산완료")

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
        if col in df_clean.columns:
            new_col = col.replace("카테고리", "수치")
            df_clean[new_col] = df_clean[col].map(risk_mapping).fillna(1)
            print(f"  📊 {col} → {new_col} 변환완료")

    # 공사상태 수치화
    if "공사상태" in df_clean.columns:
        status_mapping = {"진행중": 3, "일시중단": 2, "완료": 1}
        df_clean["공사상태_수치"] = df_clean["공사상태"].map(status_mapping).fillna(1)
        print(f"  🚧 공사상태 수치화 완료")

    # 영향반경 처리
    if "영향반경_미터" in df_clean.columns:
        df_clean["영향반경_미터"] = pd.to_numeric(
            df_clean["영향반경_미터"], errors="coerce"
        ).fillna(50)
        df_clean["영향반경_km"] = df_clean["영향반경_미터"] / 1000
        print(f"  📏 영향반경 처리완료")

    print(f"  ✅ 공사현황 전처리 완료: {len(df_clean)} 레코드")
    return df_clean


def preprocess_sinkhole_data(df):
    """포트홀/싱크홀 데이터 전처리"""
    print("\n🕳️ 포트홀/싱크홀 데이터 전처리...")

    if df.empty:
        return df

    df_clean = validate_seoul_coordinates(df)

    # 날짜 처리
    if "날짜" in df_clean.columns:
        df_clean["날짜"] = pd.to_datetime(
            df_clean["날짜"], format="%Y%m%d", errors="coerce"
        )
        print(f"  📅 날짜 처리완료")

    # 발생 규모 수치화
    size_columns = ["발생규모폭(m)", "발생규모연장(m)", "발생규모깊이(m)"]
    for col in size_columns:
        if col in df_clean.columns:
            df_clean[col] = pd.to_numeric(df_clean[col], errors="coerce").fillna(0)

    # 규모 부피 계산
    if all(col in df_clean.columns for col in size_columns):
        df_clean["규모_부피"] = (
            df_clean["발생규모폭(m)"]
            * df_clean["발생규모연장(m)"]
            * df_clean["발생규모깊이(m)"]
        )
        print(f"  📐 규모 부피 계산완료")

    # 피해 수치화
    damage_columns = [
        "피해사망자수(명)",
        "피해부상자수(명)",
        "피해차량대수(대)",
        "피해규모점수",
    ]
    for col in damage_columns:
        if col in df_clean.columns:
            df_clean[col] = pd.to_numeric(df_clean[col], errors="coerce").fillna(0)

    # 총 피해 점수 계산
    if all(col in df_clean.columns for col in damage_columns):
        df_clean["총_피해점수"] = (
            df_clean["피해사망자수(명)"] * 100
            + df_clean["피해부상자수(명)"] * 10
            + df_clean["피해차량대수(대)"] * 5
            + df_clean["피해규모점수"] * 2
        )
        print(f"  💥 총 피해점수 계산완료")

    # 발생 원인 위험도
    if "발생원인구분" in df_clean.columns:
        cause_mapping = {
            "하수관 손상": 3,
            "상수관 손상": 3,
            "기타매설물 손상": 2,
            "자연발생": 1,
        }
        df_clean["원인_위험도"] = df_clean["발생원인구분"].map(cause_mapping).fillna(2)
        print(f"  🔧 발생원인 위험도 계산완료")

    # 최근성 가중치
    if "날짜" in df_clean.columns:
        current_date = datetime.now()
        df_clean["발생후_경과일"] = (current_date - df_clean["날짜"]).dt.days
        df_clean["발생후_경과일"] = df_clean["발생후_경과일"].fillna(9999)

        df_clean["최근성_가중치"] = np.where(
            df_clean["발생후_경과일"] <= 365,
            1.0,
            np.where(df_clean["발생후_경과일"] <= 730, 0.5, 0.1),
        )
        print(f"  ⏰ 최근성 가중치 계산완료")

    print(f"  ✅ 싱크홀 전처리 완료: {len(df_clean)} 레코드")
    return df_clean


def preprocess_population_data(df):
    """유동인구 데이터 전처리"""
    print("\n👥 유동인구 데이터 전처리...")

    if df.empty:
        return df

    df_clean = validate_seoul_coordinates(df)

    # 날짜 처리
    if "날짜" in df_clean.columns:
        df_clean["날짜"] = pd.to_datetime(
            df_clean["날짜"], format="%Y%m%d", errors="coerce"
        )
        print(f"  📅 날짜 처리완료")

    # 방문자수 수치화
    if "방문자수" in df_clean.columns:
        df_clean["방문자수"] = pd.to_numeric(
            df_clean["방문자수"], errors="coerce"
        ).fillna(0)
        print(f"  👤 방문자수 수치화완료")

    # 유동인구 밀도 등급
    if "방문자수" in df_clean.columns:
        df_clean["인구밀도등급"] = pd.cut(
            df_clean["방문자수"],
            bins=[0, 200, 500, 1000, float("inf")],
            labels=[1, 2, 3, 4],
            include_lowest=True,
        )
        df_clean["인구밀도등급"] = df_clean["인구밀도등급"].fillna(1)
        print(f"  📈 인구밀도등급 분류완료")

    # 자치구별 통계 (있는 경우)
    if "자치구" in df_clean.columns and "방문자수" in df_clean.columns:
        district_stats = (
            df_clean.groupby("자치구")["방문자수"].agg(["mean", "max"]).reset_index()
        )
        district_stats.columns = ["자치구", "구_평균방문자", "구_최대방문자"]
        df_clean = df_clean.merge(district_stats, on="자치구", how="left")
        print(f"  🏢 자치구별 통계 생성완료")

    print(f"  ✅ 유동인구 전처리 완료: {len(df_clean)} 레코드")
    return df_clean


def preprocess_subway_data(df):
    """지하철 유동인구 데이터 전처리"""
    print("\n🚇 지하철 유동인구 데이터 전처리...")

    if df.empty:
        return df

    df_clean = validate_seoul_coordinates(df)

    # 날짜 처리
    if "날짜" in df_clean.columns:
        df_clean["날짜"] = pd.to_datetime(
            df_clean["날짜"], format="%Y%m%d", errors="coerce"
        )
        print(f"  📅 날짜 처리완료")

    # 승하차 승객수 수치화
    if "승하차총승객수" in df_clean.columns:
        df_clean["승하차총승객수"] = pd.to_numeric(
            df_clean["승하차총승객수"], errors="coerce"
        ).fillna(0)
        print(f"  🚊 승하차승객수 수치화완료")

    # 지하철 이용 수준 분류
    if "승하차총승객수" in df_clean.columns:
        df_clean["지하철이용수준"] = pd.cut(
            df_clean["승하차총승객수"],
            bins=[0, 10000, 30000, 60000, float("inf")],
            labels=[1, 2, 3, 4],
            include_lowest=True,
        )
        df_clean["지하철이용수준"] = df_clean["지하철이용수준"].fillna(1)
        print(f"  🚉 지하철이용수준 분류완료")

    # 역 중요도 계산
    if "승하차총승객수" in df_clean.columns:
        max_passengers = df_clean["승하차총승객수"].max()
        df_clean["역_중요도"] = df_clean["승하차총승객수"] / (max_passengers + 1)
        print(f"  ⭐ 역 중요도 계산완료")

    # 자치구별 지하철 통계
    if "자치구" in df_clean.columns and "승하차총승객수" in df_clean.columns:
        subway_stats = (
            df_clean.groupby("자치구")["승하차총승객수"]
            .agg(["mean", "sum", "count"])
            .reset_index()
        )
        subway_stats.columns = [
            "자치구",
            "구_평균지하철승객",
            "구_총지하철승객",
            "구_지하철역수",
        ]
        df_clean = df_clean.merge(subway_stats, on="자치구", how="left")
        print(f"  🏢 자치구별 지하철 통계 생성완료")

    print(f"  ✅ 지하철 전처리 완료: {len(df_clean)} 레코드")
    return df_clean


def preprocess_rainfall_data(df):
    """강수량 데이터 전처리"""
    print("\n🌧️ 강수량 데이터 전처리...")

    if df.empty:
        return df

    df_clean = validate_seoul_coordinates(df)

    # 날짜 처리
    if "날짜" in df_clean.columns:
        df_clean["날짜"] = pd.to_datetime(
            df_clean["날짜"], format="%Y%m%d", errors="coerce"
        )
        print(f"  📅 날짜 처리완료")

    # 누적강수량 수치화
    if "누적강수량" in df_clean.columns:
        df_clean["누적강수량"] = pd.to_numeric(
            df_clean["누적강수량"], errors="coerce"
        ).fillna(0)
        print(f"  💧 누적강수량 수치화완료")

    # 강수량 위험도 등급
    if "누적강수량" in df_clean.columns:
        df_clean["강수량위험등급"] = pd.cut(
            df_clean["누적강수량"],
            bins=[0, 1, 5, 20, 60, float("inf")],
            labels=[0, 1, 2, 3, 4],
            include_lowest=True,
        )
        df_clean["강수량위험등급"] = df_clean["강수량위험등급"].fillna(0)
        print(f"  ⛈️ 강수량위험등급 분류완료")

    # 시간 가중치 (최근 데이터일수록 높은 가중치)
    if "날짜" in df_clean.columns:
        current_date = datetime.now()
        df_clean["강수후_경과일"] = (current_date - df_clean["날짜"]).dt.days
        df_clean["강수후_경과일"] = df_clean["강수후_경과일"].fillna(9999)

        df_clean["강수_시간가중치"] = np.where(
            df_clean["강수후_경과일"] <= 7,
            1.0,
            np.where(
                df_clean["강수후_경과일"] <= 30,
                0.7,
                np.where(df_clean["강수후_경과일"] <= 90, 0.4, 0.1),
            ),
        )
        print(f"  ⏰ 강수 시간가중치 계산완료")

    print(f"  ✅ 강수량 전처리 완료: {len(df_clean)} 레코드")
    return df_clean


def calculate_location_risk_features(
    target_lat, target_lng, location_name, radius_km, datasets
):
    """특정 위치의 위험도 피처 계산"""

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
    }

    # 각 데이터셋 분석
    for dataset_name, df in datasets.items():
        if df.empty:
            continue

        # 거리 계산
        df["거리"] = df.apply(
            lambda row: haversine_distance(
                target_lat, target_lng, row["위도"], row["경도"]
            ),
            axis=1,
        )
        nearby_data = df[df["거리"] <= radius_km]

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
        "population_density_score": visitors.mean() / 1000,  # 정규화
    }


def analyze_subway_risk(nearby_data):
    """지하철 위험도 분석"""
    if nearby_data.empty:
        return {
            "nearby_subway_stations": 0,
            "avg_subway_passengers": 0,
            "total_subway_passengers": 0,
            "subway_congestion_risk": 0,
        }

    passengers = nearby_data.get("승하차총승객수", pd.Series([0]))

    return {
        "nearby_subway_stations": len(nearby_data),
        "avg_subway_passengers": passengers.mean(),
        "total_subway_passengers": passengers.sum(),
        "subway_congestion_risk": passengers.mean() / 50000,  # 정규화
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
    """종합 위험도 계산"""

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

    # 0-100 스케일로 정규화
    final_risk_score = min(100, max(0, comprehensive_risk * 25))

    # 위험도 등급 분류
    if final_risk_score >= 80:
        risk_level = "매우높음"
        risk_category = "최고위험"
    elif final_risk_score >= 65:
        risk_level = "높음"
        risk_category = "상위험"
    elif final_risk_score >= 45:
        risk_level = "보통"
        risk_category = "중위험"
    elif final_risk_score >= 25:
        risk_level = "낮음"
        risk_category = "하위험"
    else:
        risk_level = "매우낮음"
        risk_category = "최저위험"

    # 결과 업데이트
    features.update(
        {
            "physical_risk_score": physical_risk * 25,
            "social_risk_score": social_risk * 25,
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


def main():
    """메인 실행 함수"""
    print("🚀 5개 CSV 파일 통합 전처리 시작\n")

    # 1. 파일 경로 설정
    data_folder = "data"  # CSV 파일들이 있는 폴더
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
    print("\n🔄 데이터 전처리 시작...")
    processed_datasets = {}

    if not datasets["construction"].empty:
        processed_datasets["construction"] = preprocess_construction_data(
            datasets["construction"]
        )
    else:
        processed_datasets["construction"] = pd.DataFrame()

    if not datasets["sinkhole"].empty:
        processed_datasets["sinkhole"] = preprocess_sinkhole_data(datasets["sinkhole"])
    else:
        processed_datasets["sinkhole"] = pd.DataFrame()

    if not datasets["population"].empty:
        processed_datasets["population"] = preprocess_population_data(
            datasets["population"]
        )
    else:
        processed_datasets["population"] = pd.DataFrame()

    if not datasets["subway"].empty:
        processed_datasets["subway"] = preprocess_subway_data(datasets["subway"])
    else:
        processed_datasets["subway"] = pd.DataFrame()

    if not datasets["rainfall"].empty:
        processed_datasets["rainfall"] = preprocess_rainfall_data(datasets["rainfall"])
    else:
        processed_datasets["rainfall"] = pd.DataFrame()

    # 4. 분석 대상 위치 정의
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

    # 5. 위치별 위험도 분석
    print("\n📍 위치별 위험도 분석...")
    all_results = []
    radius_options = [0.5, 1.0, 2.0]  # 분석 반경 (km)

    for i, location in enumerate(analysis_locations):
        for j, radius in enumerate(radius_options):
            print(
                f"  🎯 {location['name']} (반경 {radius}km) 분석 중... [{i*3+j+1}/{len(analysis_locations)*3}]"
            )

            # 위험도 피처 계산
            risk_features = calculate_location_risk_features(
                location["lat"],
                location["lng"],
                location["name"],
                radius,
                processed_datasets,
            )

            # 종합 위험도 계산
            comprehensive_features = calculate_comprehensive_risk(risk_features)
            all_results.append(comprehensive_features)

    # 6. 결과 데이터프레임 생성
    print("\n📊 결과 데이터프레임 생성...")
    result_df = pd.DataFrame(all_results)

    # 7. ML용 파생 피처 추가
    result_df = create_ml_features(result_df)

    # 8. 데이터 검증 및 정리
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

    # 9. 결과 저장
    output_file = f"{data_folder}/integrated_risk_dataset.csv"
    result_df.to_csv(output_file, index=False, encoding="utf-8")

    print(f"\n🎉 통합 전처리 완료!")
    print(f"  📁 결과 파일: {output_file}")
    print(f"  📊 총 레코드 수: {len(result_df)}")
    print(f"  🏷️ 총 피처 수: {len(result_df.columns)}")

    # 10. 위험도 분포 확인
    print(f"\n📈 위험도 분포:")
    risk_distribution = result_df["comprehensive_risk_level"].value_counts()
    for level, count in risk_distribution.items():
        percentage = count / len(result_df) * 100
        print(f"  - {level}: {count}개 ({percentage:.1f}%)")

    # 11. 주요 피처 요약
    print(f"\n🔧 주요 ML 피처 목록:")
    ml_features = [
        "final_risk_score",  # 타겟 변수 (회귀)
        "comprehensive_risk_category",  # 타겟 변수 (분류)
        "weighted_construction_risk",
        "weighted_sinkhole_risk",
        "weighted_rainfall_risk",
        "total_daily_visitors",
        "total_subway_passengers",
        "nearby_subway_stations",
        "rainfall_amplification_factor",
        "analysis_radius_km",
        "distance_from_center",
        "construction_rainfall_interaction",
        "population_physical_interaction",
        "activity_density",
        "risk_density",
    ]

    for feature in ml_features:
        if feature in result_df.columns:
            dtype = result_df[feature].dtype
            non_zero = (result_df[feature] != 0).sum()
            print(f"  ✅ {feature} ({dtype}): {non_zero}/{len(result_df)} non-zero")
        else:
            print(f"  ❌ {feature}: 없음")

    # 12. 샘플 데이터 표시
    print(f"\n📋 샘플 데이터 (상위 5개):")
    sample_columns = [
        "location_name",
        "analysis_radius_km",
        "final_risk_score",
        "comprehensive_risk_level",
    ]
    print(result_df[sample_columns].head().to_string(index=False))

    # 13. Azure ML Studio 업로드 안내
    print(f"\n📤 다음 단계 안내:")
    print(f"  1. Azure ML Studio에 로그인")
    print(f"  2. Data → Datasets → Create dataset → From local files")
    print(f"  3. '{output_file}' 파일 업로드")
    print(f"  4. Dataset name: 'integrated_risk_dataset'")
    print(f"  5. Designer에서 이 데이터셋으로 ML 파이프라인 구성")

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
    subway_sample.to_csv("data/지하철유동인구.csv", index=False, encoding="utf-8")
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
            print("  - data/공사현황.csv")
            print("  - data/포트홀_싱크홀.csv")
            print("  - data/유동인구수.csv")
            print("  - data/지하철유동인구.csv")
            print("  - data/지역구별_강수량.csv")
            exit()

    # 메인 처리 실행
    try:
        result_df = main()
        print("\n🎊 전체 처리가 성공적으로 완료되었습니다!")

    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        import traceback

        print(f"상세 오류:\n{traceback.format_exc()}")

        print(f"\n🔧 문제 해결 방법:")
        print(f"  1. CSV 파일 경로 확인")
        print(f"  2. 파일 인코딩 확인 (UTF-8 또는 CP949)")
        print(f"  3. 필수 컬럼 존재 여부 확인")
        print(f"  4. Python 패키지 설치: pip install pandas numpy")
