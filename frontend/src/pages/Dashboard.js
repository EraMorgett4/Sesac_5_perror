// frontend/src/pages/Dashboard.js - 카카오 지명 검색 추가 버전

import React, { useState, useEffect } from 'react';
import { toast } from 'react-toastify';
import axios from 'axios';
import '../styles/Dashboard.css';

const Dashboard = () => {
  const [currentLocation, setCurrentLocation] = useState(null);
  const [riskData, setRiskData] = useState(null);
  const [loading, setLoading] = useState(false);
  
  // 검색 입력 상태 (기존 좌표 입력 대신)
  const [searchInput, setSearchInput] = useState('');
  const [searchSuggestions, setSearchSuggestions] = useState([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [searchTimeout, setSearchTimeout] = useState(null);
  
  // 검색 방식 선택 (지명검색 vs 좌표입력)
  const [searchMode, setSearchMode] = useState('place'); // 'place' or 'coordinates'
  const [locationInput, setLocationInput] = useState({
    latitude: '',
    longitude: ''
  });

  useEffect(() => {
    getCurrentLocation();
    
    // 컴포넌트 언마운트 시 타이머 정리
    return () => {
      if (searchTimeout) {
        clearTimeout(searchTimeout);
      }
    };
  }, []);

  // 외부 클릭 시 드롭다운 닫기
  useEffect(() => {
    const handleDocumentClick = (e) => {
      if (!e.target.closest('.search-input-container')) {
        setShowSuggestions(false);
      }
    };

    document.addEventListener('click', handleDocumentClick);
    return () => {
      document.removeEventListener('click', handleDocumentClick);
    };
  }, []);

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
      return getLocalSearchResults(query);
    }
  };

  const getCurrentLocation = () => {
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        (position) => {
          const location = {
            latitude: position.coords.latitude,
            longitude: position.coords.longitude
          };
          setCurrentLocation(location);
          checkRiskAtLocation(location);
        },
        (error) => {
          toast.error('위치 정보를 가져올 수 없습니다: ' + error.message);
        }
      );
    } else {
      toast.error('이 브라우저는 위치 서비스를 지원하지 않습니다.');
    }
  };

  const checkRiskAtLocation = async (location) => {
    setLoading(true);
    try {
      const response = await axios.post('/predict-risk', location);
      setRiskData(response.data);
    } catch (error) {
      toast.error('위험도 예측 실패: ' + (error.response?.data?.detail || '서버 오류'));
    } finally {
      setLoading(false);
    }
  };

  // 지명 검색 입력 처리
  const handleSearchInputChange = async (e) => {
    const value = e.target.value;
    setSearchInput(value);
    
    // 기존 타이머 취소
    if (searchTimeout) {
      clearTimeout(searchTimeout);
    }
    
    if (value.length >= 2) {
      // 500ms 후에 검색 실행
      const newTimeout = setTimeout(async () => {
        const suggestions = await searchLocation(value);
        setSearchSuggestions(suggestions);
        setShowSuggestions(true);
      }, 500);
      
      setSearchTimeout(newTimeout);
    } else {
      setShowSuggestions(false);
      setSearchSuggestions([]);
    }
  };

  // 지명 선택
  const selectPlace = (place) => {
    setSearchInput(place.place_name);
    setShowSuggestions(false);
    setSearchSuggestions([]);
    
    // 선택한 장소의 위험도 확인
    const location = {
      latitude: parseFloat(place.y),
      longitude: parseFloat(place.x)
    };
    checkRiskAtLocation(location);
  };

  // 좌표 직접 입력으로 검색
  const handleManualLocationCheck = async (e) => {
    e.preventDefault();
    if (!locationInput.latitude || !locationInput.longitude) {
      toast.error('위도와 경도를 모두 입력해주세요.');
      return;
    }

    const location = {
      latitude: parseFloat(locationInput.latitude),
      longitude: parseFloat(locationInput.longitude)
    };

    await checkRiskAtLocation(location);
  };

  // 지명 검색으로 위험도 확인
  const handlePlaceSearch = async (e) => {
    e.preventDefault();
    
    if (!searchInput) {
      toast.error('검색할 장소를 입력해주세요.');
      return;
    }
    
    // 입력된 텍스트로 검색 시도
    const suggestions = await searchLocation(searchInput);
    if (suggestions.length > 0) {
      // 첫 번째 결과 사용
      selectPlace(suggestions[0]);
    } else {
      toast.error('검색 결과를 찾을 수 없습니다.');
    }
  };

  const getRiskColor = (riskScore) => {
    if (riskScore >= 0.8) return '#ff4444';
    if (riskScore >= 0.6) return '#ff8800';
    if (riskScore >= 0.4) return '#ffaa00';
    if (riskScore >= 0.2) return '#88cc00';
    return '#44cc44';
  };

  return (
    <div className="dashboard">
      <div className="dashboard-header">
        <h1>대시보드</h1>
        <p>현재 위치의 싱크홀 위험도를 확인해보세요!</p>
      </div>

      <div className="dashboard-content">
        <div className="current-location-card">
          <h2>📍 현재 위치</h2>
          {currentLocation ? (
            <div className="location-info">
              <p><strong>위도:</strong> {currentLocation.latitude.toFixed(6)}</p>
              <p><strong>경도:</strong> {currentLocation.longitude.toFixed(6)}</p>
              <button onClick={getCurrentLocation} className="refresh-btn">
                위치 새로고침
              </button>
            </div>
          ) : (
            <p>위치 정보를 가져오는 중...</p>
          )}
        </div>

        <div className="risk-prediction-card">
          <h2>🔍 위험도 예측</h2>
          {loading ? (
            <p>예측 중...</p>
          ) : riskData ? (
            <div className="risk-result">
              <div 
                className="risk-score"
                style={{ backgroundColor: getRiskColor(riskData.risk_score) }}
              >
                <span className="score-value">{(riskData.risk_score * 100).toFixed(1)}%</span>
                <span className="risk-level">{riskData.risk_level}</span>
              </div>
              <p className="risk-message">{riskData.message}</p>
            </div>
          ) : (
            <p>위치 정보를 확인한 후 위험도를 예측합니다.</p>
          )}
        </div>

        <div className="manual-location-card">
          <h2>🎯 특정 위치 검색</h2>
          
          {/* 검색 방식 선택 */}
          <div className="search-mode-selector">
            <div className="mode-buttons">
              <button 
                className={`mode-btn ${searchMode === 'place' ? 'active' : ''}`}
                onClick={() => setSearchMode('place')}
              >
                지명 검색
              </button>
              <button 
                className={`mode-btn ${searchMode === 'coordinates' ? 'active' : ''}`}
                onClick={() => setSearchMode('coordinates')}
              >
                좌표 입력
              </button>
            </div>
          </div>

          {/* 지명 검색 모드 */}
          {searchMode === 'place' && (
            <form onSubmit={handlePlaceSearch}>
              <div className="input-group">
                <label>장소명:</label>
                <div className="search-input-container">
                  <input
                    type="text"
                    value={searchInput}
                    onChange={handleSearchInputChange}
                    onFocus={() => searchSuggestions.length > 0 && setShowSuggestions(true)}
                    placeholder="예: 강남역, 홍대입구, 명동, 서울시청"
                  />
                  {showSuggestions && searchSuggestions.length > 0 && (
                    <div className="suggestions-dropdown">
                      {searchSuggestions.slice(0, 5).map((place, index) => (
                        <div
                          key={index}
                          className="suggestion-item"
                          onClick={() => selectPlace(place)}
                        >
                          <div className="place-name">{place.place_name}</div>
                          <div className="place-address">{place.address_name}</div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
              <button type="submit" disabled={loading}>위험도 확인</button>
            </form>
          )}

          {/* 좌표 입력 모드 */}
          {searchMode === 'coordinates' && (
            <form onSubmit={handleManualLocationCheck}>
              <div className="input-group">
                <label>위도:</label>
                <input
                  type="number"
                  step="any"
                  value={locationInput.latitude}
                  onChange={(e) => setLocationInput({...locationInput, latitude: e.target.value})}
                  placeholder="37.5665 (서울시청 예시)"
                />
              </div>
              <div className="input-group">
                <label>경도:</label>
                <input
                  type="number"
                  step="any"
                  value={locationInput.longitude}
                  onChange={(e) => setLocationInput({...locationInput, longitude: e.target.value})}
                  placeholder="126.9780 (서울시청 예시)"
                />
              </div>
              <button type="submit" disabled={loading}>위험도 확인</button>
            </form>
          )}
        </div>
      </div>
    </div>
  );
};

export default Dashboard;