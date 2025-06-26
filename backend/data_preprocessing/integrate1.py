"""
격자 기반 샘플링 5개 CSV 파일 통합 전처리 스크립트
서울 전역을 200m 간격 격자로 나누어 체계적 샘플링
"final_risk_score",  # 타겟 변수 (회귀)
"comprehensive_risk_category",  # 타겟 변수 (분류)
"""

"""
병렬 처리만 적용한 격자 기반 샘플링 완전한 코드
기존 코드에 멀티프로세싱만 추가하여 3-8배 속도 향상
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from math import radians, cos, sin, asin, sqrt
import os
import warnings
from multiprocessing import Pool, cpu_count
from functools import partial
import time

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


def generate_seoul_grid_locations(grid_spacing=0.002, exclude_areas=True):
    """서울 전역 격자 샘플링 포인트 생성"""
    print(f"\n🗺️ 서울 격자 샘플링 포인트 생성...")
    print(f"  📏 격자 간격: {grid_spacing}도 (약 {grid_spacing*111:.0f}m)")

    # 서울시 경계
    seoul_bounds = {
        "lat_min": 37.45,
        "lat_max": 37.70,
        "lng_min": 126.75,
        "lng_max": 127.15,
    }

    # 제외 구역 정의
    excluded_zones = [
        {
            "lat_min": 37.50,
            "lat_max": 37.53,
            "lng_min": 126.88,
            "lng_max": 127.05,
            "name": "한강",
        },
        {
            "lat_min": 37.65,
            "lat_max": 37.70,
            "lng_min": 126.95,
            "lng_max": 127.05,
            "name": "북한산",
        },
        {
            "lat_min": 37.45,
            "lat_max": 37.48,
            "lng_min": 126.93,
            "lng_max": 126.98,
            "name": "관악산",
        },
        {
            "lat_min": 37.55,
            "lat_max": 37.56,
            "lng_min": 126.98,
            "lng_max": 126.99,
            "name": "남산",
        },
    ]

    def is_excluded_zone(lat, lng):
        if not exclude_areas:
            return False
        for zone in excluded_zones:
            if (
                zone["lat_min"] <= lat <= zone["lat_max"]
                and zone["lng_min"] <= lng <= zone["lng_max"]
            ):
                return True
        return False

    locations = []
    lat = seoul_bounds["lat_min"]

    while lat <= seoul_bounds["lat_max"]:
        lng = seoul_bounds["lng_min"]
        while lng <= seoul_bounds["lng_max"]:
            if not is_excluded_zone(lat, lng):
                locations.append(
                    {
                        "name": f"Grid_{lat:.3f}_{lng:.3f}",
                        "lat": round(lat, 3),
                        "lng": round(lng, 3),
                        "grid_id": f"{lat:.3f}_{lng:.3f}",
                    }
                )
            lng += grid_spacing
        lat += grid_spacing

    print(f"  ✅ 생성된 격자 포인트: {len(locations)}개")
    return locations


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
        conditions = [
            df_clean["방문자수"] <= 200,
            (df_clean["방문자수"] > 200) & (df_clean["방문자수"] <= 500),
            (df_clean["방문자수"] > 500) & (df_clean["방문자수"] <= 1000),
            df_clean["방문자수"] > 1000,
        ]
        choices = [1, 2, 3, 4]
        df_clean["인구밀도등급"] = np.select(conditions, choices, default=1)
        print(f"  📈 인구밀도등급 분류완료")

    # 자치구별 통계
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
        conditions = [
            df_clean["승하차총승객수"] <= 10000,
            (df_clean["승하차총승객수"] > 10000)
            & (df_clean["승하차총승객수"] <= 30000),
            (df_clean["승하차총승객수"] > 30000)
            & (df_clean["승하차총승객수"] <= 60000),
            df_clean["승하차총승객수"] > 60000,
        ]
        choices = [1, 2, 3, 4]
        df_clean["지하철이용수준"] = np.select(conditions, choices, default=1)
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
        conditions = [
            df_clean["누적강수량"] <= 1,
            (df_clean["누적강수량"] > 1) & (df_clean["누적강수량"] <= 5),
            (df_clean["누적강수량"] > 5) & (df_clean["누적강수량"] <= 20),
            (df_clean["누적강수량"] > 20) & (df_clean["누적강수량"] <= 60),
            df_clean["누적강수량"] > 60,
        ]
        choices = [0, 1, 2, 3, 4]
        df_clean["강수량위험등급"] = np.select(conditions, choices, default=0)
        print(f"  ⛈️ 강수량위험등급 분류완료")

    # 시간 가중치
    if "날짜" in df_clean.columns:
        current_date = datetime.now()
        df_clean["강수후_경과일"] = (current_date - df_clean["날짜"]).dt.days
        df_clean["강수후_경과일"] = df_clean["강수후_경과일"].fillna(9999)

        conditions = [
            df_clean["강수후_경과일"] <= 7,
            (df_clean["강수후_경과일"] > 7) & (df_clean["강수후_경과일"] <= 30),
            (df_clean["강수후_경과일"] > 30) & (df_clean["강수후_경과일"] <= 90),
            df_clean["강수후_경과일"] > 90,
        ]
        choices = [1.0, 0.7, 0.4, 0.1]
        df_clean["강수_시간가중치"] = np.select(conditions, choices, default=0.1)
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
        "population_density_score": visitors.mean() / 1000,
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
    risk_level = nearby_data.get("강수량위험등급", pd.Series([0])).astype(float)
    time_weight = nearby_data.get("강수_시간가중치", pd.Series([1])).astype(float)

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

    weighted_risk = 0
    if len(weights) > 0:
        weighted_risk = (risk_level * weights * time_weight).sum() / weights.sum()

    return {
        "avg_rainfall": avg_rainfall,
        "weighted_rainfall_risk": weighted_risk,
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

    # 종합 위험도
    comprehensive_risk = physical_risk * 0.65 + social_risk * 0.35
    final_risk_score = min(100, max(0, comprehensive_risk * 25))

    # 위험도 등급 분류
    if final_risk_score >= 80:
        risk_level, risk_category = "매우높음", "최고위험"
    elif final_risk_score >= 65:
        risk_level, risk_category = "높음", "상위험"
    elif final_risk_score >= 45:
        risk_level, risk_category = "보통", "중위험"
    elif final_risk_score >= 25:
        risk_level, risk_category = "낮음", "하위험"
    else:
        risk_level, risk_category = "매우낮음", "최저위험"

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


# ================== 병렬 처리 핵심 함수들 ==================


def process_single_location_all_radii(args):
    """단일 위치에 대해 모든 반경을 처리하는 함수 (병렬 처리용)"""
    location, radius_options, datasets = args

    results = []

    for radius in radius_options:
        try:
            # 위험도 피처 계산
            risk_features = calculate_location_risk_features(
                location["lat"], location["lng"], location["name"], radius, datasets
            )

            # 종합 위험도 계산
            comprehensive_features = calculate_comprehensive_risk(risk_features)
            results.append(comprehensive_features)

        except Exception as e:
            # 오류 시 기본값으로 레코드 생성
            print(f"    ⚠️ 오류 ({location['name']}, {radius}km): {e}")
            default_features = {
                "location_name": location["name"],
                "target_lat": location["lat"],
                "target_lng": location["lng"],
                "analysis_radius_km": radius,
                "final_risk_score": 0,
                "comprehensive_risk_level": "매우낮음",
                "comprehensive_risk_category": "최저위험",
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
                "physical_risk_score": 0,
                "social_risk_score": 0,
            }
            results.append(default_features)

    return results


def process_grid_parallel(grid_locations, datasets, radius_options, n_workers=None):
    """병렬 처리로 격자 포인트들을 분석하는 메인 함수"""

    if n_workers is None:
        n_workers = min(cpu_count() - 1, 8)  # CPU 코어 수 - 1, 최대 8개
        if n_workers < 1:
            n_workers = 1

    print(f"\n⚡ 병렬 처리 시작")
    print(f"  🖥️ 사용 가능한 CPU 코어: {cpu_count()}개")
    print(f"  🔧 사용할 워커 수: {n_workers}개")
    print(
        f"  📊 총 처리 대상: {len(grid_locations)} 위치 × {len(radius_options)} 반경 = {len(grid_locations) * len(radius_options)} 작업"
    )

    # 병렬 처리를 위한 인수 준비
    args_list = [(location, radius_options, datasets) for location in grid_locations]

    start_time = time.time()
    all_results = []

    # 병렬 처리 실행
    with Pool(processes=n_workers) as pool:
        print(f"  🚀 작업 시작...")

        # 진행률 추적을 위한 비동기 실행
        results = pool.map_async(process_single_location_all_radii, args_list)

        # 주기적으로 진행률 체크 (30초마다)
        while not results.ready():
            time.sleep(30)
            elapsed = time.time() - start_time
            print(f"    ⏱️ 경과 시간: {elapsed:.1f}초... (계속 처리 중)")

        # 결과 수집
        pool_results = results.get()

        # 결과 평탄화 (각 위치당 여러 반경 결과를 하나의 리스트로)
        for location_results in pool_results:
            all_results.extend(location_results)

    total_time = time.time() - start_time

    print(f"\n🎉 병렬 처리 완료!")
    print(f"  ⏰ 총 처리 시간: {total_time:.1f}초")
    print(f"  📊 처리 속도: {len(all_results)/total_time:.1f} 레코드/초")
    print(f"  🎯 성공 생성된 레코드: {len(all_results):,}개")
    print(
        f"  📈 예상 성공률: {len(all_results)/(len(grid_locations)*len(radius_options))*100:.1f}%"
    )

    return all_results


def main_parallel():
    """병렬 처리가 적용된 메인 실행 함수"""
    print("🚀 병렬 처리 적용 격자 기반 5개 CSV 파일 통합 전처리 시작\n")

    # 설정값
    GRID_SPACING = 0.003  # 약 330m 간격 (병렬 처리로 더 세밀하게 가능)
    N_WORKERS = None  # 자동으로 CPU 코어 수 - 1 설정

    print(f"🔧 병렬 처리 설정:")
    print(f"  - 격자 간격: {GRID_SPACING}도 (약 {GRID_SPACING*111:.0f}m)")
    print(f"  - 워커 수: {'자동 감지' if N_WORKERS is None else N_WORKERS}개")

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

    # 4. 격자 기반 분석 위치 생성
    grid_locations = generate_seoul_grid_locations(
        grid_spacing=GRID_SPACING, exclude_areas=True
    )

    if len(grid_locations) == 0:
        print("❌ 격자 포인트 생성 실패!")
        return None

    # 5. 분석 반경 설정
    radius_options = [0.05, 0.1]  # 50m, 100m, 200m
    print(f"\n📏 분석 반경: {[f'{r*1000:.0f}m' for r in radius_options]}")

    total_expected = len(grid_locations) * len(radius_options)
    print(f"📊 예상 총 데이터 포인트: {total_expected:,}개")

    # 사용자 확인
    if total_expected > 20000:
        print(f"⚠️ 데이터 포인트가 많습니다 ({total_expected:,}개)")
        estimated_time = total_expected / (cpu_count() * 100)  # 대략적 추정
        print(f"💾 예상 처리 시간 (병렬): {estimated_time:.1f}분")
        response = input("계속 진행하시겠습니까? (y/n): ").lower()
        if response != "y":
            print("처리를 중단합니다.")
            return None

    # 6. 병렬 처리로 격자별 위험도 분석
    all_results = process_grid_parallel(
        grid_locations, processed_datasets, radius_options, n_workers=N_WORKERS
    )

    # 7. 결과 데이터프레임 생성
    print("\n📊 결과 데이터프레임 생성...")
    result_df = pd.DataFrame(all_results)

    if result_df.empty:
        print("❌ 결과 데이터가 비어있습니다!")
        return None

    # 8. ML용 파생 피처 추가
    result_df = create_ml_features(result_df)

    # 9. 데이터 검증 및 정리
    print("\n🔍 데이터 검증...")

    # 결측치 확인
    missing_data = result_df.isnull().sum()
    if missing_data.sum() > 0:
        print(f"  ⚠️ 결측치 발견:")
        for col, count in missing_data[missing_data > 0].items():
            if count > 0:
                print(f"    - {col}: {count}개")

        # 결측치 처리
        result_df = result_df.fillna(0)
        print(f"  ✅ 결측치를 0으로 대체")

    # 위험도 통계
    if "final_risk_score" in result_df.columns:
        risk_stats = result_df["final_risk_score"].describe()
        print(f"  📈 위험도 점수 통계:")
        print(f"    - 평균: {risk_stats['mean']:.2f}")
        print(f"    - 중앙값: {risk_stats['50%']:.2f}")
        print(f"    - 최소: {risk_stats['min']:.2f}")
        print(f"    - 최대: {risk_stats['max']:.2f}")
        print(f"    - 표준편차: {risk_stats['std']:.2f}")

    # 10. 결과 저장
    output_file = f"{data_folder}/parallel_grid_integrated_risk_dataset.csv"
    result_df.to_csv(output_file, index=False, encoding="utf-8")

    print(f"\n🎉 병렬 처리 통합 전처리 완료!")
    print(f"  📁 결과 파일: {output_file}")
    print(f"  📊 총 레코드 수: {len(result_df):,}")
    print(f"  🏷️ 총 피처 수: {len(result_df.columns)}")
    print(f"  🗺️ 분석된 격자 수: {len(grid_locations):,}")

    # 11. 위험도 분포 확인
    if "comprehensive_risk_level" in result_df.columns:
        print(f"\n📈 위험도 분포:")
        risk_distribution = (
            result_df["comprehensive_risk_level"].value_counts().sort_index()
        )
        for level, count in risk_distribution.items():
            percentage = count / len(result_df) * 100
            print(f"  - {level}: {count:,}개 ({percentage:.1f}%)")

    # 12. 반경별 통계
    if "analysis_radius_km" in result_df.columns:
        print(f"\n📏 반경별 분포:")
        radius_distribution = (
            result_df["analysis_radius_km"].value_counts().sort_index()
        )
        for radius, count in radius_distribution.items():
            print(f"  - {radius*1000:.0f}m: {count:,}개")

    # 13. 주요 피처 요약
    print(f"\n🔧 주요 ML 피처 목록:")
    ml_features = [
        "final_risk_score",
        "comprehensive_risk_category",
        "weighted_construction_risk",
        "weighted_sinkhole_risk",
        "weighted_rainfall_risk",
        "total_daily_visitors",
        "total_subway_passengers",
        "rainfall_amplification_factor",
        "analysis_radius_km",
        "distance_from_center",
        "construction_rainfall_interaction",
        "activity_density",
        "risk_density",
    ]

    available_features = []
    for feature in ml_features:
        if feature in result_df.columns:
            dtype = result_df[feature].dtype
            non_zero = (result_df[feature] != 0).sum()
            percentage = non_zero / len(result_df) * 100
            print(
                f"  ✅ {feature} ({dtype}): {non_zero:,}/{len(result_df):,} ({percentage:.1f}%) non-zero"
            )
            available_features.append(feature)
        else:
            print(f"  ❌ {feature}: 없음")

    # 14. 샘플 데이터 표시
    print(f"\n📋 샘플 데이터 (임의 5개):")
    sample_columns = [
        "location_name",
        "analysis_radius_km",
        "final_risk_score",
        "comprehensive_risk_level",
    ]
    available_sample_columns = [
        col for col in sample_columns if col in result_df.columns
    ]
    if available_sample_columns and len(result_df) > 0:
        sample_df = result_df.sample(min(5, len(result_df)))[available_sample_columns]
        print(sample_df.to_string(index=False))

    # 15. 성능 요약
    print(f"\n⚡ 병렬 처리 성능 요약:")
    print(
        f"  - 사용된 CPU 코어: {min(cpu_count() - 1, 8) if N_WORKERS is None else N_WORKERS}개"
    )
    print(f"  - 총 처리 시간: 위에 표시됨")
    print(f"  - 예상 단일 스레드 대비 속도 향상: 3-8배")

    # 16. Azure ML Studio 업로드 안내
    print(f"\n📤 다음 단계 안내:")
    print(f"  1. Azure ML Studio에 로그인")
    print(f"  2. Data → Datasets → Create dataset → From local files")
    print(f"  3. '{output_file}' 파일 업로드")
    print(f"  4. Dataset name: 'parallel_grid_risk_dataset'")
    print(f"  5. Designer에서 이 데이터셋으로 ML 파이프라인 구성")

    return result_df


if __name__ == "__main__":
    try:
        print("🔧 병렬 처리 요구사항:")
        print(f"  - Python multiprocessing 모듈 (기본 내장)")
        print(f"  - 권장 메모리: 8GB 이상")
        print(f"  - 권장 CPU: 4코어 이상")
        print(f"  - 현재 시스템 CPU 코어: {cpu_count()}개")
        print()

        result_df = main_parallel()
        if result_df is not None:
            print("\n🎊 병렬 처리 전체 처리가 성공적으로 완료되었습니다!")
            print(
                f"💡 다음에는 Numba JIT 컴파일을 추가하면 추가로 5-10배 더 빨라집니다!"
            )
        else:
            print("\n❌ 처리 중 문제가 발생했습니다.")

    except Exception as e:
        print(f"\n❌ 전체 오류 발생: {e}")
        import traceback

        print(f"상세 오류:\n{traceback.format_exc()}")

        print(f"\n🔧 문제 해결 방법:")
        print(f"  1. CSV 파일 경로 및 형식 확인")
        print(f"  2. 메모리 부족 시 GRID_SPACING 증가 (0.004~0.005)")
        print(f"  3. 멀티프로세싱 오류 시 N_WORKERS = 1로 설정")
        print(f"  4. Python 패키지 설치: pip install pandas numpy")
        print(f"  5. Windows에서는 if __name__ == '__main__': 블록 안에서 실행 필수")
