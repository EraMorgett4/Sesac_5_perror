// frontend/src/RouteSearch.js - 음성 안내 기능이 복구된 최종 완료 버전

import React, { useState, useEffect, useRef } from 'react';
import { MapContainer, TileLayer, Marker, Popup, Polyline, CircleMarker } from 'react-leaflet';
import { toast } from 'react-toastify';
import axios from 'axios';
import L from 'leaflet';
import AzureVoiceNavigation from '../components/AzureVoiceNavigation'; // 음성 안내 컴포넌트 다시 임포트
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
  const [activeTab, setActiveTab] = useState('recommend');

  const [startSuggestions, setStartSuggestions] = useState([]);
  const [endSuggestions, setEndSuggestions] = useState([]);
  const [showStartSuggestions, setShowStartSuggestions] = useState(false);
  const [showEndSuggestions, setShowEndSuggestions] = useState(false);
  const [showRouteDetails, setShowRouteDetails] = useState(false);
  
  const [recommendedCourses, setRecommendedCourses] = useState([]);
  const [searchTimeout, setSearchTimeout] = useState(null);
  const mapRef = useRef(null);

  useEffect(() => {
    handleCurrentLocation(true);
    return () => { if (searchTimeout) clearTimeout(searchTimeout); };
  }, []);

  // 음성 안내 기능 관련 함수들 다시 추가
  const handleVoiceRouteFound = (foundRoute, currentLoc, destCoords, destName) => {
    setRoute(foundRoute);
    setStartCoords(currentLoc);
    setEndCoords(destCoords);
    setStartLocation(`현재위치 (${currentLoc.lat.toFixed(4)}, ${currentLoc.lng.toFixed(4)})`);
    setEndLocation(destName || '음성 입력 목적지');
    
    if (mapRef.current) {
      const bounds = L.latLngBounds([
        [currentLoc.lat, currentLoc.lng],
        [destCoords.lat, destCoords.lng]
      ]);
      mapRef.current.fitBounds(bounds, { padding: [50, 50] });
    }
  };

  const handleVoiceLocationUpdate = (newLocation) => {
    setStartCoords(newLocation);
    setStartLocation(`현재위치 (${newLocation.lat.toFixed(4)}, ${newLocation.lng.toFixed(4)})`);
  };

  const fetchRecommendedCourses = async (coords) => {
    if (!coords) return;
    setLoading(true);
    try {
      const response = await axios.get('/exercise-areas');
      const areas = response.data.areas || [];
      const sortedCourses = areas.map(area => {
        const distance = L.latLng(coords.lat, coords.lng).distanceTo(L.latLng(area.center.lat, area.center.lng));
        return { ...area, distance: distance / 1000 };
      }).sort((a, b) => a.distance - b.distance);
      setRecommendedCourses(sortedCourses);
    } catch (error) {
      toast.error("추천 산책로를 불러오는 데 실패했습니다.");
    } finally {
      setLoading(false);
    }
  };

  const handleCurrentLocation = (autoFetchCourses = false) => {
    if (navigator.geolocation) {
      setLoading(true);
      navigator.geolocation.getCurrentPosition(
        (position) => {
          const coords = { lat: position.coords.latitude, lng: position.coords.longitude };
          setStartCoords(coords);
          setStartLocation(`현재위치 (${coords.lat.toFixed(4)}, ${coords.lng.toFixed(4)})`);
          setLoading(false);
          toast.success('현재 위치를 가져왔습니다.');
          if (autoFetchCourses) fetchRecommendedCourses(coords);
        },
        () => { setLoading(false); toast.error('위치 정보를 가져올 수 없습니다.'); },
        { timeout: 10000, enableHighAccuracy: true }
      );
    } else {
      toast.error('이 브라우저는 위치 서비스를 지원하지 않습니다.');
    }
  };

  const handleSelectCourse = async (course) => {
    if (!startCoords) {
      toast.error("현재 위치를 먼저 확인해주세요.");
      return;
    }
    const destinationCoords = { lat: course.center.lat, lng: course.center.lng };
    setEndLocation(course.name);
    setEndCoords(destinationCoords);
    
    setLoading(true);
    try {
      const endpoint = '/safe-walking-route';
      const response = await axios.post(endpoint, {
        start_latitude: startCoords.lat, start_longitude: startCoords.lng,
        end_latitude: destinationCoords.lat, end_longitude: destinationCoords.lng
      });
      setRoute(response.data);
      setShowRouteDetails(false);
      toast.success(`${course.name}(으)로 가는 안전 경로가 생성되었습니다!`);
    } catch (error) {
      toast.error(error.response?.data?.detail || '추천 경로 검색 중 오류가 발생했습니다.');
    } finally {
      setLoading(false);
    }
  };

  const searchLocation = async (query) => {
    if (!query || query.length < 2) return [];
    try {
      const response = await axios.get('/search-location-combined', { params: { query: query.trim() } });
      return response.data.places || [];
    } catch (error) { return []; }
  };

  const handleLocationChange = (setter, value, suggestionSetter, showSuggestionSetter) => {
    setter(value);
    if (searchTimeout) clearTimeout(searchTimeout);
    if (value.length >= 2) {
      const newTimeout = setTimeout(async () => {
        suggestionSetter(await searchLocation(value));
        showSuggestionSetter(true);
      }, 500);
      setSearchTimeout(newTimeout);
    } else {
      showSuggestionSetter(false);
    }
  };

  const selectLocation = (place, locSetter, coordsSetter, showSetter) => {
    locSetter(place.place_name);
    coordsSetter({ lat: parseFloat(place.y), lng: parseFloat(place.x) });
    showSetter(false);
  };
  
  const handleSearch = async (start = startCoords, end = endCoords) => {
    if (!start || !end) {
      toast.error('출발지와 도착지를 모두 설정해주세요.');
      return;
    }
    setLoading(true);
    try {
      const endpoint = routeType === 'safe' ? '/safe-walking-route' : '/walking-route';
      const response = await axios.post(endpoint, {
        start_latitude: start.lat, start_longitude: start.lng,
        end_latitude: end.lat, end_longitude: end.lng
      });
      setRoute(response.data);
      setShowRouteDetails(false);
      toast.success('도보 경로가 생성되었습니다!');
    } catch (error) {
      toast.error(error.response?.data?.detail || '경로 검색 중 오류가 발생했습니다.');
    } finally {
      setLoading(false);
    }
  };

  const formatDistance = (distance) => distance < 1 ? `${Math.round(distance * 1000)}m` : `${distance.toFixed(2)}km`;
  const formatDuration = (minutes) => minutes < 60 ? `${minutes}분` : `${Math.floor(minutes / 60)}시간 ${minutes % 60}분`;
  const getRouteColor = (type) => type?.includes('safe') ? '#4CAF50' : '#2196F3';

  return (
    <div className="route-search">
      <div className="search-panel">
        <h2>🚶‍♂️ 안전 도보 길잡이</h2>
        <div className="search-tabs">
          <button className={`tab-btn ${activeTab === 'recommend' ? 'active' : ''}`} onClick={() => setActiveTab('recommend')}>🏞️ 산책로 추천</button>
          <button className={`tab-btn ${activeTab === 'manual' ? 'active' : ''}`} onClick={() => setActiveTab('manual')}>⌨️ 목적지 검색</button>
          <button className={`tab-btn ${activeTab === 'voice' ? 'active' : ''}`} onClick={() => setActiveTab('voice')}>🎤 음성 안내</button>
        </div>

        {activeTab === 'manual' && (
          <>
            <div className="route-type-selector">
              <label><input type="radio" value="safe" checked={routeType === 'safe'} onChange={(e) => setRouteType(e.target.value)} />🛡️ 안전 경로</label>
              <label><input type="radio" value="basic" checked={routeType === 'basic'} onChange={(e) => setRouteType(e.target.value)} />📍 최단 경로</label>
            </div>
            <div className="search-inputs">
              <div className="input-group">
                <label>출발지:</label>
                <div className="input-with-suggestions">
                  <div className="search-input-container">
                    <input type="text" value={startLocation} onChange={(e) => handleLocationChange(setStartLocation, e.target.value, setStartSuggestions, setShowStartSuggestions)} onFocus={() => startSuggestions.length > 0 && setShowStartSuggestions(true)} placeholder="예: 강남역 또는 현재위치 버튼"/>
                    {showStartSuggestions && <div className="suggestions-dropdown">{startSuggestions.slice(0,5).map((p,i)=><div key={i} className="suggestion-item" onClick={()=>selectLocation(p,setStartLocation,setStartCoords,setShowStartSuggestions)}><div>{p.place_name}</div><div className="place-address">{p.address_name}</div></div>)}</div>}
                  </div>
                  <button onClick={() => handleCurrentLocation(false)} className="current-location-btn" disabled={loading}>📍</button>
                </div>
              </div>
              <div className="input-group">
                <label>도착지:</label>
                <input type="text" value={endLocation} onChange={(e) => handleLocationChange(setEndLocation, e.target.value, setEndSuggestions, setShowEndSuggestions)} onFocus={() => endSuggestions.length > 0 && setShowEndSuggestions(true)} placeholder="예: 홍대입구"/>
                {showEndSuggestions && <div className="suggestions-dropdown">{endSuggestions.slice(0,5).map((p,i)=><div key={i} className="suggestion-item" onClick={()=>selectLocation(p,setEndLocation,setEndCoords,setShowEndSuggestions)}><div>{p.place_name}</div><div className="place-address">{p.address_name}</div></div>)}</div>}
              </div>
              <button onClick={() => handleSearch()} disabled={loading} className="search-btn">{loading ? '🔍 경로 계산 중...' : '🚶‍♂️ 경로 검색'}</button>
            </div>
          </>
        )}
        
        {activeTab === 'recommend' && (
          <div className="recommend-panel">
            <h3>🏞️ 주변 추천 산책로</h3>
            <p>현재 위치에서 가까운 걷기 좋은 곳들이에요.</p>
            {loading && <div className="loading-spinner"></div>}
            <div className="course-list">
              {recommendedCourses.slice(0, 10).map((course, index) => (
                <div key={index} className="course-card" onClick={() => handleSelectCourse(course)}>
                  <div className="course-card-header">
                    <span className={`course-type ${course.type}`}>{course.type_description}</span>
                    <span className="course-distance">약 {course.distance.toFixed(1)}km</span>
                  </div>
                  <h4 className="course-name">{course.name}</h4>
                  <div className="course-tags">
                    {course.recommended_activities.slice(0, 3).map((tag, i) => (<span key={i} className="tag">{tag}</span>))}
                  </div>
                  <button className="course-select-btn">이곳으로 안전경로 안내</button>
                </div>
              ))}
            </div>
          </div>
        )}

        {activeTab === 'voice' && (
          <AzureVoiceNavigation 
            onRouteFound={handleVoiceRouteFound}
            onLocationUpdate={handleVoiceLocationUpdate}
            onServiceShutdown={() => console.log('음성 서비스 종료')}
          />
        )}

        {route && (
          <div className="route-info">
            <h3>📍 경로 정보</h3>
            <div className="route-summary">
              <div className="route-stat"><span>거리:</span><span>{formatDistance(route.distance)}</span></div>
              <div className="route-stat"><span>소요시간:</span><span>{formatDuration(route.estimated_time)}</span></div>
            </div>
            <div className="route-message"><p>{route.message}</p></div>
            {route.avoided_zones?.length > 0 && <div className="avoided-zones"><h4>🛡️ 우회한 위험지역:</h4><ul>{route.avoided_zones.map((z, i) => <li key={i}>{z.name}</li>)}</ul></div>}
            {route.steps?.length > 0 && <div className="route-details-toggle"><button onClick={() => setShowRouteDetails(!showRouteDetails)} className="details-toggle-btn">{showRouteDetails ? '🔼' : '🔽'} 상세 안내</button>{showRouteDetails && <div className="route-steps"><ol>{route.steps.map((s, i) => <li key={i}>{s.instruction} ({formatDistance(s.distance / 1000)})</li>)}</ol></div>}</div>}
          </div>
        )}
      </div>

      <div className="map-container">
        <MapContainer center={startCoords || [37.5665, 126.9780]} zoom={13} style={{ height: '100%', width: '100%' }} ref={mapRef}>
          <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors' />
          {startCoords && <Marker position={[startCoords.lat, startCoords.lng]}><Popup>🚩 출발지</Popup></Marker>}
          {endCoords && <Marker position={[endCoords.lat, endCoords.lng]}><Popup>🎯 도착지: {endLocation}</Popup></Marker>}
          {route?.waypoints && <Polyline positions={route.waypoints.map(wp => [wp.lat, wp.lng])} color={getRouteColor(route.route_type)} weight={5} />}
          {route?.avoided_zones?.map((zone, index) => <CircleMarker key={index} center={[zone.lat, zone.lng]} radius={20} color="#FF5722" fillOpacity={0.3}><Popup><h4>⚠️ {zone.name}</h4><p>위험도: {(zone.risk * 100).toFixed(1)}%</p></Popup></CircleMarker>)}
        </MapContainer>
      </div>
    </div>
  );
};

export default RouteSearch;