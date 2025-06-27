# backend/exercise_route_service.py - 최종 완료 버전

import math
import random
import asyncio
import aiohttp
from typing import List, Dict, Tuple, Optional
from geopy.distance import geodesic
import logging

logger = logging.getLogger(__name__)


class ExerciseRouteService:
    """OSRM API를 활용한 만보기 운동 경로 생성 서비스"""

    def __init__(self, osrm_base_url: str = "https://router.project-osrm.org"):
        self.osrm_base_url = osrm_base_url
        self.session = None
        self.steps_per_kilometer = 1250
        self.default_target_steps = 10000
        self.walking_speed_kmh = 4.0

        # 서울 추천 산책 장소 리스트 대폭 확장 (40+ 곳)
        self.safe_areas = [
            # 공원 (Parks)
            {
                "name": "올림픽공원",
                "center": (37.5213, 127.1218),
                "type": "park",
                "type_description": "대규모 공원",
                "recommended_activities": ["산책", "조깅", "자전거"],
            },
            {
                "name": "서울숲",
                "center": (37.5447, 127.0374),
                "type": "park",
                "type_description": "도심 속 자연",
                "recommended_activities": ["가족나들이", "피크닉", "생태체험"],
            },
            {
                "name": "보라매공원",
                "center": (37.4915, 126.9199),
                "type": "park",
                "type_description": "지역 공원",
                "recommended_activities": ["산책", "운동기구", "반려견놀이터"],
            },
            {
                "name": "북서울꿈의숲",
                "center": (37.6214, 127.0601),
                "type": "park",
                "type_description": "전망 좋은 공원",
                "recommended_activities": ["전망대", "미술관", "호수 산책"],
            },
            {
                "name": "월드컵공원 (하늘공원)",
                "center": (37.5709, 126.8828),
                "type": "park",
                "type_description": "억새, 야경",
                "recommended_activities": ["억새축제", "메타세콰이어길", "야경 감상"],
            },
            {
                "name": "선유도공원",
                "center": (37.5434, 126.8973),
                "type": "park",
                "type_description": "생태 공원",
                "recommended_activities": ["사진촬영", "식물원", "데이트코스"],
            },
            {
                "name": "어린이대공원",
                "center": (37.5479, 127.0810),
                "type": "park",
                "type_description": "가족 공원",
                "recommended_activities": ["동물원", "식물원", "놀이동산"],
            },
            {
                "name": "서서울호수공원",
                "center": (37.5210, 126.8370),
                "type": "park",
                "type_description": "소리분수 공원",
                "recommended_activities": ["호수 산책", "소리분수", "재생건축"],
            },
            {
                "name": "푸른수목원",
                "center": (37.4836, 126.8155),
                "type": "park",
                "type_description": "생태 수목원",
                "recommended_activities": ["항동철길", "온실", "다양한 식물"],
            },
            {
                "name": "율현공원",
                "center": (37.4760, 127.1120),
                "type": "park",
                "type_description": "조용한 공원",
                "recommended_activities": ["산책", "조깅", "토끼 관찰"],
            },
            # 강변 (Riverfront)
            {
                "name": "여의도 한강공원",
                "center": (37.5284, 126.9338),
                "type": "river",
                "type_description": "도심 강변",
                "recommended_activities": ["자전거", "피크닉", "유람선"],
            },
            {
                "name": "반포 한강공원",
                "center": (37.5123, 127.0065),
                "type": "river",
                "type_description": "야경, 분수",
                "recommended_activities": [
                    "달빛무지개분수",
                    "세빛섬",
                    "밤도깨비야시장",
                ],
            },
            {
                "name": "뚝섬 한강공원",
                "center": (37.5309, 127.0664),
                "type": "river",
                "type_description": "수상레저",
                "recommended_activities": ["윈드서핑", "오리배", "자벌레"],
            },
            {
                "name": "잠실 한강공원",
                "center": (37.5180, 127.0818),
                "type": "river",
                "type_description": "스포츠 공원",
                "recommended_activities": ["자전거", "인라인", "체육시설"],
            },
            {
                "name": "난지 한강공원",
                "center": (37.5714, 126.8986),
                "type": "river",
                "type_description": "캠핑, 생태",
                "recommended_activities": ["캠핑장", "생태습지원", "자전거"],
            },
            # 산 (Mountains & Trails)
            {
                "name": "남산공원 (북측순환로)",
                "center": (37.5534, 126.9823),
                "type": "mountain",
                "type_description": "도심 속 산",
                "recommended_activities": ["남산타워", "케이블카", "산책"],
            },
            {
                "name": "인왕산 자락길",
                "center": (37.5815, 126.9620),
                "type": "mountain",
                "type_description": "성곽길, 야경",
                "recommended_activities": [
                    "성곽길 트래킹",
                    "야경 감상",
                    "더숲초소책방",
                ],
            },
            {
                "name": "안산 자락길",
                "center": (37.5772, 126.9488),
                "type": "mountain",
                "type_description": "무장애 숲길",
                "recommended_activities": ["메타세콰이어길", "휠체어 산책", "가족산책"],
            },
            {
                "name": "관악산 둘레길",
                "center": (37.4658, 126.9491),
                "type": "mountain",
                "type_description": "계곡, 사찰",
                "recommended_activities": ["계곡 트래킹", "서울대입구", "사찰 방문"],
            },
            {
                "name": "북한산 둘레길 (우이령길)",
                "center": (37.6630, 127.0110),
                "type": "mountain",
                "type_description": "국립공원",
                "recommended_activities": ["등산", "트래킹", "사찰 방문"],
            },
            {
                "name": "아차산 생태공원",
                "center": (37.5539, 127.0988),
                "type": "mountain",
                "type_description": "고구려 유적",
                "recommended_activities": ["해맞이", "고구려정", "가벼운 등산"],
            },
            # 하천 및 숲길 (Streams & Forest Trails)
            {
                "name": "양재천 시민의숲",
                "center": (37.4704, 127.0368),
                "type": "stream",
                "type_description": "시민의 숲",
                "recommended_activities": ["메타세콰이어길", "단풍", "자전거"],
            },
            {
                "name": "청계천",
                "center": (37.5692, 127.0056),
                "type": "stream",
                "type_description": "도심 하천",
                "recommended_activities": ["밤 산책", "데이트", "등불축제"],
            },
            {
                "name": "경의선 숲길 (연남동 구간)",
                "center": (37.5606, 126.9255),
                "type": "trail",
                "type_description": "연트럴파크",
                "recommended_activities": ["카페거리", "피크닉", "반려견 산책"],
            },
            {
                "name": "성북천",
                "center": (37.5820, 127.0180),
                "type": "stream",
                "type_description": "한성대입구역",
                "recommended_activities": ["벚꽃길", "동네 산책", "조깅"],
            },
            {
                "name": "불광천",
                "center": (37.5880, 126.9130),
                "type": "stream",
                "type_description": "은평구 하천",
                "recommended_activities": ["벚꽃길", "자전거", "운동"],
            },
            {
                "name": "우이천",
                "center": (37.6380, 127.0300),
                "type": "stream",
                "type_description": "강북/도봉",
                "recommended_activities": ["벚꽃길", "산책", "조깅"],
            },
            {
                "name": "경춘선 숲길",
                "center": (37.6220, 127.0850),
                "type": "trail",
                "type_description": "폐철길 공원",
                "recommended_activities": ["기차마을", "자전거", "레트로 감성"],
            },
            {
                "name": "관악산 공원",
                "center": (37.4769, 126.9534),
                "type": "park",
                "type_description": "서울대 인근",
                "recommended_activities": ["등산", "계곡", "산책"],
            },
            # 역사 및 문화 (History & Culture)
            {
                "name": "덕수궁 돌담길 (정동길)",
                "center": (37.5659, 126.9749),
                "type": "history",
                "type_description": "역사 문화길",
                "recommended_activities": ["고궁 산책", "미술관", "데이트"],
            },
            {
                "name": "한양도성길 (낙산공원 구간)",
                "center": (37.5788, 127.0072),
                "type": "history",
                "type_description": "성곽 야경",
                "recommended_activities": ["야경 감상", "이화벽화마을", "성곽길 걷기"],
            },
            {
                "name": "석촌호수 공원",
                "center": (37.5093, 127.1048),
                "type": "park",
                "type_description": "호수 공원",
                "recommended_activities": ["롯데월드타워", "벚꽃축제", "조깅"],
            },
            {
                "name": "몽마르뜨공원",
                "center": (37.5003, 127.0016),
                "type": "park",
                "type_description": "서래마을 공원",
                "recommended_activities": ["누에다리", "토끼", "조용한 산책"],
            },
            {
                "name": "삼청동길",
                "center": (37.5824, 126.9816),
                "type": "history",
                "type_description": "북촌, 갤러리",
                "recommended_activities": ["갤러리 투어", "카페", "한옥마을"],
            },
            {
                "name": "창경궁",
                "center": (37.5787, 126.9953),
                "type": "history",
                "type_description": "고궁 산책",
                "recommended_activities": ["고궁 산책", "온실", "야간개장"],
            },
            {
                "name": "국립현충원",
                "center": (37.5029, 126.9769),
                "type": "park",
                "type_description": "추모, 벚꽃",
                "recommended_activities": ["수양벚꽃", "산책", "추모"],
            },
            # 기타 특색있는 장소
            {
                "name": "매헌시민의숲 (양재시민의숲)",
                "center": (37.4704, 127.0368),
                "type": "park",
                "type_description": "울창한 숲",
                "recommended_activities": ["메타세콰이어길", "피크닉", "결혼식"],
            },
            {
                "name": "용산가족공원",
                "center": (37.5259, 126.9789),
                "type": "park",
                "type_description": "박물관 인근",
                "recommended_activities": ["국립중앙박물관", "호수", "넓은 잔디밭"],
            },
            {
                "name": "개운산 공원",
                "center": (37.5950, 127.0200),
                "type": "mountain",
                "type_description": "성북구 근린공원",
                "recommended_activities": ["산책", "운동시설", "어린이숲놀이터"],
            },
            {
                "name": "일자산 허브천문공원",
                "center": (37.5490, 127.1600),
                "type": "park",
                "type_description": "허브, 천문",
                "recommended_activities": ["허브향기", "천문관측", "야경"],
            },
        ]

    async def get_session(self):
        if not self.session:
            self.session = aiohttp.ClientSession()
        return self.session

    async def close_session(self):
        if self.session:
            await self.session.close()
            self.session = None

    def find_best_exercise_area(self, start_location: Dict) -> Dict:
        start_lat, start_lng = start_location["lat"], start_location["lng"]
        area_scores = []
        for area in self.safe_areas:
            area_lat, area_lng = area["center"]
            distance_to_area = geodesic(
                (start_lat, start_lng), (area_lat, area_lng)
            ).kilometers
            distance_score = max(0, 10 - distance_to_area)
            area_scores.append({"area": area, "score": distance_score})

        if not area_scores:
            return self.safe_areas[0]
        area_scores.sort(key=lambda x: x["score"], reverse=True)
        return area_scores[0]["area"]

    async def get_route_between_points(
        self, start_point: Tuple, end_point: Tuple
    ) -> Optional[Dict]:
        session = await self.get_session()
        start_lng, start_lat = start_point[1], start_point[0]
        end_lng, end_lat = end_point[1], end_point[0]

        coord_string = f"{start_lng},{start_lat};{end_lng},{end_lat}"
        params = {"overview": "full", "geometries": "geojson", "steps": "true"}
        url = f"{self.osrm_base_url}/route/v1/foot/{coord_string}"

        try:
            async with session.get(url, params=params, timeout=15) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("code") == "Ok" and data.get("routes"):
                        return data["routes"][0]
        except Exception as e:
            logger.error(f"OSRM 경로 탐색 오류: {e}")
        return None

    async def generate_exercise_route(
        self, start_location: Dict, target_steps: Optional[int] = None, **kwargs
    ) -> Dict:
        try:
            target_steps = target_steps or self.default_target_steps
            start_point = (start_location["lat"], start_location["lng"])
            destination_area = self.find_best_exercise_area(start_location)
            destination_point = destination_area["center"]
            destination_name = destination_area["name"]

            one_way_route_data = await self.get_route_between_points(
                start_point, destination_point
            )
            if not one_way_route_data:
                return {
                    "success": False,
                    "error": "추천 목적지까지의 경로를 탐색할 수 없습니다.",
                }

            one_way_distance_km = one_way_route_data.get("distance", 0) / 1000
            one_way_duration_min = one_way_route_data.get("duration", 0) / 60
            one_way_geometry = one_way_route_data["geometry"]["coordinates"]

            round_trip_distance_km = one_way_distance_km * 2
            round_trip_duration_min = one_way_duration_min * 2
            round_trip_steps = int(round_trip_distance_km * self.steps_per_kilometer)
            remaining_steps = target_steps - round_trip_steps

            if remaining_steps <= 500:
                message = f"{destination_name}까지 왕복 산책하는 것을 추천합니다. 이 경로만으로 목표 걸음 수({target_steps:,}보)를 거의 달성할 수 있습니다."
            else:
                remaining_km = round(remaining_steps / self.steps_per_kilometer, 1)
                message = f"{destination_name}까지 왕복 산책 후, 약 {remaining_steps:,}보(약 {remaining_km}km)를 추가로 걸으면 목표를 달성할 수 있습니다."

            forward_waypoints = [
                {"lat": coord[1], "lng": coord[0]} for coord in one_way_geometry
            ]
            total_waypoints = forward_waypoints + forward_waypoints[::-1][1:]

            return {
                "success": True,
                "route_type": "exercise_out_and_back_to_poi",
                "waypoints": total_waypoints,
                "distance": round(round_trip_distance_km, 2),
                "estimated_time": int(round_trip_duration_min),
                "target_steps": target_steps,
                "actual_steps": round_trip_steps,
                "steps_accuracy": (
                    round((round_trip_steps / target_steps) * 100, 1)
                    if target_steps > 0
                    else 100
                ),
                "exercise_area": {
                    "name": destination_name,
                    "center": destination_point,
                },
                "route_description": f"현재위치 ↔ {destination_name} 왕복",
                "message": message,
                "steps": one_way_route_data.get("legs", [{}])[0].get("steps", []),
            }
        except Exception as e:
            logger.error(f"운동 경로 생성 오류: {e}", exc_info=True)
            return {"success": False, "error": f"경로 생성에 실패했습니다: {e}"}


exercise_route_service = ExerciseRouteService()
