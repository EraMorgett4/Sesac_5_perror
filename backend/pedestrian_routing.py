# real_osm_pedestrian_routing.py - 실제 OSM 데이터 활용 도보 경로 계산

import psycopg2
import networkx as nx
from sqlalchemy import create_engine, text
import math
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from geopy.distance import geodesic
import logging
import json

# 로거 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class Coordinate:
    lat: float
    lng: float
    
    def to_tuple(self) -> Tuple[float, float]:
        return (self.lat, self.lng)

class RealOSMPedestrianRouter:
    def __init__(self, database_url: str):
        """
        실제 OSM 데이터 기반 도보 경로 계산기
        """
        self.database_url = database_url
        self.engine = None
        self.graph = nx.Graph()
        self.osm_data_loaded = False
        
        try:
            self.engine = create_engine(database_url)
            logger.info("데이터베이스 연결 성공")
            self._load_real_osm_network()
        except Exception as e:
            logger.error(f"데이터베이스 연결 실패: {e}")
            self._create_fallback_network()
    
    def _load_real_osm_network(self):
        """실제 OSM 데이터에서 보행자 네트워크 구축"""
        try:
            logger.info("실제 OSM 데이터로 보행자 네트워크 구축 시작...")
            
            # 1. 보행자가 이용 가능한 모든 highway 타입 로드
            pedestrian_highways = [
                'footway', 'pedestrian', 'path', 'steps', 'cycleway',  # 보행자 전용
                'residential', 'service', 'living_street',              # 보행 가능 도로
                'tertiary', 'secondary', 'primary'                      # 주요 도로 (인도 있음)
            ]
            
            loaded_count = 0
            
            # 각 highway 타입별로 데이터 로드
            for highway_type in pedestrian_highways:
                count = self._load_highway_type(highway_type)
                loaded_count += count
                logger.info(f"{highway_type} 데이터 {count}개 로드")
            
            if loaded_count > 0:
                self.osm_data_loaded = True
                logger.info(f"실제 OSM 네트워크 로드 완료: {self.graph.number_of_nodes()}개 노드, {self.graph.number_of_edges()}개 엣지")
            else:
                logger.warning("OSM 데이터 로드 실패, 대체 네트워크 생성")
                self._create_fallback_network()
                
        except Exception as e:
            logger.error(f"OSM 네트워크 로딩 실패: {e}")
            self._create_fallback_network()
    
    def _load_highway_type(self, highway_type: str) -> int:
        """특정 highway 타입의 데이터를 그래프에 추가"""
        try:
            # highway 타입별 우선순위 및 속성 설정
            type_config = {
                'footway': {'priority': 1.0, 'speed': 4.0, 'pedestrian_only': True},
                'pedestrian': {'priority': 0.9, 'speed': 4.0, 'pedestrian_only': True},
                'path': {'priority': 1.1, 'speed': 3.5, 'pedestrian_only': True},
                'steps': {'priority': 1.5, 'speed': 2.0, 'pedestrian_only': True},
                'cycleway': {'priority': 1.2, 'speed': 4.0, 'pedestrian_only': False},
                'residential': {'priority': 1.3, 'speed': 4.0, 'pedestrian_only': False},
                'service': {'priority': 1.4, 'speed': 4.0, 'pedestrian_only': False},
                'living_street': {'priority': 1.2, 'speed': 4.0, 'pedestrian_only': False},
                'tertiary': {'priority': 1.6, 'speed': 4.0, 'pedestrian_only': False},
                'secondary': {'priority': 1.8, 'speed': 4.0, 'pedestrian_only': False},
                'primary': {'priority': 2.0, 'speed': 4.0, 'pedestrian_only': False}
            }
            
            config = type_config.get(highway_type, {'priority': 1.5, 'speed': 4.0, 'pedestrian_only': False})
            
            # 서울시 범위로 제한하여 데이터 로드 (매개변수 수정)
            query = """
            SELECT 
                osm_id,
                name,
                ST_AsGeoJSON(ST_Transform(way, 4326)) as geometry
            FROM planet_osm_line 
            WHERE highway = :highway_type
              AND way && ST_Transform(ST_MakeEnvelope(126.7, 37.3, 127.3, 37.8, 4326), 3857)
            LIMIT 10000
            """
            
            loaded_count = 0
            
            with self.engine.connect() as conn:
                result = conn.execute(text(query), {'highway_type': highway_type})
                
                for row in result:
                    try:
                        if row.geometry:
                            geom = json.loads(row.geometry)
                            if geom['type'] == 'LineString':
                                coords = geom['coordinates']
                                
                                # LineString의 각 세그먼트를 그래프에 추가
                                for i in range(len(coords) - 1):
                                    start_lat, start_lng = coords[i][1], coords[i][0]
                                    end_lat, end_lng = coords[i+1][1], coords[i+1][0]
                                    
                                    start_node = self._create_node_id(start_lat, start_lng)
                                    end_node = self._create_node_id(end_lat, end_lng)
                                    
                                    # 거리 계산
                                    distance = geodesic(
                                        (start_lat, start_lng),
                                        (end_lat, end_lng)
                                    ).meters
                                    
                                    # 너무 짧은 세그먼트는 제외
                                    if distance < 1:
                                        continue
                                    
                                    # 가중치 계산 (거리 × 우선순위)
                                    weight = distance * config['priority']
                                    
                                    # 그래프에 엣지 추가
                                    self.graph.add_edge(
                                        start_node, 
                                        end_node,
                                        weight=weight,
                                        distance=distance,
                                        highway_type=highway_type,
                                        priority=config['priority'],
                                        speed=config['speed'],
                                        pedestrian_only=config['pedestrian_only'],
                                        osm_id=row.osm_id,
                                        name=row.name
                                    )
                                    
                                    # 노드 좌표 정보 저장
                                    if start_node not in self.graph.nodes:
                                        self.graph.add_node(start_node, 
                                                          lat=start_lat, 
                                                          lng=start_lng)
                                    if end_node not in self.graph.nodes:
                                        self.graph.add_node(end_node, 
                                                          lat=end_lat, 
                                                          lng=end_lng)
                                
                                loaded_count += 1
                    
                    except Exception as e:
                        logger.warning(f"{highway_type} 데이터 처리 실패 (OSM ID: {row.osm_id}): {e}")
                        continue
            
            return loaded_count
                        
        except Exception as e:
            logger.error(f"{highway_type} 데이터 로드 실패: {e}")
            return 0
    
    def _create_fallback_network(self):
        """대체 네트워크 생성"""
        logger.info("대체 네트워크 생성 중...")
        
        # 서울시 전체를 커버하는 조밀한 격자 네트워크
        lat_min, lat_max = 37.42, 37.68
        lng_min, lng_max = 126.82, 127.18
        
        # 0.01도 간격 (약 1km)
        lat_step = 0.01
        lng_step = 0.01
        
        grid_nodes = []
        node_count = 0
        
        lat = lat_min
        while lat <= lat_max:
            lng = lng_min
            while lng <= lng_max:
                node_id = f"fallback_{node_count}"
                self.graph.add_node(node_id, lat=lat, lng=lng, type='fallback')
                grid_nodes.append((node_id, lat, lng))
                node_count += 1
                lng += lng_step
            lat += lat_step
        
        # 인접한 격자점들 연결
        for i, (node1, lat1, lng1) in enumerate(grid_nodes):
            for j, (node2, lat2, lng2) in enumerate(grid_nodes[i+1:], i+1):
                distance = geodesic((lat1, lng1), (lat2, lng2)).meters
                
                if distance <= 1500:  # 1.5km 이내만 연결
                    self.graph.add_edge(
                        node1, node2,
                        weight=distance,
                        distance=distance,
                        highway_type='fallback',
                        priority=1.0,
                        speed=4.0,
                        pedestrian_only=True
                    )
        
        logger.info(f"대체 네트워크 생성 완료: {self.graph.number_of_nodes()}개 노드, {self.graph.number_of_edges()}개 엣지")
    
    def _create_node_id(self, lat: float, lng: float, precision: int = 5) -> str:
        """좌표를 기반으로 노드 ID 생성"""
        return f"{round(lat, precision)},{round(lng, precision)}"
    
    def _find_nearest_nodes(self, target_lat: float, target_lng: float, max_distance: float = 2000) -> List[Tuple[str, float]]:
        """가장 가까운 그래프 노드들 찾기 (여러 개 반환)"""
        node_distances = []
        
        for node_id in self.graph.nodes():
            node_data = self.graph.nodes[node_id]
            if 'lat' in node_data and 'lng' in node_data:
                distance = geodesic(
                    (target_lat, target_lng),
                    (node_data['lat'], node_data['lng'])
                ).meters
                
                if distance <= max_distance:
                    node_distances.append((node_id, distance))
        
        # 거리순으로 정렬하여 가까운 노드들 반환
        node_distances.sort(key=lambda x: x[1])
        
        logger.info(f"({target_lat:.6f}, {target_lng:.6f}) 근처 {len(node_distances)}개 노드 발견 (최대 {max_distance}m)")
        
        return node_distances[:10]  # 상위 10개만 반환
    
    def calculate_pedestrian_route(
        self, 
        start_lat: float, 
        start_lng: float, 
        end_lat: float, 
        end_lng: float,
        avoid_zones: List[Dict] = None,
        wheelchair_accessible: bool = False
    ) -> Dict:
        """
        실제 OSM 데이터 기반 도보 경로 계산
        """
        try:
            logger.info(f"실제 OSM 경로 계산: ({start_lat:.6f}, {start_lng:.6f}) -> ({end_lat:.6f}, {end_lng:.6f})")
            
            # 시작점과 도착점 근처의 노드들 찾기
            start_nodes = self._find_nearest_nodes(start_lat, start_lng)
            end_nodes = self._find_nearest_nodes(end_lat, end_lng)
            
            if not start_nodes or not end_nodes:
                logger.warning("가까운 노드를 찾을 수 없음")
                return self._create_direct_route(start_lat, start_lng, end_lat, end_lng, 
                                               "근처에 도로 데이터를 찾을 수 없어 직선 경로를 제공합니다.")
            
            # 여러 시작점-도착점 조합으로 경로 시도
            best_route = None
            best_distance = float('inf')
            
            for start_node, start_dist in start_nodes[:3]:  # 상위 3개 시작점
                for end_node, end_dist in end_nodes[:3]:    # 상위 3개 도착점
                    try:
                        # 최단 경로 계산
                        path = nx.shortest_path(self.graph, start_node, end_node, weight='weight')
                        
                        # 경로 거리 계산
                        route_distance = self._calculate_path_distance(path)
                        
                        # 더 좋은 경로인지 확인
                        if route_distance < best_distance:
                            best_distance = route_distance
                            best_route = (path, start_node, end_node, start_dist, end_dist)
                            
                    except nx.NetworkXNoPath:
                        continue
            
            if best_route:
                path, start_node, end_node, start_dist, end_dist = best_route
                logger.info(f"경로 발견: {len(path)}개 노드, 총 거리 {best_distance:.0f}m")
                
                # 경로 상세 정보 생성
                route_info = self._create_route_info(path, start_lat, start_lng, end_lat, end_lng,
                                                   start_dist, end_dist)
                return route_info
            else:
                logger.warning("네트워크에서 경로를 찾을 수 없음")
                return self._create_direct_route(start_lat, start_lng, end_lat, end_lng,
                                               "도로 네트워크에서 연결된 경로를 찾을 수 없어 직선 경로를 제공합니다.")
            
        except Exception as e:
            logger.error(f"경로 계산 실패: {e}")
            return self._create_direct_route(start_lat, start_lng, end_lat, end_lng,
                                           f"경로 계산 중 오류가 발생했습니다: {str(e)}")
    
    def _calculate_path_distance(self, path: List[str]) -> float:
        """경로의 총 거리 계산"""
        total_distance = 0
        for i in range(len(path) - 1):
            edge_data = self.graph.get_edge_data(path[i], path[i+1])
            if edge_data:
                total_distance += edge_data.get('distance', 0)
        return total_distance
    
    def _create_route_info(self, path: List[str], start_lat: float, start_lng: float, 
                          end_lat: float, end_lng: float, start_dist: float, end_dist: float) -> Dict:
        """경로 정보 생성"""
        # 실제 출발점에서 시작
        waypoints = [{"lat": start_lat, "lng": start_lng}]
        
        total_distance = start_dist  # 시작점까지의 거리 포함
        segments = []
        highway_types = {}
        
        # 경로의 각 노드를 waypoint로 변환
        for i, node_id in enumerate(path):
            node_data = self.graph.nodes[node_id]
            if 'lat' in node_data and 'lng' in node_data:
                waypoints.append({
                    "lat": node_data['lat'],
                    "lng": node_data['lng']
                })
                
                # 세그먼트 정보 수집
                if i > 0:
                    prev_node = path[i-1]
                    edge_data = self.graph.get_edge_data(prev_node, node_id)
                    
                    if edge_data:
                        segment_distance = edge_data.get('distance', 0)
                        total_distance += segment_distance
                        highway_type = edge_data.get('highway_type', 'unknown')
                        
                        # highway 타입별 통계
                        highway_types[highway_type] = highway_types.get(highway_type, 0) + 1
                        
                        segments.append({
                            "start": {"lat": self.graph.nodes[prev_node]['lat'], "lng": self.graph.nodes[prev_node]['lng']},
                            "end": {"lat": node_data['lat'], "lng": node_data['lng']},
                            "distance": round(segment_distance, 1),
                            "highway_type": highway_type,
                            "pedestrian_only": edge_data.get('pedestrian_only', False),
                            "priority": edge_data.get('priority', 1.0)
                        })
        
        # 실제 도착점으로 종료
        waypoints.append({"lat": end_lat, "lng": end_lng})
        total_distance += end_dist  # 도착점까지의 거리 포함
        
        # 예상 소요시간 계산 (평균 보행속도 4km/h)
        estimated_time = int((total_distance / 1000) / 4 * 60)
        
        # 보행자 전용 구간 비율 계산
        pedestrian_only_segments = len([s for s in segments if s.get("pedestrian_only", False)])
        pedestrian_ratio = pedestrian_only_segments / max(len(segments), 1)
        
        # 경로 타입 결정
        if self.osm_data_loaded:
            route_type = "real_osm_pedestrian"
            message = f"실제 서울시 OSM 데이터 기반 도보 경로입니다."
        else:
            route_type = "fallback_pedestrian"
            message = f"대체 네트워크 기반 도보 경로입니다."
        
        # highway 타입 요약
        highway_summary = ", ".join([f"{ht}: {cnt}구간" for ht, cnt in highway_types.items()])
        if highway_summary:
            message += f" 경로 구성: {highway_summary}"
        
        return {
            "waypoints": waypoints,
            "distance": round(total_distance / 1000, 3),  # km
            "estimated_time": max(1, estimated_time),
            "route_type": route_type,
            "segments": segments,
            "total_segments": len(segments),
            "sidewalk_ratio": pedestrian_ratio,
            "highway_types": highway_types,
            "data_source": "Real OSM Data" if self.osm_data_loaded else "Fallback Network",
            "message": message
        }
    
    def _create_direct_route(self, start_lat: float, start_lng: float, 
                           end_lat: float, end_lng: float, message: str) -> Dict:
        """직선 경로 생성"""
        distance = geodesic((start_lat, start_lng), (end_lat, end_lng)).kilometers
        estimated_time = int(distance / 4 * 60)
        
        return {
            "waypoints": [
                {"lat": start_lat, "lng": start_lng},
                {"lat": end_lat, "lng": end_lng}
            ],
            "distance": round(distance, 3),
            "estimated_time": max(1, estimated_time),
            "route_type": "direct",
            "segments": [],
            "total_segments": 1,
            "sidewalk_ratio": 0.0,
            "highway_types": {},
            "data_source": "Direct Line",
            "message": message
        }
    
    def get_network_stats(self) -> Dict:
        """네트워크 통계 정보 반환"""
        try:
            highway_type_stats = {}
            pedestrian_only_edges = 0
            
            for u, v, data in self.graph.edges(data=True):
                highway_type = data.get('highway_type', 'unknown')
                highway_type_stats[highway_type] = highway_type_stats.get(highway_type, 0) + 1
                
                if data.get('pedestrian_only', False):
                    pedestrian_only_edges += 1
            
            return {
                "total_nodes": self.graph.number_of_nodes(),
                "total_edges": self.graph.number_of_edges(),
                "highway_type_distribution": highway_type_stats,
                "pedestrian_only_edges": pedestrian_only_edges,
                "osm_data_loaded": self.osm_data_loaded,
                "data_source": "Real OSM Data" if self.osm_data_loaded else "Fallback Network"
            }
            
        except Exception as e:
            logger.error(f"통계 계산 실패: {e}")
            return {
                "total_nodes": self.graph.number_of_nodes(),
                "total_edges": self.graph.number_of_edges(),
                "error": str(e)
            }


# 초기화 함수
def init_pedestrian_router(database_url: str):
    """실제 OSM 데이터 기반 도보 라우터 초기화"""
    try:
        router = RealOSMPedestrianRouter(database_url)
        logger.info("실제 OSM 도보 라우터 초기화 완료")
        return router
    except Exception as e:
        logger.error(f"도보 라우터 초기화 실패: {e}")
        return None