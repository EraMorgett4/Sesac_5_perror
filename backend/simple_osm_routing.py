# simple_osm_routing.py - 공간 인덱스 및 캐싱으로 최적화된 버전

import psycopg2
import networkx as nx
import math
import pickle
import os
import time
from typing import List, Dict, Tuple, Optional
from geopy.distance import geodesic
from scipy.spatial import KDTree
import logging
import json
from functools import lru_cache
import hashlib

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class OptimizedOSMRouter:
    def __init__(self, database_url: str, cache_dir: str = "cache"):
        self.database_url = database_url
        self.cache_dir = cache_dir
        self.graph = nx.Graph()
        
        # 공간 인덱스를 위한 데이터 구조
        self.node_coordinates = []  # [(lat, lng), ...]
        self.node_ids = []          # [node_id, ...]
        self.spatial_index = None   # KDTree
        
        # 캐시 관련
        self.route_cache = {}       # 경로 캐시
        self.max_cache_size = 1000  # 최대 캐시 항목 수
        
        # 캐시 디렉토리 생성
        os.makedirs(cache_dir, exist_ok=True)
        
        try:
            # 캐시된 네트워크 로드 시도
            if self._load_cached_network():
                logger.info("캐시된 네트워크 로드 성공")
            else:
                # 새로 네트워크 구축
                self.conn = psycopg2.connect(
                    host='192.168.165.133',
                    port=5432,
                    database='seoul_gis',
                    user='postgres',
                    password='sesacmicro31#!'
                )
                logger.info("직접 PostgreSQL 연결 성공")
                self._load_and_cache_network()
                
        except Exception as e:
            logger.error(f"연결 실패: {e}")
            self._create_fallback_network()
    
    def _get_cache_path(self, filename):
        """캐시 파일 경로 생성"""
        return os.path.join(self.cache_dir, filename)
    
    def _load_cached_network(self):
        """캐시된 네트워크 로드"""
        try:
            cache_files = {
                'graph': self._get_cache_path('graph.pkl'),
                'spatial': self._get_cache_path('spatial_index.pkl'),
                'metadata': self._get_cache_path('metadata.json')
            }
            
            # 모든 캐시 파일이 존재하는지 확인
            if not all(os.path.exists(f) for f in cache_files.values()):
                logger.info("일부 캐시 파일이 없음")
                return False
            
            logger.info("캐시된 네트워크 로드 중...")
            start_time = time.time()
            
            # 메타데이터 확인
            with open(cache_files['metadata'], 'r') as f:
                metadata = json.load(f)
            
            cache_age_days = (time.time() - metadata['created_time']) / (24 * 3600)
            if cache_age_days > 7:  # 7일 이상 오래된 캐시는 무시
                logger.info(f"캐시가 오래됨 ({cache_age_days:.1f}일)")
                return False
            
            # 그래프 로드
            with open(cache_files['graph'], 'rb') as f:
                self.graph = pickle.load(f)
            
            # 공간 인덱스 로드
            with open(cache_files['spatial'], 'rb') as f:
                spatial_data = pickle.load(f)
                self.node_coordinates = spatial_data['coordinates']
                self.node_ids = spatial_data['node_ids']
                self.spatial_index = KDTree(self.node_coordinates)
            
            load_time = time.time() - start_time
            logger.info(f"캐시 로드 완료: {load_time:.2f}초, "
                       f"{self.graph.number_of_nodes():,}개 노드, "
                       f"{self.graph.number_of_edges():,}개 엣지")
            return True
            
        except Exception as e:
            logger.warning(f"캐시 로드 실패: {e}")
            return False
    
    def _save_network_cache(self):
        """네트워크를 캐시에 저장"""
        try:
            logger.info("네트워크 캐시 저장 중...")
            start_time = time.time()
            
            # 그래프 저장
            with open(self._get_cache_path('graph.pkl'), 'wb') as f:
                pickle.dump(self.graph, f)
            
            # 공간 인덱스 저장
            spatial_data = {
                'coordinates': self.node_coordinates,
                'node_ids': self.node_ids
            }
            with open(self._get_cache_path('spatial_index.pkl'), 'wb') as f:
                pickle.dump(spatial_data, f)
            
            # 메타데이터 저장
            metadata = {
                'created_time': time.time(),
                'node_count': self.graph.number_of_nodes(),
                'edge_count': self.graph.number_of_edges(),
                'version': '1.0'
            }
            with open(self._get_cache_path('metadata.json'), 'w') as f:
                json.dump(metadata, f)
            
            save_time = time.time() - start_time
            logger.info(f"캐시 저장 완료: {save_time:.2f}초")
            
        except Exception as e:
            logger.error(f"캐시 저장 실패: {e}")
    
    def _load_and_cache_network(self):
        """네트워크 로드 및 캐시"""
        logger.info("새 네트워크 구축 시작...")
        start_time = time.time()
        
        self._load_optimized_network()
        self._build_spatial_index()
        self._save_network_cache()
        
        total_time = time.time() - start_time
        logger.info(f"네트워크 구축 완료: {total_time:.2f}초")
    
    def _load_optimized_network(self):
        """최적화된 네트워크 로드"""
        try:
            cursor = self.conn.cursor()
            
            # 더 큰 영역으로 확장 + 배치 처리
            logger.info("최적화된 OSM 데이터 로드...")
            
            # footway + residential + pedestrian 한번에 로드
            cursor.execute("""
                SELECT 
                    osm_id,
                    highway,
                    name,
                    ST_AsGeoJSON(ST_Transform(way, 4326)) as geometry
                FROM planet_osm_line 
                WHERE highway IN ('footway', 'residential', 'pedestrian', 'path', 'cycleway')
                  AND way && ST_Transform(ST_MakeEnvelope(126.7, 37.4, 127.2, 37.7, 4326), 3857)
                LIMIT 5000;
            """)
            
            results = cursor.fetchall()
            logger.info(f"총 {len(results)}개 도로 세그먼트 로드")
            
            # 배치 처리로 노드 및 엣지 생성
            node_batch = {}
            edge_batch = []
            
            for row in results:
                try:
                    osm_id, highway, name, geometry = row
                    if geometry:
                        geom = json.loads(geometry)
                        if geom['type'] == 'LineString':
                            coords = geom['coordinates']
                            
                            # 가중치 설정
                            weight_multiplier = {
                                'footway': 1.0,
                                'pedestrian': 1.0,
                                'path': 1.1,
                                'cycleway': 1.2,
                                'residential': 1.5
                            }.get(highway, 1.3)
                            
                            for i in range(len(coords) - 1):
                                start_lat, start_lng = coords[i][1], coords[i][0]
                                end_lat, end_lng = coords[i+1][1], coords[i+1][0]
                                
                                start_node = f"{start_lat:.5f},{start_lng:.5f}"
                                end_node = f"{end_lat:.5f},{end_lng:.5f}"
                                
                                distance = geodesic((start_lat, start_lng), (end_lat, end_lng)).meters
                                
                                if distance > 1:  # 1미터 이상만
                                    # 노드 정보 저장
                                    node_batch[start_node] = (start_lat, start_lng)
                                    node_batch[end_node] = (end_lat, end_lng)
                                    
                                    # 엣지 정보 저장
                                    edge_batch.append({
                                        'start': start_node,
                                        'end': end_node,
                                        'weight': distance * weight_multiplier,
                                        'highway_type': highway,
                                        'distance': distance
                                    })
                
                except Exception as e:
                    logger.warning(f"데이터 처리 실패: {e}")
                    continue
            
            # 배치로 그래프에 추가
            logger.info(f"그래프 구축: {len(node_batch)}개 노드, {len(edge_batch)}개 엣지")
            
            # 노드 추가
            for node_id, (lat, lng) in node_batch.items():
                self.graph.add_node(node_id, lat=lat, lng=lng)
            
            # 엣지 추가
            for edge in edge_batch:
                self.graph.add_edge(
                    edge['start'], edge['end'],
                    weight=edge['weight'],
                    highway_type=edge['highway_type'],
                    distance=edge['distance']
                )
            
            cursor.close()
            
            if self.graph.number_of_nodes() > 0:
                logger.info(f"최적화된 OSM 네트워크 로드 완료: {self.graph.number_of_nodes():,}개 노드, {self.graph.number_of_edges():,}개 엣지")
            else:
                logger.warning("OSM 데이터 로드 실패, 대체 네트워크 생성")
                self._create_fallback_network()
                
        except Exception as e:
            logger.error(f"네트워크 로딩 실패: {e}")
            self._create_fallback_network()
    
    def _build_spatial_index(self):
        """공간 인덱스 구축"""
        logger.info("공간 인덱스 구축 중...")
        start_time = time.time()
        
        self.node_coordinates = []
        self.node_ids = []
        
        for node_id in self.graph.nodes():
            node_data = self.graph.nodes[node_id]
            if 'lat' in node_data and 'lng' in node_data:
                self.node_coordinates.append([node_data['lat'], node_data['lng']])
                self.node_ids.append(node_id)
        
        if self.node_coordinates:
            self.spatial_index = KDTree(self.node_coordinates)
            build_time = time.time() - start_time
            logger.info(f"공간 인덱스 구축 완료: {len(self.node_coordinates):,}개 노드, {build_time:.2f}초")
        else:
            logger.warning("공간 인덱스 구축 실패: 노드가 없음")
    
    def _create_fallback_network(self):
        """대체 네트워크 - 더 조밀하게"""
        logger.info("대체 네트워크 생성...")
        
        # 서울 주요 지역 확장
        major_points = [
            # 강남/서초 지역
            (37.4979, 127.0276, "강남역"),
            (37.5074, 127.0533, "선릉역"),
            (37.5172, 127.0473, "삼성역"),
            
            # 강서/마포 지역
            (37.5507, 126.8657, "강서구청"),
            (37.5509, 126.8495, "김포공항"),
            (37.5574, 126.9240, "홍대입구"),
            
            # 중구/종로 지역
            (37.5665, 126.9780, "서울시청"),
            (37.5703, 126.9925, "종로3가"),
            (37.5636, 126.9826, "명동"),
            
            # 영등포/용산 지역
            (37.5219, 126.9245, "여의도"),
            (37.5347, 126.9947, "이태원"),
            
            # 기타 주요 지역
            (37.5134, 127.1000, "잠실역"),
            (37.5800, 127.0410, "청량리"),
        ]
        
        # 격자 형태로 더 많은 노드 추가
        for lat_base in [37.49, 37.51, 37.53, 37.55, 37.57]:
            for lng_base in [126.85, 126.90, 126.95, 127.00, 127.05]:
                for lat_offset in [-0.005, 0, 0.005]:
                    for lng_offset in [-0.005, 0, 0.005]:
                        lat = lat_base + lat_offset
                        lng = lng_base + lng_offset
                        major_points.append((lat, lng, f"격자_{lat:.3f}_{lng:.3f}"))
        
        # 노드 추가
        for i, (lat, lng, name) in enumerate(major_points):
            node_id = f"fallback_{i}"
            self.graph.add_node(node_id, lat=lat, lng=lng, name=name)
        
        # 효율적인 연결 (가까운 노드들끼리만)
        nodes = list(self.graph.nodes())
        for i, node1 in enumerate(nodes):
            lat1 = self.graph.nodes[node1]['lat']
            lng1 = self.graph.nodes[node1]['lng']
            
            for j in range(i + 1, len(nodes)):
                node2 = nodes[j]
                lat2 = self.graph.nodes[node2]['lat']
                lng2 = self.graph.nodes[node2]['lng']
                
                distance = geodesic((lat1, lng1), (lat2, lng2)).meters
                
                # 거리별 연결 전략
                if distance <= 500:      # 500m 이내는 직접 연결
                    self.graph.add_edge(node1, node2, weight=distance, highway_type='fallback')
                elif distance <= 1500:   # 1.5km 이내는 가중치 증가
                    self.graph.add_edge(node1, node2, weight=distance * 1.2, highway_type='fallback')
        
        self._build_spatial_index()
        logger.info(f"대체 네트워크 완료: {self.graph.number_of_nodes():,}개 노드, {self.graph.number_of_edges():,}개 엣지")
    
    def _find_nearest_node_fast(self, target_lat, target_lng, k=5):
        """공간 인덱스를 사용한 빠른 최근접 노드 찾기"""
        if not self.spatial_index:
            return self._find_nearest_node_slow(target_lat, target_lng)
        
        try:
            # KDTree로 k개의 가장 가까운 노드 찾기
            distances, indices = self.spatial_index.query([target_lat, target_lng], k=k)
            
            # 스칼라인 경우 리스트로 변환
            if not hasattr(distances, '__len__'):
                distances = [distances]
                indices = [indices]
            
            # 가장 가까운 유효한 노드 반환
            for dist_deg, idx in zip(distances, indices):
                if idx < len(self.node_ids):
                    node_id = self.node_ids[idx]
                    # 거리를 미터로 변환 (대략적)
                    dist_meters = dist_deg * 111000  # 1도 ≈ 111km
                    
                    if dist_meters <= 3000:  # 3km 이내
                        logger.debug(f"빠른 노드 찾기: {node_id}, 거리: {dist_meters:.0f}m")
                        return node_id
            
            logger.warning("공간 인덱스에서 가까운 노드를 찾지 못함")
            return None
            
        except Exception as e:
            logger.warning(f"공간 인덱스 검색 실패: {e}, 느린 검색으로 대체")
            return self._find_nearest_node_slow(target_lat, target_lng)
    
    def _find_nearest_node_slow(self, target_lat, target_lng, max_distance=3000):
        """기존 방식의 느린 최근접 노드 찾기 (백업용)"""
        min_distance = float('inf')
        nearest_node = None
        
        for node_id in self.graph.nodes():
            node_data = self.graph.nodes[node_id]
            if 'lat' in node_data and 'lng' in node_data:
                distance = geodesic(
                    (target_lat, target_lng),
                    (node_data['lat'], node_data['lng'])
                ).meters
                
                if distance < min_distance and distance <= max_distance:
                    min_distance = distance
                    nearest_node = node_id
        
        return nearest_node
    
    def _get_route_cache_key(self, start_lat, start_lng, end_lat, end_lng, options=None):
        """경로 캐시 키 생성"""
        # 좌표를 적당히 반올림해서 캐시 효율성 높이기
        key_data = f"{start_lat:.4f},{start_lng:.4f}-{end_lat:.4f},{end_lng:.4f}"
        if options:
            key_data += f"-{hash(str(sorted(options.items())))}"
        return hashlib.md5(key_data.encode()).hexdigest()
    
    @lru_cache(maxsize=500)
    def _cached_shortest_path(self, start_node, end_node):
        """경로 계산 결과 캐싱"""
        try:
            return nx.shortest_path(self.graph, start_node, end_node, weight='weight')
        except nx.NetworkXNoPath:
            return None
    
    def calculate_pedestrian_route(self, start_lat, start_lng, end_lat, end_lng, **kwargs):
        """최적화된 경로 계산"""
        start_time = time.time()
        
        try:
            logger.info(f"최적화된 경로 계산: ({start_lat:.6f}, {start_lng:.6f}) -> ({end_lat:.6f}, {end_lng:.6f})")
            
            # 캐시 확인
            cache_key = self._get_route_cache_key(start_lat, start_lng, end_lat, end_lng, kwargs)
            if cache_key in self.route_cache:
                logger.info("캐시된 경로 반환")
                return self.route_cache[cache_key]
            
            # 빠른 노드 찾기
            start_node = self._find_nearest_node_fast(start_lat, start_lng)
            end_node = self._find_nearest_node_fast(end_lat, end_lng)
            
            logger.info(f"노드 찾기 완료: start={start_node}, end={end_node}")
            
            if not start_node or not end_node:
                logger.warning("가까운 노드를 찾을 수 없음")
                result = self._create_direct_route(start_lat, start_lng, end_lat, end_lng)
            else:
                # 캐시된 경로 계산
                path = self._cached_shortest_path(start_node, end_node)
                
                if path:
                    logger.info(f"경로 계산 성공: {len(path)}개 노드")
                    result = self._create_route_info(path, start_lat, start_lng, end_lat, end_lng)
                else:
                    logger.warning("경로를 찾을 수 없음")
                    result = self._create_direct_route(start_lat, start_lng, end_lat, end_lng)
            
            # 캐시 저장 (크기 제한)
            if len(self.route_cache) < self.max_cache_size:
                self.route_cache[cache_key] = result
            
            calc_time = time.time() - start_time
            logger.info(f"경로 계산 완료: {calc_time:.3f}초")
            
            return result
            
        except Exception as e:
            logger.error(f"경로 계산 실패: {e}")
            return self._create_direct_route(start_lat, start_lng, end_lat, end_lng)
    
    def _create_route_info(self, path, start_lat, start_lng, end_lat, end_lng):
        """경로 정보 생성"""
        waypoints = [{"lat": start_lat, "lng": start_lng}]
        total_distance = 0
        segments = []
        
        for node_id in path:
            node_data = self.graph.nodes[node_id]
            waypoints.append({"lat": node_data['lat'], "lng": node_data['lng']})
        
        waypoints.append({"lat": end_lat, "lng": end_lng})
        
        # 거리 계산
        for i in range(len(path) - 1):
            edge_data = self.graph.get_edge_data(path[i], path[i+1])
            if edge_data:
                segment_distance = edge_data.get('distance', edge_data.get('weight', 0))
                total_distance += segment_distance
                
                segments.append({
                    "start_node": path[i],
                    "end_node": path[i+1],
                    "distance": segment_distance,
                    "highway_type": edge_data.get('highway_type', 'unknown')
                })
        
        estimated_time = int((total_distance / 1000) / 4 * 60)
        
        return {
            "waypoints": waypoints,
            "distance": round(total_distance / 1000, 3),
            "estimated_time": max(1, estimated_time),
            "route_type": "simple_osm",
            "segments": segments,
            "total_segments": len(path) - 1,
            "sidewalk_ratio": 0.8,
            "avoided_zones": [],
            "message": f"최적화된 OSM 네트워크 기반 경로입니다. {len(path)}개 노드를 경유합니다."
        }
    
    def _create_direct_route(self, start_lat, start_lng, end_lat, end_lng):
        """직선 경로"""
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
            "avoided_zones": [],
            "message": "직선 경로입니다."
        }
    
    def get_network_stats(self):
        """네트워크 통계"""
        try:
            stats = {
                "total_nodes": self.graph.number_of_nodes(),
                "total_edges": self.graph.number_of_edges(),
                "sidewalk_edges": 0,
                "crossing_edges": 0,
                "pedestrian_area_edges": 0,
                "wheelchair_accessible_edges": 0,
                "highway_type_distribution": {},
                "cache_stats": {
                    "route_cache_size": len(self.route_cache),
                    "max_cache_size": self.max_cache_size,
                    "spatial_index_enabled": self.spatial_index is not None,
                    "cached_nodes": len(self.node_coordinates) if self.node_coordinates else 0
                }
            }
            
            # 엣지별 통계 계산
            for u, v, data in self.graph.edges(data=True):
                highway_type = data.get('highway_type', 'unknown')
                stats["highway_type_distribution"][highway_type] = stats["highway_type_distribution"].get(highway_type, 0) + 1
                
                if highway_type == 'footway':
                    stats["sidewalk_edges"] += 1
                elif highway_type == 'crossing':
                    stats["crossing_edges"] += 1
                elif highway_type == 'pedestrian':
                    stats["pedestrian_area_edges"] += 1
                
                if highway_type in ['footway', 'pedestrian', 'residential']:
                    stats["wheelchair_accessible_edges"] += 1
            
            stats["data_source"] = "Optimized OSM + Spatial Index + Cache"
            stats["network_type"] = "Cached OSM with KDTree"
            
            return stats
            
        except Exception as e:
            logger.error(f"통계 계산 실패: {e}")
            return {
                "total_nodes": self.graph.number_of_nodes(),
                "total_edges": self.graph.number_of_edges(),
                "error": str(e),
                "data_source": "Error in calculation"
            }
    
    def clear_cache(self):
        """캐시 정리"""
        self.route_cache.clear()
        self._cached_shortest_path.cache_clear()
        logger.info("캐시 정리 완료")

def init_pedestrian_router(database_url: str):
    """최적화된 라우터 초기화"""
    try:
        router = OptimizedOSMRouter(database_url)
        logger.info("최적화된 OSM 라우터 초기화 완료")
        return router
    except Exception as e:
        logger.error(f"라우터 초기화 실패: {e}")
        return None