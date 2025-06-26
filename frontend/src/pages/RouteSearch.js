// frontend/src/pages/RouteSearch.js - 음성 안내 통합 버전

import React, { useState, useEffect, useRef } from 'react';
import { MapContainer, TileLayer, Marker, Popup, Polyline, CircleMarker } from 'react-leaflet';
import { toast } from 'react-toastify';
import axios from 'axios';
import L from 'leaflet';
import AzureVoiceNavigation from '../components/AzureVoiceNavigation';
import '../styles/RouteSearch.css';
import '../styles/VoiceNavigation.css';

// 아이콘 설정
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
});

const RouteSearch = () => {
  const [startLocation, setStartLocation] = useState('');
  const [endLocation, setEndLocation] = useState('');
  const [startCoords, setStartCoords] = useState(null);
  const [endCoords, setEndCoords] = useState(null);
  const [route, setRoute] = useState(null);
  const [loading, setLoading] = useState(false);
  const [routeType, setRouteType] = useState('safe');
  const [activeTab, setActiveTab] = useState('manual'); // 'manual' 또는 'voice'
  
  // 검색 제안 결과
  const [startSuggestions, setStartSuggestions] = useState([]);
  const [endSuggestions, setEndSuggestions] = useState([]);
  const [showStartSuggestions, setShowStartSuggestions] = useState(false);
  const [showEndSuggestions, setShowEndSuggestions] = useState(false);
  
  // 경로 상세 정보 표시 상태
  const [showRouteDetails, setShowRouteDetails] = useState(false);
  
  // 검색 디바운싱을 위한 타이머
  const [searchTimeout, setSearchTimeout] = useState(null);
  
  // 지도 참조
  const mapRef = useRef(null);

  useEffect(() => {
    return () => {
      if (searchTimeout) {
        clearTimeout(searchTimeout);
      }
    };
  }, [searchTimeout]);

  // 음성 안내에서 경로가 찾아졌을 때 호출
  const handleVoiceRouteFound = (foundRoute, currentLoc, destCoords) => {
    setRoute(foundRoute);
    setStartCoords(currentLoc);
    setEndCoords(destCoords);
    setStartLocation(`현재위치 (${currentLoc.lat.toFixed(4)}, ${currentLoc.lng.toFixed(4)})`);
    setEndLocation('음성 입력 목적지');
    
    // 지도 중심을 경로에 맞게 조정
    if (mapRef.current) {
      const bounds = L.latLngBounds([
        [currentLoc.lat, currentLoc.lng],
        [destCoords.lat, destCoords.lng]
      ]);
      mapRef.current.fitBounds(bounds, { padding: [20, 20] });
    }
  };

  // 음성 안내에서 위치가 업데이트될 때 호출
  const handleVoiceLocationUpdate = (newLocation) => {
    setStartCoords(newLocation);
    setStartLocation(`현재위치 (${newLocation.lat.toFixed(4)}, ${newLocation.lng.toFixed(4)})`);
  };

  // 로컬 더미 데이터 (API 실패 시 백업)
  const getLocalSearchResults = (query) => {
    const localPlaces = [
      { place_name: "강남역", address_name: "서울 강남구 역삼동", x: "127.0276", y: "37.4979" },
      { place_name: "홍대입구역", address_name: "서울 마포구 동교동", x: "126.9240", y: "37.5574" },
      { place_name: "명동", address_name: "서울 중구 명동", x: "126.9826", y: "37.5636" },
      { place_name: "잠실역", address_name: "서울 송파구 잠실동", x: "127.1000", y: "37.5134" },
      { place_name: "종로3가", address_name: "서울 종로구 종로3가", x: "126.9925", y: "37.5703" },
      { place_name: "이태원", address_name: "서울 용산구 이태원동", x: "126.9947", y: "37.5347" },
      { place_name: "신촌", address_name: "서울 서대문구 신촌동", x: "126.9364", y: "37.5558" },
      { place_name: "여의도", address_name: "서울 영등포구 여의도동", x: "126.9245", y: "37.5219" },
      { place_name: "서울시청", address_name: "서울 중구 태평로1가", x: "126.9780", y: "37.5665" },
      { place_name: "건대입구", address_name: "서울 광진구 화양동", x: "127.0699", y: "37.5403" },
    ];
    
    if (!query || query.length < 2) return [];
    
    const queryLower = query.toLowerCase();
    return localPlaces.filter(place => 
      place.place_name.toLowerCase().includes(queryLower) ||
      place.address_name.toLowerCase().includes(queryLower)
    );
  };

  // 지명 검색 (기존 카카오 API 또는 오픈 지오코딩 사용)
  const searchLocation = async (query) => {
    if (!query || query.length < 2) return [];
    
    try {
      // 1. 기존 카카오 API 시도
      let response = await axios.get('/search-location-combined', {
        params: { query: query.trim() }
      });
      
      let places = response.data.places || [];
      
      // 2. 카카오 API 결과가 없으면 오픈 지오코딩 시도
      if (places.length === 0) {
        try {
          const geocodeResponse = await axios.get('/geocode', {
            params: { address: query.trim() }
          });
          
          if (geocodeResponse.data) {
            places = [{
              place_name: query,
              address_name: geocodeResponse.data.display_name,
              x: geocodeResponse.data.longitude.toString(),
              y: geocodeResponse.data.latitude.toString()
            }];
          }
        } catch (geocodeError) {
          console.log('지오코딩 실패:', geocodeError);
        }
      }
      
      // 3. 모든 API가 실패하면 로컬 데이터 사용
      if (places.length === 0) {
        return getLocalSearchResults(query);
      }
      
      return places;
      
    } catch (error) {
      console.error('지명 검색 실패:', error);
      return getLocalSearchResults(query);
    }
  };

  // 출발지 입력 처리
  const handleStartLocationChange = async (e) => {
    const value = e.target.value;
    setStartLocation(value);
    
    if (searchTimeout) {
      clearTimeout(searchTimeout);
    }
    
    if (value.length >= 2) {
      const newTimeout = setTimeout(async () => {
        const suggestions = await searchLocation(value);
        setStartSuggestions(suggestions);
        setShowStartSuggestions(true);
      }, 500);
      
      setSearchTimeout(newTimeout);
    } else {
      setShowStartSuggestions(false);
      setStartSuggestions([]);
    }
  };

  // 도착지 입력 처리
  const handleEndLocationChange = async (e) => {
    const value = e.target.value;
    setEndLocation(value);
    
    if (searchTimeout) {
      clearTimeout(searchTimeout);
    }
    
    if (value.length >= 2) {
      const newTimeout = setTimeout(async () => {
        const suggestions = await searchLocation(value);
        setEndSuggestions(suggestions);
        setShowEndSuggestions(true);
      }, 500);
      
      setSearchTimeout(newTimeout);
    } else {
      setShowEndSuggestions(false);
      setEndSuggestions([]);
    }
  };

  // 출발지 선택
  const selectStartLocation = (place) => {
    setStartLocation(place.place_name);
    setStartCoords({ lat: parseFloat(place.y), lng: parseFloat(place.x) });
    setShowStartSuggestions(false);
    setStartSuggestions([]);
  };

  // 도착지 선택
  const selectEndLocation = (place) => {
    setEndLocation(place.place_name);
    setEndCoords({ lat: parseFloat(place.y), lng: parseFloat(place.x) });
    setShowEndSuggestions(false);
    setEndSuggestions([]);
  };

  // 현재 위치 가져오기
  const handleCurrentLocation = () => {
    if (navigator.geolocation) {
      setLoading(true);
      navigator.geolocation.getCurrentPosition(
        (position) => {
          const coords = {
            lat: position.coords.latitude,
            lng: position.coords.longitude
          };
          setStartCoords(coords);
          setStartLocation(`현재위치 (${coords.lat.toFixed(4)}, ${coords.lng.toFixed(4)})`);
          setLoading(false);
          toast.success('현재 위치를 가져왔습니다.');
        },
        (error) => {
          setLoading(false);
          toast.error('위치 정보를 가져올 수 없습니다.');
          console.error('Geolocation error:', error);
        },
        { timeout: 10000, enableHighAccuracy: true }
      );
    } else {
      toast.error('이 브라우저는 위치 서비스를 지원하지 않습니다.');
    }
  };

  // 좌표 직접 입력 파싱
  const parseCoordinates = (locationStr) => {
    const coordMatch = locationStr.match(/([0-9.]+),\s*([0-9.]+)/);
    if (coordMatch) {
      return {
        lat: parseFloat(coordMatch[1]),
        lng: parseFloat(coordMatch[2])
      };
    }
    return null;
  };
  const handleServiceShutdown = () => {
  console.log('음성 서비스가 종료되었습니다');
  // 필요한 정리 작업 수행
};
  // 도보 경로 검색 실행 (수동 입력용)
  const handleSearch = async () => {
    let startPos = startCoords;
    let endPos = endCoords;
    
    // 좌표가 설정되지 않은 경우 좌표 형식인지 확인
    if (!startPos) {
      startPos = parseCoordinates(startLocation);
      if (!startPos) {
        toast.error('출발지를 선택하거나 올바른 좌표를 입력해주세요.');
        return;
      }
    }
    
    if (!endPos) {
      endPos = parseCoordinates(endLocation);
      if (!endPos) {
        toast.error('도착지를 선택하거나 올바른 좌표를 입력해주세요.');
        return;
      }
    }

    setLoading(true);
    
    try {
      const endpoint = routeType === 'safe' ? '/safe-walking-route' : '/walking-route';
      
      const routeRequest = {
        start_latitude: startPos.lat,
        start_longitude: startPos.lng,
        end_latitude: endPos.lat,
        end_longitude: endPos.lng
      };

      const response = await axios.post(endpoint, routeRequest);
      
      if (response.data) {
        setRoute(response.data);
        setShowRouteDetails(false);
        toast.success('도보 경로가 생성되었습니다!');
      } else {
        toast.error('경로를 찾을 수 없습니다.');
      }
    } catch (error) {
      console.error('경로 검색 오류:', error);
      if (error.response?.data?.detail) {
        toast.error(error.response.data.detail);
      } else {
        toast.error('경로 검색 중 오류가 발생했습니다.');
      }
    } finally {
      setLoading(false);
    }
  };

  // 위험도에 따른 색상 결정
  const getRiskColor = (risk) => {
    if (risk >= 0.8) return '#ff0000';
    if (risk >= 0.6) return '#ff8800';
    if (risk >= 0.4) return '#ffff00';
    return '#00ff00';
  };

  // 거리와 시간 포맷팅
  const formatDistance = (distance) => {
    if (distance < 1) {
      return `${Math.round(distance * 1000)}m`;
    }
    return `${distance.toFixed(2)}km`;
  };

  const formatDuration = (minutes) => {
    if (minutes < 60) {
      return `${minutes}분`;
    }
    const hours = Math.floor(minutes / 60);
    const remainingMinutes = minutes % 60;
    return `${hours}시간 ${remainingMinutes}분`;
  };

  // 경로 출입구 교환
  const swapLocations = () => {
    const tempLocation = startLocation;
    setStartLocation(endLocation);
    setEndLocation(tempLocation);
    
    const tempCoords = startCoords;
    setStartCoords(endCoords);
    setEndCoords(tempCoords);
    
    setStartSuggestions([]);
    setEndSuggestions([]);
    setShowStartSuggestions(false);
    setShowEndSuggestions(false);
    
    toast.info('출발지와 도착지를 교환했습니다.');
  };

  return (
    <div className="route-search">
      <div className="search-panel">
        <h2>🚶‍♂️ 도보 경로 안내</h2>
        
        {/* 탭 전환 */}
        <div className="search-tabs">
          <button 
            className={`tab-btn ${activeTab === 'manual' ? 'active' : ''}`}
            onClick={() => setActiveTab('manual')}
          >
            ⌨️ 수동 입력
          </button>
          <button 
            className={`tab-btn ${activeTab === 'voice' ? 'active' : ''}`}
            onClick={() => setActiveTab('voice')}
          >
            🎤 음성 안내
          </button>
        </div>

        {activeTab === 'voice' ? (
          /* Azure 음성 안내 탭 */
          <AzureVoiceNavigation 
            onRouteFound={handleVoiceRouteFound}
            onLocationUpdate={handleVoiceLocationUpdate}
          />
        ) : (
          /* 수동 입력 탭 */
          <>
            {/* 경로 타입 선택 */}
            <div className="route-type-selector">
              <label>
                <input
                  type="radio"
                  value="safe"
                  checked={routeType === 'safe'}
                  onChange={(e) => setRouteType(e.target.value)}
                />
                🛡️ 안전 경로 (위험지역 우회)
              </label>
              <label>
                <input
                  type="radio"
                  value="basic"
                  checked={routeType === 'basic'}
                  onChange={(e) => setRouteType(e.target.value)}
                />
                📍 최단 경로
              </label>
            </div>

            <div className="search-inputs">
              {/* 출발지 입력 */}
              <div className="input-group">
                <label>출발지:</label>
                <div className="input-with-suggestions">
                  <div className="search-input-container">
                    <input
                      type="text"
                      value={startLocation}
                      onChange={handleStartLocationChange}
                      onFocus={() => startSuggestions.length > 0 && setShowStartSuggestions(true)}
                      placeholder="예: 강남역, 서울시청 또는 37.5665,126.9780"
                    />
                    {showStartSuggestions && startSuggestions.length > 0 && (
                      <div className="suggestions-dropdown">
                        {startSuggestions.slice(0, 5).map((place, index) => (
                          <div
                            key={index}
                            className="suggestion-item"
                            onClick={() => selectStartLocation(place)}
                          >
                            <div className="place-name">{place.place_name}</div>
                            <div className="place-address">{place.address_name}</div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                  <button onClick={handleCurrentLocation} className="current-location-btn" disabled={loading}>
                    📍 현재위치
                  </button>
                </div>
              </div>
              
              {/* 위치 교환 버튼 */}
              <div className="swap-locations">
                <button onClick={swapLocations} className="swap-btn" title="출발지와 도착지 교환">
                  🔄
                </button>
              </div>
              
              {/* 도착지 입력 */}
              <div className="input-group">
                <label>도착지:</label>
                <div className="search-input-container">
                  <input
                    type="text"
                    value={endLocation}
                    onChange={handleEndLocationChange}
                    onFocus={() => endSuggestions.length > 0 && setShowEndSuggestions(true)}
                    placeholder="예: 홍대입구, 명동 또는 37.4979,127.0276"
                  />
                  {showEndSuggestions && endSuggestions.length > 0 && (
                    <div className="suggestions-dropdown">
                      {endSuggestions.slice(0, 5).map((place, index) => (
                        <div
                          key={index}
                          className="suggestion-item"
                          onClick={() => selectEndLocation(place)}
                        >
                          <div className="place-name">{place.place_name}</div>
                          <div className="place-address">{place.address_name}</div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
              
              <button 
                onClick={handleSearch} 
                disabled={loading}
                className="search-btn"
              >
                {loading ? '🔍 경로 계산 중...' : '🚶‍♂️ 도보 경로 검색'}
              </button>
            </div>
          </>
        )}

        {/* 경로 정보 표시 */}
        {route && (
          <div className="route-info">
            <h3>📍 경로 정보</h3>
            <div className="route-summary">
              <div className="route-stat">
                <span className="stat-label">거리:</span>
                <span className="stat-value">{formatDistance(route.distance)}</span>
              </div>
              <div className="route-stat">
                <span className="stat-label">소요시간:</span>
                <span className="stat-value">{formatDuration(route.estimated_time)}</span>
              </div>
              <div className="route-stat">
                <span className="stat-label">경로 타입:</span>
                <span className="stat-value">
                  {route.route_type === 'safe_detour' && '🛡️ 안전 우회'}
                  {route.route_type === 'direct' && '📍 직선 경로'}
                  {route.route_type === 'walking' && '🚶‍♂️ 도보 경로'}
                  {route.route_type === 'direct_with_warning' && '⚠️ 주의 경로'}
                </span>
              </div>
            </div>
            
            <div className="route-message">
              <p>{route.message}</p>
            </div>
            
            {route.avoided_zones && route.avoided_zones.length > 0 && (
              <div className="avoided-zones">
                <h4>🛡️ 우회한 위험지역:</h4>
                <ul>
                  {route.avoided_zones.map((zone, index) => (
                    <li key={index} className="zone-item">
                      <span className="zone-name">{zone.name}</span>
                      <span className="zone-risk" style={{color: getRiskColor(zone.risk)}}>
                        위험도: {(zone.risk * 100).toFixed(1)}%
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
            
            {/* 상세 경로 안내 토글 */}
            {route.steps && route.steps.length > 0 && (
              <div className="route-details-toggle">
                <button 
                  onClick={() => setShowRouteDetails(!showRouteDetails)}
                  className="details-toggle-btn"
                >
                  {showRouteDetails ? '🔼 상세 안내 숨기기' : '🔽 상세 안내 보기'}
                </button>
                
                {showRouteDetails && (
                  <div className="route-steps">
                    <h4>🗺️ 상세 경로 안내:</h4>
                    <ol className="steps-list">
                      {route.steps.map((step, index) => (
                        <li key={index} className="step-item">
                          <div className="step-instruction">{step.instruction}</div>
                          {step.name && (
                            <div className="step-road">{step.name}</div>
                          )}
                          <div className="step-distance">
                            {step.distance > 0 && formatDistance(step.distance / 1000)}
                          </div>
                        </li>
                      ))}
                    </ol>
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>

      {/* 지도 컨테이너 */}
      <div className="map-container">
        <MapContainer
          center={[37.5665, 126.9780]}
          zoom={11}
          style={{ height: '600px', width: '100%' }}
          ref={mapRef}
        >
          <TileLayer
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          />
          
          {/* 출발지 마커 */}
          {startCoords && (
            <Marker position={[startCoords.lat, startCoords.lng]}>
              <Popup>
                <div>
                  <h4>🚩 출발지</h4>
                  <p>{startLocation}</p>
                  <small>위도: {startCoords.lat.toFixed(6)}</small><br/>
                  <small>경도: {startCoords.lng.toFixed(6)}</small>
                </div>
              </Popup>
            </Marker>
          )}
          
          {/* 도착지 마커 */}
          {endCoords && (
            <Marker position={[endCoords.lat, endCoords.lng]}>
              <Popup>
                <div>
                  <h4>🎯 도착지</h4>
                  <p>{endLocation}</p>
                  <small>위도: {endCoords.lat.toFixed(6)}</small><br/>
                  <small>경도: {endCoords.lng.toFixed(6)}</small>
                </div>
              </Popup>
            </Marker>
          )}
          
          {/* 경로 표시 */}
          {route && route.waypoints && (
            <>
              <Polyline
                positions={route.waypoints.map(wp => [wp.lat, wp.lng])}
                color={
                  route.route_type === 'safe_detour' ? '#4CAF50' :
                  route.route_type === 'direct_with_warning' ? '#FF9800' : '#2196F3'
                }
                weight={5}
                opacity={0.8}
              />
              
              {/* 우회한 위험지역 표시 */}
              {route.avoided_zones && route.avoided_zones.map((zone, index) => (
                <CircleMarker
                  key={index}
                  center={[zone.lat, zone.lng]}
                  radius={20}
                  color={getRiskColor(zone.risk)}
                  fillColor={getRiskColor(zone.risk)}
                  fillOpacity={0.3}
                  weight={2}
                >
                  <Popup>
                    <div>
                      <h4>⚠️ {zone.name}</h4>
                      <p><strong>위험도:</strong> {(zone.risk * 100).toFixed(1)}%</p>
                      <p><strong>상태:</strong> 우회됨</p>
                    </div>
                  </Popup>
                </CircleMarker>
              ))}
            </>
          )}
        </MapContainer>
      </div>
    </div>
  );
};

export default RouteSearch;