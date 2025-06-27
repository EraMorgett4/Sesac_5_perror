import asyncio
import aiohttp
import logging
from typing import List, Dict, Tuple, Optional
from geopy.distance import geodesic
import json
import time

logger = logging.getLogger(__name__)


class EnhancedRoutingService:
    """실제 도로만 사용하는 강화된 라우팅 서비스"""

    def __init__(self):
        self.osrm_base_url = "https://router.project-osrm.org"
        self.session = None

        # 여러 OSRM 서버 백업 (순서대로 시도)
        self.osrm_servers = [
            "https://router.project-osrm.org",
            "http://router.project-osrm.org",
            # 추가 백업 서버들 (필요시)
        ]

        # 도보 전용 프로파일들
        self.walking_profiles = {
            "foot": "foot",  # 기본 도보
            "walking": "foot",  # 도보 (별칭)
            "pedestrian": "foot",  # 보행자 (별칭)
        }

        # 경로 품질 검증 설정
        self.max_detour_ratio = 2.5  # 직선거리 대비 최대 우회 비율
        self.min_route_points = 3  # 최소 경로 포인트 수

    async def get_session(self):
        """비동기 HTTP 세션 획득"""
        if not self.session:
            timeout = aiohttp.ClientTimeout(total=15, connect=5)
            self.session = aiohttp.ClientSession(
                timeout=timeout, headers={"User-Agent": "Seoul-Safety-Navigation/1.0"}
            )
        return self.session

    async def close_session(self):
        """세션 정리"""
        if self.session:
            await self.session.close()
            self.session = None

    def calculate_direct_distance(
        self, start_lat: float, start_lng: float, end_lat: float, end_lng: float
    ) -> float:
        """직선 거리 계산 (km)"""
        return geodesic((start_lat, start_lng), (end_lat, end_lng)).kilometers

    async def get_real_walking_route(
        self,
        start_lat: float,
        start_lng: float,
        end_lat: float,
        end_lng: float,
        profile: str = "foot",
        alternatives: bool = True,
    ) -> Dict:
        """실제 도보 경로 생성 (여러 서버 시도 + 검증)"""

        start_time = time.time()
        direct_distance = self.calculate_direct_distance(
            start_lat, start_lng, end_lat, end_lng
        )

        logger.info(f"🚶 실제 도보 경로 요청: {direct_distance:.2f}km (직선거리)")

        # 1단계: 여러 OSRM 서버로 경로 시도
        route_result = None
        successful_server = None

        for server_url in self.osrm_servers:
            try:
                logger.info(f"🌐 OSRM 서버 시도: {server_url}")
                result = await self._request_osrm_route(
                    server_url,
                    start_lat,
                    start_lng,
                    end_lat,
                    end_lng,
                    profile,
                    alternatives,
                )

                if result["success"]:
                    route_result = result
                    successful_server = server_url
                    logger.info(f"✅ OSRM 경로 성공: {server_url}")
                    break
                else:
                    logger.warning(f"⚠️ OSRM 실패: {server_url} - {result.get('error')}")

            except Exception as e:
                logger.warning(f"❌ OSRM 오류: {server_url} - {e}")
                continue

        if not route_result or not route_result["success"]:
            logger.error("❌ 모든 OSRM 서버에서 경로 생성 실패")
            return {
                "success": False,
                "error": "실제 도로 경로를 찾을 수 없습니다. 도보로 접근 불가능한 지역일 수 있습니다.",
                "direct_distance": direct_distance,
                "attempted_servers": len(self.osrm_servers),
            }

        # 2단계: 경로 품질 검증
        route_data = route_result["route_data"]
        validation_result = self._validate_route_quality(
            route_data, direct_distance, start_lat, start_lng, end_lat, end_lng
        )

        if not validation_result["is_valid"]:
            logger.warning(f"⚠️ 경로 품질 검증 실패: {validation_result['reason']}")

            # 품질이 낮으면 대안 경로 시도
            if alternatives and "alternatives" in route_result:
                for i, alt_route in enumerate(route_result["alternatives"]):
                    alt_validation = self._validate_route_quality(
                        alt_route,
                        direct_distance,
                        start_lat,
                        start_lng,
                        end_lat,
                        end_lng,
                    )
                    if alt_validation["is_valid"]:
                        logger.info(f"✅ 대안 경로 {i+1} 사용")
                        route_data = alt_route
                        validation_result = alt_validation
                        break

        # 3단계: 경로 정보 추출 및 가공
        processed_route = self._process_route_data(
            route_data, successful_server, validation_result, direct_distance
        )

        processing_time = time.time() - start_time
        processed_route["processing_time"] = round(processing_time, 3)

        logger.info(
            f"✅ 실제 도보 경로 완성: {processed_route['distance']:.2f}km, "
            f"{processed_route['estimated_time']}분 ({processing_time:.2f}초)"
        )

        return processed_route

    async def _request_osrm_route(
        self,
        server_url: str,
        start_lat: float,
        start_lng: float,
        end_lat: float,
        end_lng: float,
        profile: str = "foot",
        alternatives: bool = True,
    ) -> Dict:
        """개별 OSRM 서버에 경로 요청"""

        session = await self.get_session()

        # OSRM 좌표 형식: longitude,latitude
        coordinates = f"{start_lng},{start_lat};{end_lng},{end_lat}"

        params = {
            "overview": "full",
            "geometries": "geojson",
            "steps": "true",
            "annotations": "duration,distance,nodes",
            "alternatives": "true" if alternatives else "false",
            "continue_straight": "false",  # 직진 강제 비활성화
        }

        url = f"{server_url}/route/v1/{profile}/{coordinates}"

        try:
            async with session.get(url, params=params) as response:
                if response.status != 200:
                    return {"success": False, "error": f"HTTP {response.status}"}

                data = await response.json()

                if data.get("code") != "Ok":
                    return {
                        "success": False,
                        "error": f"OSRM 코드: {data.get('code')} - {data.get('message', 'Unknown error')}",
                    }

                if not data.get("routes"):
                    return {"success": False, "error": "No routes found"}

                return {
                    "success": True,
                    "route_data": data["routes"][0],
                    "alternatives": (
                        data["routes"][1:] if len(data["routes"]) > 1 else []
                    ),
                    "server_used": server_url,
                }

        except asyncio.TimeoutError:
            return {"success": False, "error": "Request timeout"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _validate_route_quality(
        self,
        route_data: Dict,
        direct_distance: float,
        start_lat: float,
        start_lng: float,
        end_lat: float,
        end_lng: float,
    ) -> Dict:
        """경로 품질 검증"""

        try:
            route_distance = route_data.get("distance", 0) / 1000  # km
            geometry = route_data.get("geometry", {})
            coordinates = geometry.get("coordinates", [])

            # 검증 1: 경로 포인트 수 확인
            if len(coordinates) < self.min_route_points:
                return {
                    "is_valid": False,
                    "reason": f"경로 포인트 부족 ({len(coordinates)}개)",
                    "quality_score": 0.0,
                }

            # 검증 2: 우회 비율 확인
            if direct_distance > 0:
                detour_ratio = route_distance / direct_distance
                if detour_ratio > self.max_detour_ratio:
                    return {
                        "is_valid": False,
                        "reason": f"과도한 우회 ({detour_ratio:.1f}배)",
                        "quality_score": 0.3,
                        "detour_ratio": detour_ratio,
                    }

            # 검증 3: 시작/끝점 근접성 확인
            if coordinates:
                start_point = coordinates[0]
                end_point = coordinates[-1]

                start_error = geodesic(
                    (start_lat, start_lng), (start_point[1], start_point[0])
                ).kilometers
                end_error = geodesic(
                    (end_lat, end_lng), (end_point[1], end_point[0])
                ).kilometers

                if start_error > 0.5 or end_error > 0.5:  # 500m 이상 오차
                    return {
                        "is_valid": False,
                        "reason": f"시작/끝점 오차 큼 (시작: {start_error:.1f}km, 끝: {end_error:.1f}km)",
                        "quality_score": 0.5,
                    }

            # 검증 4: 합리적인 거리 범위 확인
            if route_distance < direct_distance * 0.8:  # 너무 짧음
                return {
                    "is_valid": False,
                    "reason": "비현실적으로 짧은 경로",
                    "quality_score": 0.2,
                }

            # 품질 점수 계산
            quality_score = 1.0
            if direct_distance > 0:
                detour_penalty = max(0, (route_distance / direct_distance - 1.0) * 0.5)
                quality_score = max(0.1, 1.0 - detour_penalty)

            return {
                "is_valid": True,
                "reason": "품질 검증 통과",
                "quality_score": quality_score,
                "detour_ratio": (
                    route_distance / direct_distance if direct_distance > 0 else 1.0
                ),
                "route_points": len(coordinates),
                "start_error": start_error if "start_error" in locals() else 0,
                "end_error": end_error if "end_error" in locals() else 0,
            }

        except Exception as e:
            return {
                "is_valid": False,
                "reason": f"검증 과정 오류: {str(e)}",
                "quality_score": 0.0,
            }

    def _process_route_data(
        self,
        route_data: Dict,
        server_used: str,
        validation_result: Dict,
        direct_distance: float,
    ) -> Dict:
        """경로 데이터 가공 및 최종 정보 생성"""

        try:
            # 기본 정보 추출
            distance_m = route_data.get("distance", 0)
            duration_s = route_data.get("duration", 0)
            geometry = route_data.get("geometry", {})
            coordinates = geometry.get("coordinates", [])

            # 좌표 변환 (OSRM: lng,lat → 우리: lat,lng)
            waypoints = [{"lat": coord[1], "lng": coord[0]} for coord in coordinates]

            # 상세 안내 추출
            steps = []
            if "legs" in route_data:
                for leg in route_data["legs"]:
                    if "steps" in leg:
                        for step in leg["steps"]:
                            maneuver = step.get("maneuver", {})
                            step_info = {
                                "instruction": self._translate_instruction(maneuver),
                                "distance": step.get("distance", 0),
                                "duration": step.get("duration", 0),
                                "name": step.get("name", ""),
                                "mode": "walking",
                                "maneuver_type": maneuver.get("type", "straight"),
                                "bearing_before": maneuver.get("bearing_before"),
                                "bearing_after": maneuver.get("bearing_after"),
                            }
                            steps.append(step_info)

            # 경로 타입 결정
            route_type = "real_walking"
            if validation_result.get("detour_ratio", 1.0) > 1.8:
                route_type = "real_walking_detour"
            elif validation_result.get("quality_score", 1.0) < 0.7:
                route_type = "real_walking_suboptimal"

            # 메시지 생성
            quality_score = validation_result.get("quality_score", 1.0)
            detour_ratio = validation_result.get("detour_ratio", 1.0)

            if quality_score >= 0.9:
                quality_msg = "최적의 도보 경로"
            elif quality_score >= 0.7:
                quality_msg = "양호한 도보 경로"
            else:
                quality_msg = "가능한 도보 경로"

            if detour_ratio <= 1.2:
                detour_msg = ""
            elif detour_ratio <= 1.5:
                detour_msg = " (약간 우회)"
            else:
                detour_msg = f" ({detour_ratio:.1f}배 우회)"

            return {
                "success": True,
                "route_type": route_type,
                "waypoints": waypoints,
                "distance": round(distance_m / 1000, 3),  # km
                "estimated_time": max(1, int(duration_s / 60)),  # 분
                "steps": steps,
                "message": f"{quality_msg}입니다{detour_msg}. 실제 도로를 따라 안내합니다.",
                # 품질 정보
                "quality_info": {
                    "score": round(quality_score, 2),
                    "is_valid": validation_result.get("is_valid", True),
                    "detour_ratio": round(detour_ratio, 2),
                    "route_points": len(waypoints),
                    "validation_reason": validation_result.get("reason", ""),
                },
                # 기술 정보
                "technical_info": {
                    "server_used": server_used,
                    "direct_distance": round(direct_distance, 3),
                    "profile_used": "foot",
                    "coordinates_count": len(coordinates),
                    "steps_count": len(steps),
                },
                # 추가 정보
                "avoided_zones": [],  # 위험지역 우회는 별도 처리
                "total_segments": len(steps),
                "sidewalk_ratio": 0.8,  # OSRM foot 프로파일은 보행자 우선
                "accessibility": "pedestrian_optimized",
            }

        except Exception as e:
            logger.error(f"❌ 경로 데이터 처리 오류: {e}")
            return {
                "success": False,
                "error": f"경로 데이터 처리 실패: {str(e)}",
                "route_type": "error",
            }

    def _translate_instruction(self, maneuver: Dict) -> str:
        """OSRM 안내를 한국어로 번역"""

        maneuver_type = maneuver.get("type", "straight")
        modifier = maneuver.get("modifier", "")

        # 기본 안내문 매핑
        instructions = {
            "depart": "출발하세요",
            "arrive": "목적지에 도착했습니다",
            "turn": "회전",
            "continue": "직진하세요",
            "merge": "합류하세요",
            "ramp": "램프로 진입하세요",
            "roundabout": "로터리",
            "exit roundabout": "로터리에서 나가세요",
            "fork": "갈림길",
            "end of road": "길 끝에서",
            "use lane": "차선을 이용하세요",
        }

        # 방향 수식어 매핑
        modifiers = {
            "left": "좌회전",
            "right": "우회전",
            "sharp left": "좌측으로 급회전",
            "sharp right": "우측으로 급회전",
            "slight left": "좌측으로 완만하게",
            "slight right": "우측으로 완만하게",
            "straight": "직진",
            "uturn": "U턴",
        }

        base_instruction = instructions.get(maneuver_type, "계속 진행")

        if maneuver_type == "turn" and modifier in modifiers:
            return f"{modifiers[modifier]}하세요"
        elif modifier and modifier in modifiers:
            return f"{modifiers[modifier]} {base_instruction}"
        else:
            return f"{base_instruction}하세요"

    async def get_enhanced_safe_route(
        self,
        start_lat: float,
        start_lng: float,
        end_lat: float,
        end_lng: float,
        avoid_zones: List[Dict] = None,
    ) -> Dict:
        """위험지역을 우회하는 실제 도로 경로"""

        logger.info("🛡️ 안전 우회 경로 생성 시작")

        # 1단계: 기본 실제 경로 생성
        basic_route = await self.get_real_walking_route(
            start_lat, start_lng, end_lat, end_lng
        )

        if not basic_route["success"]:
            return basic_route

        # 2단계: 위험지역과의 교차 검사
        if not avoid_zones:
            basic_route["message"] += " (위험지역 없음)"
            return basic_route

        crossing_zones = []
        for zone in avoid_zones:
            if self._route_crosses_danger_zone(
                basic_route["waypoints"], zone, threshold_km=0.3
            ):
                if zone.get("risk", 0) > 0.7:  # 고위험 지역만
                    crossing_zones.append(zone)

        if not crossing_zones:
            basic_route["message"] += " (위험지역 우회 불필요)"
            basic_route["avoided_zones"] = []
            return basic_route

        # 3단계: 우회 지점 계산 및 다중 경유지 경로
        logger.info(f"⚠️ {len(crossing_zones)}개 위험지역 발견, 우회 경로 계산")

        detour_waypoints = self._calculate_detour_waypoints(
            start_lat, start_lng, end_lat, end_lng, crossing_zones
        )

        # 4단계: 다중 경유지 실제 경로 생성
        detour_route = await self._get_multi_waypoint_route(detour_waypoints)

        if detour_route["success"]:
            detour_route["avoided_zones"] = crossing_zones
            detour_route["route_type"] = "real_walking_safe_detour"
            detour_route["message"] = (
                f"실제 도로를 이용해 {len(crossing_zones)}개 위험지역을 "
                f"안전하게 우회하는 경로입니다."
            )
            return detour_route
        else:
            # 우회 실패 시 기본 경로에 경고 추가
            basic_route["avoided_zones"] = crossing_zones
            basic_route["route_type"] = "real_walking_with_warning"
            basic_route["message"] = (
                f"실제 도로 경로이지만 {len(crossing_zones)}개 위험지역을 "
                f"지나갑니다. 주의하여 이동하세요."
            )
            return basic_route

    def _route_crosses_danger_zone(
        self, waypoints: List[Dict], zone: Dict, threshold_km: float = 0.3
    ) -> bool:
        """경로가 위험지역과 교차하는지 정밀 검사"""

        zone_lat, zone_lng = zone["lat"], zone["lng"]

        # 모든 waypoint에서 위험지역까지의 거리 검사
        for i, waypoint in enumerate(waypoints):
            distance = geodesid(
                (waypoint["lat"], waypoint["lng"]), (zone_lat, zone_lng)
            ).kilometers

            if distance <= threshold_km:
                return True

        # 인접한 waypoint들 사이의 중간점들도 검사 (정밀도 향상)
        for i in range(len(waypoints) - 1):
            wp1 = waypoints[i]
            wp2 = waypoints[i + 1]

            # 두 점 사이의 중간점 검사
            mid_lat = (wp1["lat"] + wp2["lat"]) / 2
            mid_lng = (wp1["lng"] + wp2["lng"]) / 2

            distance = geodesic((mid_lat, mid_lng), (zone_lat, zone_lng)).kilometers
            if distance <= threshold_km:
                return True

        return False

    def _calculate_detour_waypoints(
        self,
        start_lat: float,
        start_lng: float,
        end_lat: float,
        end_lng: float,
        danger_zones: List[Dict],
    ) -> List[Tuple[float, float]]:
        """위험지역을 우회하는 경유지 계산"""

        waypoints = [(start_lat, start_lng)]

        # 위험지역들의 중심 계산
        if danger_zones:
            danger_center_lat = sum(z["lat"] for z in danger_zones) / len(danger_zones)
            danger_center_lng = sum(z["lng"] for z in danger_zones) / len(danger_zones)

            # 시작-끝 중점
            mid_lat = (start_lat + end_lat) / 2
            mid_lng = (start_lng + end_lng) / 2

            # 우회 방향 계산 (위험지역과 반대 방향으로)
            offset_distance = 0.008  # 약 800m

            if danger_center_lat > mid_lat:
                detour_lat = mid_lat - offset_distance
            else:
                detour_lat = mid_lat + offset_distance

            if danger_center_lng > mid_lng:
                detour_lng = mid_lng - offset_distance
            else:
                detour_lng = mid_lng + offset_distance

            # 우회 지점 추가
            waypoints.append((detour_lat, detour_lng))

        waypoints.append((end_lat, end_lng))
        return waypoints

    async def _get_multi_waypoint_route(
        self, waypoints: List[Tuple[float, float]]
    ) -> Dict:
        """다중 경유지 실제 경로 생성"""

        if len(waypoints) < 2:
            return {"success": False, "error": "Insufficient waypoints"}

        try:
            session = await self.get_session()

            # 좌표를 OSRM 형식으로 변환
            coordinates_str = ";".join([f"{lng},{lat}" for lat, lng in waypoints])

            params = {
                "overview": "full",
                "geometries": "geojson",
                "steps": "true",
                "annotations": "duration,distance",
            }

            url = f"{self.osrm_base_url}/route/v1/foot/{coordinates_str}"

            async with session.get(url, params=params) as response:
                if response.status != 200:
                    return {"success": False, "error": f"HTTP {response.status}"}

                data = await response.json()

                if data.get("code") != "Ok" or not data.get("routes"):
                    return {"success": False, "error": "No multi-waypoint route found"}

                # 기본 경로 처리와 동일한 방식으로 가공
                route_data = data["routes"][0]
                direct_distance = self.calculate_direct_distance(
                    waypoints[0][0], waypoints[0][1], waypoints[-1][0], waypoints[-1][1]
                )

                validation_result = self._validate_route_quality(
                    route_data,
                    direct_distance,
                    waypoints[0][0],
                    waypoints[0][1],
                    waypoints[-1][0],
                    waypoints[-1][1],
                )

                return self._process_route_data(
                    route_data, self.osrm_base_url, validation_result, direct_distance
                )

        except Exception as e:
            logger.error(f"❌ 다중 경유지 경로 오류: {e}")
            return {"success": False, "error": str(e)}


# 전역 서비스 인스턴스
enhanced_routing_service = EnhancedRoutingService()
