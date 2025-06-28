# location_analyzer.py
"""
위치 기반 위험도 분석 전담 모듈
integrate.py 로직 기반으로 정밀 분석 수행
"""

import datetime
import logging
import traceback
from typing import Dict, List
from math import radians, cos, sin, asin, sqrt

logger = logging.getLogger(__name__)


def calculate_distance(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """두 지점 간 거리 계산 (km)"""
    if not all([lat1, lng1, lat2, lng2]):
        return float("inf")

    R = 6371  # 지구 반지름 (km)
    lat1_rad = radians(lat1)
    lat2_rad = radians(lat2)
    delta_lat = radians(lat2 - lat1)
    delta_lng = radians(lng2 - lng1)

    a = (
        sin(delta_lat / 2) ** 2
        + cos(lat1_rad) * cos(lat2_rad) * sin(delta_lng / 2) ** 2
    )
    c = 2 * asin(sqrt(a))

    return R * c


def convert_coordinates_to_features(
    target_lat: float,
    target_lng: float,
    construction_data: List[Dict],
    risk_zones: List[Dict],
    location_name: str = "현재 위치",
    radius_km: float = 0.1,
) -> Dict:
    """
    integrate.py 로직 기반으로 좌표를 Azure ML 입력 형태로 변환
    100m(0.1km) 반경 내 실제 데이터 분석
    """
    try:
        print(f"\n📊 정밀 피처 변환 시작 (integrate.py 로직 기반):")
        print(f"  🎯 대상: {location_name}")
        print(f"  📍 좌표: ({target_lat:.6f}, {target_lng:.6f})")
        print(f"  📏 분석반경: {radius_km*1000:.0f}m")

        # =================================================================
        # 1. 공사장 위험도 분석
        # =================================================================
        print(f"  🚧 공사장 분석 중... (총 {len(construction_data)}개 데이터)")

        nearby_constructions = []
        construction_weights = []
        ongoing_count = 0

        for construction in construction_data:
            if not construction:
                continue

            distance = calculate_distance(
                target_lat,
                target_lng,
                construction.get("lat", 0),
                construction.get("lng", 0),
            )

            if distance <= radius_km:
                nearby_constructions.append(construction)

                # 거리 기반 가중치 (가까울수록 높은 가중치)
                weight = 1 / (distance + 0.01)  # 0.01 추가로 0으로 나누기 방지
                construction_weights.append(weight)

                if construction.get("status") == "진행중":
                    ongoing_count += 1

                print(
                    f"    🔍 공사장 발견: {construction.get('address', '주소없음')[:40]}..."
                )
                print(
                    f"       📏 거리: {distance*1000:.1f}m, 상태: {construction.get('status', '알수없음')}"
                )

        # 가중 평균으로 공사 위험도 계산
        if nearby_constructions and construction_weights:
            weighted_construction_risk = sum(
                construction.get("risk_level", 0.5) * weight
                for construction, weight in zip(
                    nearby_constructions, construction_weights
                )
            ) / sum(construction_weights)
        else:
            weighted_construction_risk = 0.0

        print(
            f"  ✅ 공사장 분석 완료: {len(nearby_constructions)}개 발견 (진행중: {ongoing_count}개)"
        )
        print(f"     📊 가중 위험도: {weighted_construction_risk:.3f}")

        # =================================================================
        # 2. 싱크홀 위험도 분석
        # =================================================================
        print(f"  🕳️ 싱크홀 위험지역 분석 중... (총 {len(risk_zones)}개 데이터)")

        nearby_sinkholes = []
        sinkhole_weights = []
        recent_sinkhole_count = 0

        for zone in risk_zones:
            distance = calculate_distance(
                target_lat, target_lng, zone.get("lat", 0), zone.get("lng", 0)
            )

            if distance <= radius_km:
                nearby_sinkholes.append(zone)

                # 거리 기반 가중치
                weight = 1 / (distance + 0.01)
                sinkhole_weights.append(weight)

                # 고위험 지역 카운트 (위험도 0.7 이상)
                if zone.get("risk", 0) > 0.7:
                    recent_sinkhole_count += 1

                print(f"    🔍 위험지역 발견: {zone.get('name', '이름없음')}")
                print(
                    f"       📏 거리: {distance*1000:.1f}m, 위험도: {zone.get('risk', 0):.2f}"
                )

        # 가중 평균으로 싱크홀 위험도 계산
        if nearby_sinkholes and sinkhole_weights:
            weighted_sinkhole_risk = sum(
                zone.get("risk", 0) * weight
                for zone, weight in zip(nearby_sinkholes, sinkhole_weights)
            ) / sum(sinkhole_weights)
        else:
            weighted_sinkhole_risk = 0.0

        print(
            f"  ✅ 싱크홀 분석 완료: {len(nearby_sinkholes)}개 발견 (고위험: {recent_sinkhole_count}개)"
        )
        print(f"     📊 가중 위험도: {weighted_sinkhole_risk:.3f}")

        # =================================================================
        # 3. 유동인구 추정
        # =================================================================
        estimated_visitors = _analyze_population_density(target_lat, target_lng)

        # =================================================================
        # 4. 지하철 승객 추정
        # =================================================================
        subway_analysis = _analyze_subway_density(target_lat, target_lng)

        # =================================================================
        # 5. 강수량 분석
        # =================================================================
        rainfall_analysis = _analyze_rainfall_risk(target_lat, target_lng)

        # =================================================================
        # 6. 종합 위험도 계산
        # =================================================================
        comprehensive_risk = _calculate_comprehensive_risk(
            weighted_construction_risk,
            weighted_sinkhole_risk,
            estimated_visitors,
            subway_analysis,
            rainfall_analysis,
        )

        # =================================================================
        # 7. Azure ML 입력 형태로 반환
        # =================================================================
        distance_from_center = calculate_distance(
            target_lat, target_lng, 37.5665, 126.9780
        )

        features = {
            "location_name": location_name,
            "target_lat": target_lat,
            "target_lng": target_lng,
            "analysis_radius_km": radius_km,
            # 공사장 관련
            "nearby_construction_count": len(nearby_constructions),
            "weighted_construction_risk": round(weighted_construction_risk, 3),
            "ongoing_construction_count": ongoing_count,
            # 싱크홀 관련
            "nearby_sinkhole_count": len(nearby_sinkholes),
            "weighted_sinkhole_risk": round(weighted_sinkhole_risk, 3),
            "recent_sinkhole_count": recent_sinkhole_count,
            # 유동인구 관련
            "avg_daily_visitors": round(estimated_visitors, 1),
            "total_daily_visitors": int(estimated_visitors),
            "population_density_score": round(estimated_visitors / 10000, 1),
            # 지하철 관련
            "nearby_subway_stations": subway_analysis["station_count"],
            "avg_subway_passengers": round(subway_analysis["avg_passengers"], 1),
            "total_subway_passengers": int(subway_analysis["total_passengers"]),
            "subway_congestion_risk": round(subway_analysis["congestion_risk"], 3),
            # 강수량 관련
            "avg_rainfall": round(rainfall_analysis["rainfall"], 1),
            "weighted_rainfall_risk": round(rainfall_analysis["risk"], 3),
            "rainfall_amplification_factor": round(
                rainfall_analysis["amplification"], 1
            ),
            # 종합 위험도
            "physical_risk_score": round(comprehensive_risk["physical"], 1),
            "social_risk_score": round(comprehensive_risk["social"], 1),
            "final_risk_score": round(comprehensive_risk["final_score"], 2),
            "comprehensive_risk_level": comprehensive_risk["level"],
            "comprehensive_risk_category": comprehensive_risk["category"],
            # 상호작용 피처
            "construction_rainfall_interaction": round(
                weighted_construction_risk * rainfall_analysis["risk"], 3
            ),
            "population_physical_interaction": round(
                estimated_visitors * comprehensive_risk["physical"] / 1000, 1
            ),
            "subway_population_ratio": round(
                subway_analysis["total_passengers"] / (estimated_visitors + 1), 1
            ),
            # 밀도 피처
            "risk_density": round(
                comprehensive_risk["final_score"] / (3.14159 * radius_km * radius_km), 1
            ),
            "activity_density": round(
                (estimated_visitors + subway_analysis["total_passengers"])
                / (3.14159 * radius_km * radius_km),
                1,
            ),
            # 위치 피처
            "distance_from_center": round(distance_from_center, 3),
            "total_infrastructure_risk": len(nearby_constructions)
            + len(nearby_sinkholes),
            "total_mobility_volume": int(
                estimated_visitors + subway_analysis["total_passengers"]
            ),
        }

        print(f"  ✅ 정밀 피처 변환 완료: {len(features)}개 피처 생성")
        print(f"  📊 핵심 지표 요약:")
        print(
            f"     - 반경 {radius_km*1000:.0f}m 내 공사장: {len(nearby_constructions)}개"
        )
        print(
            f"     - 반경 {radius_km*1000:.0f}m 내 위험지역: {len(nearby_sinkholes)}개"
        )
        print(f"     - 추정 일일 유동인구: {estimated_visitors:,.0f}명")
        print(f"     - 1km 내 지하철역: {subway_analysis['station_count']}개")
        print(
            f"     - 최종 위험점수: {comprehensive_risk['final_score']:.1f}/100 ({comprehensive_risk['category']})"
        )

        return features

    except Exception as e:
        print(f"❌ 정밀 피처 변환 오류: {e}")
        print(f"📄 오류 상세: {traceback.format_exc()}")
        return None


def _analyze_population_density(target_lat: float, target_lng: float) -> float:
    """유동인구 밀도 분석"""
    print(f"  👥 유동인구 분석...")

    # 서울 주요 지역별 기준 유동인구
    major_areas = [
        {"name": "강남역", "lat": 37.4979, "lng": 127.0276, "base_visitors": 150000},
        {"name": "홍대입구", "lat": 37.5572, "lng": 126.9245, "base_visitors": 120000},
        {"name": "명동", "lat": 37.5636, "lng": 126.9826, "base_visitors": 100000},
        {"name": "잠실", "lat": 37.5134, "lng": 127.1000, "base_visitors": 80000},
        {"name": "신촌", "lat": 37.5558, "lng": 126.9364, "base_visitors": 70000},
        {"name": "이태원", "lat": 37.5347, "lng": 126.9947, "base_visitors": 60000},
        {"name": "서울시청", "lat": 37.5665, "lng": 126.9780, "base_visitors": 50000},
        {"name": "종로3가", "lat": 37.5703, "lng": 126.9925, "base_visitors": 45000},
    ]

    # 가장 가까운 주요 지역 찾기
    min_distance = float("inf")
    nearest_area = None

    for area in major_areas:
        distance = calculate_distance(target_lat, target_lng, area["lat"], area["lng"])
        if distance < min_distance:
            min_distance = distance
            nearest_area = area

    # 거리에 따른 유동인구 감쇠 계산
    if nearest_area:
        if min_distance <= 1.0:
            visitor_factor = 1.0 - (min_distance * 0.6)
        else:
            visitor_factor = 0.4 * (0.5 ** (min_distance - 1))

        estimated_visitors = nearest_area["base_visitors"] * visitor_factor
        nearest_area_name = nearest_area["name"]
    else:
        estimated_visitors = 1000
        nearest_area_name = "일반지역"

    print(f"     📍 가장 가까운 주요지역: {nearest_area_name} ({min_distance:.2f}km)")
    print(f"     👥 추정 일일 유동인구: {estimated_visitors:,.0f}명")

    return estimated_visitors


def _analyze_subway_density(target_lat: float, target_lng: float) -> Dict:
    """지하철 승객 밀도 분석"""
    print(f"  🚇 지하철 승객 분석...")

    # 서울 주요 지하철역별 승객수
    major_stations = [
        {"name": "강남역", "lat": 37.4979, "lng": 127.0276, "passengers": 180000},
        {"name": "홍대입구역", "lat": 37.5572, "lng": 126.9245, "passengers": 120000},
        {"name": "잠실역", "lat": 37.5134, "lng": 127.1000, "passengers": 100000},
        {"name": "종로3가역", "lat": 37.5703, "lng": 126.9925, "passengers": 90000},
        {"name": "신촌역", "lat": 37.5558, "lng": 126.9364, "passengers": 80000},
        {"name": "서울역", "lat": 37.5547, "lng": 126.9707, "passengers": 85000},
        {"name": "을지로입구역", "lat": 37.5663, "lng": 126.9819, "passengers": 70000},
    ]

    # 반경 내 지하철역 찾기
    nearby_stations = []
    total_subway_passengers = 0

    for station in major_stations:
        distance = calculate_distance(
            target_lat, target_lng, station["lat"], station["lng"]
        )
        if distance <= 1.0:  # 1km 이내 지하철역
            influence = max(0, 1 - distance)
            weighted_passengers = station["passengers"] * influence

            nearby_stations.append(
                {
                    "name": station["name"],
                    "distance": distance,
                    "passengers": weighted_passengers,
                }
            )
            total_subway_passengers += weighted_passengers

            print(
                f"     🚇 {station['name']}: {distance*1000:.0f}m, 가중승객: {weighted_passengers:,.0f}명"
            )

    avg_subway_passengers = total_subway_passengers / max(1, len(nearby_stations))
    congestion_risk = avg_subway_passengers / 50000

    print(f"  ✅ 지하철 분석 완료: {len(nearby_stations)}개 역 발견")
    print(f"     📊 총 가중 승객수: {total_subway_passengers:,.0f}명")

    return {
        "station_count": len(nearby_stations),
        "avg_passengers": avg_subway_passengers,
        "total_passengers": total_subway_passengers,
        "congestion_risk": congestion_risk,
    }


def _analyze_rainfall_risk(target_lat: float, target_lng: float) -> Dict:
    """강수량 위험도 분석"""
    print(f"  ☔ 강수량 분석...")

    # 계절별 강수량 패턴
    current_month = datetime.datetime.now().month
    seasonal_base = {
        12: 25,
        1: 20,
        2: 30,  # 겨울
        3: 45,
        4: 65,
        5: 85,  # 봄
        6: 150,
        7: 280,
        8: 220,  # 여름 (장마철)
        9: 110,
        10: 50,
        11: 35,  # 가을
    }

    base_rainfall = seasonal_base.get(current_month, 50)

    # 한강 근처 보정
    hangang_distances = [
        calculate_distance(target_lat, target_lng, 37.5219, 126.9245),  # 여의도
        calculate_distance(target_lat, target_lng, 37.5133, 127.1000),  # 잠실
        calculate_distance(target_lat, target_lng, 37.5283, 126.8927),  # 마포
    ]
    hangang_distance = min(hangang_distances)

    if hangang_distance < 2.0:
        rainfall_factor = 1.0 + (2.0 - hangang_distance) * 0.1
    else:
        rainfall_factor = 1.0

    estimated_rainfall = base_rainfall * rainfall_factor

    # 강수량 위험도 계산
    if estimated_rainfall > 200:
        rainfall_risk = 0.9
        amplification = 1.5
    elif estimated_rainfall > 100:
        rainfall_risk = 0.6
        amplification = 1.3
    elif estimated_rainfall > 50:
        rainfall_risk = 0.3
        amplification = 1.1
    else:
        rainfall_risk = 0.1
        amplification = 1.0

    print(f"     ☔ 추정 누적강수량: {estimated_rainfall:.1f}mm (계절보정)")
    print(f"     📊 강수량 위험도: {rainfall_risk:.2f}")

    return {
        "rainfall": estimated_rainfall,
        "risk": rainfall_risk,
        "amplification": amplification,
    }


def _calculate_comprehensive_risk(
    construction_risk: float,
    sinkhole_risk: float,
    population: float,
    subway_analysis: Dict,
    rainfall_analysis: Dict,
) -> Dict:
    """종합 위험도 계산"""
    print(f"  🎯 종합 위험도 계산...")

    # 물리적 위험도
    physical_risk_base = (
        construction_risk * 0.4 + sinkhole_risk * 0.3 + rainfall_analysis["risk"] * 0.3
    )
    physical_risk = physical_risk_base * rainfall_analysis["amplification"]

    # 사회적 위험도
    population_density_score = population / 10000
    social_risk = (
        population_density_score * 0.6 + subway_analysis["congestion_risk"] * 0.4
    )

    # 최종 종합 위험도
    comprehensive_risk = physical_risk * 0.65 + social_risk * 0.35
    final_risk_score = min(100, max(0, comprehensive_risk * 30))

    # 위험도 등급 분류
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

    print(f"     ⚡ 물리적 위험도: {physical_risk:.3f}")
    print(f"     👥 사회적 위험도: {social_risk:.3f}")
    print(f"     🎯 최종 위험점수: {final_risk_score:.2f}/100")
    print(f"     🏷️ 위험등급: {risk_category} ({risk_level})")

    return {
        "physical": physical_risk,
        "social": social_risk,
        "final_score": final_risk_score,
        "level": risk_level,
        "category": risk_category,
    }
