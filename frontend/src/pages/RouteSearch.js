// frontend/src/pages/RouteSearch.js - 완전한 버전
import React, { useState, useEffect } from 'react';
import { MapContainer, TileLayer, Marker, Popup, Polyline, CircleMarker } from 'react-leaflet';
import { toast } from 'react-toastify';
import axios from 'axios';
import L from 'leaflet';
import '../styles/RouteSearch.css';

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
  
  // 검색 제안 결과
  const [startSuggestions, setStartSuggestions] = useState([]);
  const [endSuggestions, setEndSuggestions] = useState([]);
  const [showStartSuggestions, setShowStartSuggestions] = useState(false);
  const [showEndSuggestions, setShowEndSuggestions] = useState(false);
  
  // 검색 디바운싱을 위한 타이머
  const [searchTimeout, setSearchTimeout] = useState(null);

  // 컴포넌트 언마운트 시 타이머 정리
  useEffect(() => {
    return () => {
      if (searchTimeout) {
        clearTimeout(searchTimeout);
      }
    };
  }, [searchTimeout]);

  // 로컬 더미 데이터 (API 실패 시 백업)
  const getLocalSearchResults = (query) => {
    const localPlaces = [
      { place_name: "강남역", address_name: "서울 강남구 역삼동", x: "127.0276", y: "37.4979" },
      { place_name: "강서구청", address_name: "서울 강서구 화곡동", x: "126.8495", y: "37.5509" },
      { place_name: "홍대입구역", address_name: "서울 마포구 동교동", x: "126.9240", y: "37.5574" },
      { place_name: "명동", address_name: "서울 중구 명동", x: "126.9826", y: "37.5636" },
      { place_name: "잠실역", address_name: "서울 송파구 잠실동", x: "127.1000", y: "37.5134" },
      { place_name: "종로3가", address_name: "서울 종로구 종로3가", x: "126.9925", y: "37.5703" },
      { place_name: "이태원", address_name: "서울 용산구 이태원동", x: "126.9947", y: "37.5347" },
      { place_name: "신촌", address_name: "서울 서대문구 신촌동", x: "126.9364", y: "37.5558" },
      { place_name: "여의도", address_name: "서울 영등포구 여의도동", x: "126.9245", y: "37.5219" },
      { place_name: "청량리", address_name: "서울 동대문구 청량리동", x: "127.0410", y: "37.5800" },
      { place_name: "서울시청", address_name: "서울 중구 태평로1가", x: "126.9780", y: "37.5665" },
      { place_name: "동대문", address_name: "서울 중구 동대문로", x: "127.0099", y: "37.5711" },
      { place_name: "을지로", address_name: "서울 중구 을지로", x: "126.9910", y: "37.5664" },
      { place_name: "건대입구", address_name: "서울 광진구 화양동", x: "127.0699", y: "37.5403" },
      { place_name: "선릉역", address_name: "서울 강남구 대치동", x: "127.0495", y: "37.5045" }
    ];
    
    if (!query || query.length < 2) return [];
    
    const queryLower = query.toLowerCase();
    return localPlaces.filter(place => 
      place.place_name.toLowerCase().includes(queryLower) ||
      place.address_name.toLowerCase().includes(queryLower)
    );
  };

  // 카카오맵 API로 지명 검색
  const searchLocation = async (query) => {
    if (!query || query.length < 2) return [];
    
    try {
      // 먼저 통합 검색 API 시도
      const response = await axios.get('/search-location-combined', {
        params: { query: query.trim() }
      });
      
      const places = response.data.places || [];
      
      // API 결과가 없으면 로컬 데이터 사용
      if (places.length === 0) {
        return getLocalSearchResults(query);
      }
      
      return places;
      
    } catch (error) {
      console.error('지명 검색 실패:', error);
      
      // API 실패 시 로컬 더미 데이터 사용
      return getLocalSearchResults(query);
    }
  };

  // 출발지 입력 처리 (디바운싱 적용)
  const handleStartLocationChange = async (e) => {
    const value = e.target.value;
    setStartLocation(value);
    
    // 기존 타이머 취소
    if (searchTimeout) {
      clearTimeout(searchTimeout);
    }
    
    if (value.length >= 2) {
      // 500ms 후에 검색 실행 (타이핑 중 과도한 API 호출 방지)
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

  // 도착지 입력 처리 (디바운싱 적용)
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

  // 좌표 직접 입력 파싱 (기존 기능 유지)
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

  // 경로 검색 실행
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
      const response = await axios.post('/safe-route', {
        start_latitude: startPos.lat,
        start_longitude: startPos.lng,
        end_latitude: endPos.lat,
        end_longitude: endPos.lng
      });
      
      setRoute(response.data);
      toast.success(response.data.message);
    } catch (error) {
      console.error('경로 검색 에러:', error);
      toast.error('경로 검색 실패: ' + (error.response?.data?.detail || '서버 오류'));
    } finally {
      setLoading(false);
    }
  };

  // 현재 위치 가져오기
  const handleCurrentLocation = () => {
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        (position) => {
          const coords = {
            lat: position.coords.latitude,
            lng: position.coords.longitude
          };
          setStartLocation(`${coords.lat.toFixed(6)},${coords.lng.toFixed(6)}`);
          setStartCoords(coords);
          setShowStartSuggestions(false);
        },
        (error) => {
          toast.error('현재 위치를 가져올 수 없습니다: ' + error.message);
        }
      );
    } else {
      toast.error('이 브라우저는 위치 서비스를 지원하지 않습니다.');
    }
  };

  // 위험도에 따른 색상
  const getRiskColor = (risk) => {
    if (risk >= 0.8) return '#ff4444';
    if (risk >= 0.6) return '#ff8800';
    if (risk >= 0.4) return '#ffaa00';
    return '#88cc00';
  };

  // 드롭다운 외부 클릭 시 닫기
  const handleDocumentClick = (e) => {
    if (!e.target.closest('.search-input-container')) {
      setShowStartSuggestions(false);
      setShowEndSuggestions(false);
    }
  };

  useEffect(() => {
    document.addEventListener('click', handleDocumentClick);
    return () => {
      document.removeEventListener('click', handleDocumentClick);
    };
  }, []);

  return (
    <div className="route-search-container">
      <div className="search-panel">
        <h1>안전 경로 검색</h1>
        <p>지명이나 좌표로 검색 가능합니다</p>
        
        <div className="search-form">
          <div className="input-group">
            <label>출발지:</label>
            <div className="input-with-button">
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
              <button onClick={handleCurrentLocation} className="current-location-btn">
                현재위치
              </button>
            </div>
          </div>
          
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
            {loading ? '검색 중...' : '안전 경로 검색'}
          </button>
        </div>

        {route && (
          <div className="route-info">
            <h3>경로 정보</h3>
            <div className="route-details">
              <p><strong>경로 타입:</strong> {route.route_type === 'direct' ? '직선 경로' : '우회 경로'}</p>
              <p><strong>총 거리:</strong> {route.distance.toFixed(2)} km</p>
              <p><strong>예상 시간:</strong> {route.estimated_time}분</p>
              <p><strong>우회한 위험지역:</strong> {route.avoided_zones.length}개</p>
            </div>
            
            {route.avoided_zones.length > 0 && (
              <div className="avoided-zones">
                <h4>우회한 위험지역:</h4>
                <ul>
                  {route.avoided_zones.map((zone, index) => (
                    <li key={index}>
                      {zone.name} (위험도: {(zone.risk * 100).toFixed(1)}%)
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
      </div>

      <div className="map-container">
        <MapContainer
          center={[37.5665, 126.9780]}
          zoom={11}
          style={{ height: '600px', width: '100%' }}
        >
          <TileLayer
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          />
          
          {startCoords && (
            <Marker position={[startCoords.lat, startCoords.lng]}>
              <Popup>출발지: {startLocation}</Popup>
            </Marker>
          )}
          
          {endCoords && (
            <Marker position={[endCoords.lat, endCoords.lng]}>
              <Popup>도착지: {endLocation}</Popup>
            </Marker>
          )}
          
          {route && (
            <>
              <Polyline
                positions={route.waypoints.map(wp => [wp.lat, wp.lng])}
                color={route.route_type === 'direct' ? 'blue' : 'green'}
                weight={4}
                opacity={0.7}
              />
              
              {route.avoided_zones.map((zone, index) => (
                <CircleMarker
                  key={index}
                  center={[zone.lat, zone.lng]}
                  radius={15}
                  color={getRiskColor(zone.risk)}
                  fillColor={getRiskColor(zone.risk)}
                  fillOpacity={0.6}
                >
                  <Popup>
                    <div>
                      <h4>{zone.name}</h4>
                      <p>위험도: {(zone.risk * 100).toFixed(1)}%</p>
                      <p>이 지역을 우회합니다</p>
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