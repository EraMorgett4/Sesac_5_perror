import React, { useState, useEffect, useRef } from 'react';
import { MapContainer, TileLayer, Marker, Popup, Polyline, CircleMarker } from 'react-leaflet';
import { toast } from 'react-toastify';
import axios from 'axios';
import L from 'leaflet';
import '../styles/ExerciseRoute.css';

// 아이콘 설정
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
});

const ExerciseRoute = () => {
  // 기본 상태
  const [currentLocation, setCurrentLocation] = useState(null);
  const [exerciseRoute, setExerciseRoute] = useState(null);
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState('steps'); // 'steps' 또는 'time'
  
  // 운동 설정
  const [targetSteps, setTargetSteps] = useState(10000);
  const [exerciseTime, setExerciseTime] = useState(30);
  const [routeType, setRouteType] = useState('circular');
  const [areaPreference, setAreaPreference] = useState('auto');
  const [avoidDangerous, setAvoidDangerous] = useState(true);
  
  // 사용자 정보 (맞춤 추천용)
  const [userAge, setUserAge] = useState(30);
  const [fitnessLevel, setFitnessLevel] = useState('beginner');
  const [userWeight, setUserWeight] = useState(70);
  
  // 추천 지역 및 통계
  const [exerciseAreas, setExerciseAreas] = useState([]);
  const [recommendations, setRecommendations] = useState(null);
  const [exerciseStats, setExerciseStats] = useState(null);
  const [showRecommendations, setShowRecommendations] = useState(false);
  
  const mapRef = useRef(null);

  useEffect(() => {
    getCurrentLocation();
    loadExerciseAreas();
  }, []);

  // 현재 위치 가져오기
  const getCurrentLocation = () => {
    if (navigator.geolocation) {
      setLoading(true);
      navigator.geolocation.getCurrentPosition(
        (position) => {
          const coords = {
            lat: position.coords.latitude,
            lng: position.coords.longitude
          };
          setCurrentLocation(coords);
          setLoading(false);
          toast.success('현재 위치를 가져왔습니다.');
        },
        (error) => {
          setLoading(false);
          toast.error('위치 정보를 가져올 수 없습니다.');
          console.error('Geolocation error:', error);
          // 서울시청을 기본 위치로 설정
          setCurrentLocation({ lat: 37.5665, lng: 126.9780 });
        },
        { timeout: 10000, enableHighAccuracy: true }
      );
    } else {
      toast.error('이 브라우저는 위치 서비스를 지원하지 않습니다.');
      setCurrentLocation({ lat: 37.5665, lng: 126.9780 });
    }
  };

  // 운동 지역 목록 로드
  const loadExerciseAreas = async () => {
    try {
      const response = await axios.get('/exercise-areas');
      setExerciseAreas(response.data.areas || []);
    } catch (error) {
      console.error('운동 지역 로드 실패:', error);
    }
  };

  // 맞춤 추천 받기
  const getPersonalizedRecommendations = async () => {
    try {
      const response = await axios.get('/exercise-recommendations', {
        params: {
          user_age: userAge,
          fitness_level: fitnessLevel,
          available_time: exerciseTime
        }
      });
      setRecommendations(response.data);
      setShowRecommendations(true);
      
      // 추천 설정 자동 적용
      const rec = response.data.recommendations;
      setTargetSteps(rec.target_steps);
      setExerciseTime(rec.recommended_time_minutes);
      setRouteType(rec.preferred_route_type);
      
      toast.success('맞춤 추천이 적용되었습니다!');
    } catch (error) {
      console.error('추천 생성 실패:', error);
      toast.error('추천을 생성할 수 없습니다.');
    }
  };

  // 운동 경로 생성
  const generateExerciseRoute = async () => {
    if (!currentLocation) {
      toast.error('현재 위치를 먼저 확인해주세요.');
      return;
    }

    setLoading(true);

    try {
      let requestData;
      
      if (activeTab === 'steps') {
        // 걸음 수 기반 경로
        requestData = {
          start_latitude: currentLocation.lat,
          start_longitude: currentLocation.lng,
          target_steps: targetSteps,
          route_type: routeType,
          area_preference: areaPreference,
          avoid_dangerous_zones: avoidDangerous
        };
        
        const response = await axios.post('/exercise-route', requestData);
        setExerciseRoute(response.data);
        
      } else {
        // 시간 기반 간단 경로
        const response = await axios.post('/quick-exercise-route', null, {
          params: {
            lat: currentLocation.lat,
            lng: currentLocation.lng,
            minutes: exerciseTime,
            route_type: routeType
          }
        });
        setExerciseRoute({
          ...response.data,
          target_steps: response.data.estimated_steps,
          actual_steps: response.data.estimated_steps,
          steps_accuracy: 100
        });
      }

      // 지도 중심을 경로에 맞게 조정
      if (mapRef.current && exerciseRoute?.waypoints) {
        const bounds = L.latLngBounds(
          exerciseRoute.waypoints.map(wp => [wp.lat, wp.lng])
        );
        mapRef.current.fitBounds(bounds, { padding: [20, 20] });
      }

      toast.success('운동 경로가 생성되었습니다!');
      
    } catch (error) {
      console.error('경로 생성 실패:', error);
      if (error.response?.data?.detail) {
        toast.error(error.response.data.detail);
      } else {
        toast.error('경로 생성 중 오류가 발생했습니다.');
      }
    } finally {
      setLoading(false);
    }
  };

  // 운동 통계 계산
  const calculateExerciseStats = async () => {
    if (!exerciseRoute) return;

    try {
      const response = await axios.get('/exercise-statistics', {
        params: {
          steps: exerciseRoute.actual_steps,
          duration_minutes: exerciseRoute.estimated_time,
          user_weight_kg: userWeight
        }
      });
      setExerciseStats(response.data);
    } catch (error) {
      console.error('통계 계산 실패:', error);
    }
  };

  useEffect(() => {
    if (exerciseRoute) {
      calculateExerciseStats();
    }
  }, [exerciseRoute, userWeight]);

  // 거리와 시간 포맷팅
  const formatDistance = (distance) => {
    if (distance < 1) {
      return `${Math.round(distance * 1000)}m`;
    }
    return `${distance.toFixed(2)}km`;
  };

  const formatTime = (minutes) => {
    if (minutes < 60) {
      return `${minutes}분`;
    }
    const hours = Math.floor(minutes / 60);
    const remainingMinutes = minutes % 60;
    return `${hours}시간 ${remainingMinutes}분`;
  };

  // 경로 타입별 색상
  const getRouteColor = (routeType) => {
    if (routeType?.includes('circular')) return '#4CAF50';
    if (routeType?.includes('out_and_back')) return '#2196F3';
    return '#FF9800';
  };

  // 난이도별 색상
  const getDifficultyColor = (difficulty) => {
    switch (difficulty) {
      case 'easy': return '#4CAF50';
      case 'medium': return '#FF9800';
      case 'hard': return '#F44336';
      default: return '#2196F3';
    }
  };

  return (
    <div className="exercise-route">
      <div className="exercise-panel">
        <h2>🚶‍♂️ 만보기 운동 경로</h2>
        
        {/* 탭 전환 */}
        <div className="exercise-tabs">
          <button 
            className={`tab-btn ${activeTab === 'steps' ? 'active' : ''}`}
            onClick={() => setActiveTab('steps')}
          >
            👟 걸음 수 기반
          </button>
          <button 
            className={`tab-btn ${activeTab === 'time' ? 'active' : ''}`}
            onClick={() => setActiveTab('time')}
          >
            ⏰ 시간 기반
          </button>
        </div>

        {/* 사용자 정보 (맞춤 추천용) */}
        <div className="user-profile-section">
          <h3>👤 사용자 정보</h3>
          <div className="profile-inputs">
            <div className="input-row">
              <label>나이:</label>
              <input
                type="number"
                value={userAge}
                onChange={(e) => setUserAge(parseInt(e.target.value) || 30)}
                min="10"
                max="100"
              />
              <span>세</span>
            </div>
            <div className="input-row">
              <label>체력 수준:</label>
              <select value={fitnessLevel} onChange={(e) => setFitnessLevel(e.target.value)}>
                <option value="beginner">초보자</option>
                <option value="intermediate">중급자</option>
                <option value="advanced">고급자</option>
              </select>
            </div>
            <div className="input-row">
              <label>체중:</label>
              <input
                type="number"
                value={userWeight}
                onChange={(e) => setUserWeight(parseInt(e.target.value) || 70)}
                min="30"
                max="150"
              />
              <span>kg</span>
            </div>
          </div>
          <button 
            onClick={getPersonalizedRecommendations}
            className="recommendation-btn"
          >
            🎯 맞춤 추천 받기
          </button>
        </div>

        {/* 맞춤 추천 표시 */}
        {showRecommendations && recommendations && (
          <div className="recommendations-section">
            <h3>🎯 맞춤 추천</h3>
            <div className="recommendation-card">
              <div className="rec-stats">
                <div className="rec-stat">
                  <span className="label">목표 걸음:</span>
                  <span className="value">{recommendations.recommendations.target_steps.toLocaleString()}보</span>
                </div>
                <div className="rec-stat">
                  <span className="label">추천 시간:</span>
                  <span className="value">{recommendations.recommendations.recommended_time_minutes}분</span>
                </div>
                <div className="rec-stat">
                  <span className="label">추천 거리:</span>
                  <span className="value">{recommendations.recommendations.target_distance_km}km</span>
                </div>
              </div>
              <div className="rec-tips">
                <h4>💡 운동 팁</h4>
                <ul>
                  {recommendations.tips.map((tip, index) => (
                    <li key={index}>{tip}</li>
                  ))}
                </ul>
              </div>
            </div>
          </div>
        )}

        {/* 운동 설정 */}
        <div className="exercise-settings">
          <h3>⚙️ 운동 설정</h3>
          
          {activeTab === 'steps' ? (
            <div className="steps-settings">
              <div className="input-group">
                <label>목표 걸음 수:</label>
                <div className="steps-input">
                  <input
                    type="number"
                    value={targetSteps}
                    onChange={(e) => setTargetSteps(parseInt(e.target.value) || 10000)}
                    min="1000"
                    max="30000"
                    step="1000"
                  />
                  <span>걸음</span>
                </div>
                <div className="preset-buttons">
                  <button onClick={() => setTargetSteps(5000)} className="preset-btn">5천보</button>
                  <button onClick={() => setTargetSteps(8000)} className="preset-btn">8천보</button>
                  <button onClick={() => setTargetSteps(10000)} className="preset-btn">만보</button>
                  <button onClick={() => setTargetSteps(15000)} className="preset-btn">1.5만보</button>
                </div>
              </div>
              
              <div className="input-group">
                <label>지역 선호도:</label>
                <select value={areaPreference} onChange={(e) => setAreaPreference(e.target.value)}>
                  <option value="auto">자동 선택</option>
                  <option value="current">현재 위치</option>
                  <option value="park">공원</option>
                  <option value="river">강변</option>
                  <option value="stream">천변</option>
                </select>
              </div>
            </div>
          ) : (
            <div className="time-settings">
              <div className="input-group">
                <label>운동 시간:</label>
                <div className="time-input">
                  <input
                    type="number"
                    value={exerciseTime}
                    onChange={(e) => setExerciseTime(parseInt(e.target.value) || 30)}
                    min="10"
                    max="120"
                    step="5"
                  />
                  <span>분</span>
                </div>
                <div className="preset-buttons">
                  <button onClick={() => setExerciseTime(15)} className="preset-btn">15분</button>
                  <button onClick={() => setExerciseTime(30)} className="preset-btn">30분</button>
                  <button onClick={() => setExerciseTime(45)} className="preset-btn">45분</button>
                  <button onClick={() => setExerciseTime(60)} className="preset-btn">1시간</button>
                </div>
              </div>
            </div>
          )}

          <div className="input-group">
            <label>경로 타입:</label>
            <div className="route-type-options">
              <label className="radio-option">
                <input
                  type="radio"
                  value="circular"
                  checked={routeType === 'circular'}
                  onChange={(e) => setRouteType(e.target.value)}
                />
                🔄 원형 경로 (돌아서 오기)
              </label>
              <label className="radio-option">
                <input
                  type="radio"
                  value="out_and_back"
                  checked={routeType === 'out_and_back'}
                  onChange={(e) => setRouteType(e.target.value)}
                />
                ↔️ 왕복 경로 (되돌아 오기)
              </label>
            </div>
          </div>

          <div className="input-group">
            <label className="checkbox-option">
              <input
                type="checkbox"
                checked={avoidDangerous}
                onChange={(e) => setAvoidDangerous(e.target.checked)}
              />
              🛡️ 위험지역 우회
            </label>
          </div>

          <button 
            onClick={generateExerciseRoute}
            disabled={loading || !currentLocation}
            className="generate-btn"
          >
            {loading ? '경로 생성 중...' : '🚶‍♂️ 운동 경로 생성'}
          </button>
        </div>

        {/* 경로 정보 표시 */}
        {exerciseRoute && (
          <div className="route-result">
            <h3>📍 생성된 경로</h3>
            <div className="route-summary">
              <div className="summary-stats">
                <div className="stat-item">
                  <span className="stat-label">거리</span>
                  <span className="stat-value">{formatDistance(exerciseRoute.distance)}</span>
                </div>
                <div className="stat-item">
                  <span className="stat-label">예상 시간</span>
                  <span className="stat-value">{formatTime(exerciseRoute.estimated_time)}</span>
                </div>
                <div className="stat-item">
                  <span className="stat-label">예상 걸음</span>
                  <span className="stat-value">{exerciseRoute.actual_steps?.toLocaleString()}보</span>
                </div>
                <div className="stat-item">
                  <span className="stat-label">정확도</span>
                  <span className="stat-value">{exerciseRoute.steps_accuracy?.toFixed(1)}%</span>
                </div>
              </div>

              <div className="route-details">
                <div className="detail-item">
                  <span className="detail-label">경로 타입:</span>
                  <span className="detail-value" style={{color: getRouteColor(exerciseRoute.route_type)}}>
                    {exerciseRoute.route_description || exerciseRoute.route_type}
                  </span>
                </div>
                
                {exerciseRoute.exercise_area && (
                  <div className="detail-item">
                    <span className="detail-label">운동 지역:</span>
                    <span className="detail-value">{exerciseRoute.exercise_area.name}</span>
                  </div>
                )}
                
                {exerciseRoute.difficulty && (
                  <div className="detail-item">
                    <span className="detail-label">난이도:</span>
                    <span className="detail-value" style={{color: getDifficultyColor(exerciseRoute.difficulty)}}>
                      {exerciseRoute.difficulty === 'easy' ? '쉬움' : 
                       exerciseRoute.difficulty === 'medium' ? '보통' : '어려움'}
                    </span>
                  </div>
                )}
              </div>

              <div className="route-message">
                <p>{exerciseRoute.message}</p>
              </div>

              {/* 건강 효과 정보 */}
              {exerciseRoute.health_benefits && (
                <div className="health-benefits">
                  <h4>💪 건강 효과</h4>
                  <div className="benefits-stats">
                    <div className="benefit-item">
                      <span className="benefit-label">칼로리 소모:</span>
                      <span className="benefit-value">{exerciseRoute.health_benefits.calories_burned}kcal</span>
                    </div>
                    <div className="benefit-item">
                      <span className="benefit-label">건강 점수:</span>
                      <span className="benefit-value">{exerciseRoute.health_benefits.health_score}/100</span>
                    </div>
                  </div>
                  <div className="benefits-list">
                    {exerciseRoute.health_benefits.benefits?.map((benefit, index) => (
                      <span key={index} className="benefit-tag">{benefit}</span>
                    ))}
                  </div>
                </div>
              )}

              {/* 우회한 위험지역 */}
              {exerciseRoute.avoided_zones && exerciseRoute.avoided_zones.length > 0 && (
                <div className="avoided-zones">
                  <h4>🛡️ 우회한 위험지역</h4>
                  <ul>
                    {exerciseRoute.avoided_zones.map((zone, index) => (
                      <li key={index} className="zone-item">
                        <span className="zone-name">{zone.name}</span>
                        <span className="zone-risk">위험도: {(zone.risk * 100).toFixed(1)}%</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>

            {/* 상세 운동 통계 */}
            {exerciseStats && (
              <div className="detailed-stats">
                <h4>📊 상세 운동 분석</h4>
                <div className="stats-grid">
                  <div className="stats-section">
                    <h5>💨 운동 강도</h5>
                    <div className="intensity-info">
                      <span className="intensity-level">{exerciseStats.intensity.level}</span>
                      <span className="intensity-desc">{exerciseStats.intensity.description}</span>
                      <p className="intensity-rec">{exerciseStats.intensity.recommendation}</p>
                    </div>
                  </div>

                  <div className="stats-section">
                    <h5>🔥 칼로리 소모</h5>
                    <div className="calorie-info">
                      <div className="calorie-main">{exerciseStats.calories.burned}kcal</div>
                      <div className="calorie-equivalents">
                        <small>= 밥 {exerciseStats.calories.equivalent_foods.rice_bowls}공기</small><br/>
                        <small>= 사과 {exerciseStats.calories.equivalent_foods.apples}개</small>
                      </div>
                    </div>
                  </div>

                  <div className="stats-section">
                    <h5>🎯 목표 달성도</h5>
                    <div className="achievement-info">
                      <div className="achievement-score">{exerciseStats.health_assessment.score}/100</div>
                      <div className="achievement-grade">{exerciseStats.health_assessment.grade}</div>
                      <div className="daily-progress">{exerciseStats.health_assessment.daily_goal_achievement}</div>
                    </div>
                  </div>
                </div>

                {/* 개선 팁 */}
                <div className="improvement-tips">
                  <h5>💡 개선 팁</h5>
                  <ul>
                    {exerciseStats.recommendations.improvement_tips.map((tip, index) => (
                      <li key={index}>{tip}</li>
                    ))}
                  </ul>
                  <div className="next-goal">
                    <strong>다음 목표: {exerciseStats.recommendations.next_goal.toLocaleString()}걸음</strong>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* 추천 운동 지역 */}
        {exerciseAreas.length > 0 && (
          <div className="exercise-areas-section">
            <h3>🏞️ 추천 운동 지역</h3>
            <div className="areas-grid">
              {exerciseAreas.slice(0, 6).map((area, index) => (
                <div key={index} className="area-card">
                  <div className="area-header">
                    <h4>{area.name}</h4>
                    <span className={`area-type ${area.type}`}>{area.type_description}</span>
                  </div>
                  <div className="area-info">
                    <div className="area-detail">
                      <span>반경: {area.radius_km}km</span>
                    </div>
                    <div className="area-detail">
                      <span>난이도: {area.difficulty === 'easy' ? '쉬움' : area.difficulty === 'medium' ? '보통' : '어려움'}</span>
                    </div>
                  </div>
                  <div className="area-facilities">
                    {area.facilities.slice(0, 3).map((facility, idx) => (
                      <span key={idx} className="facility-tag">{facility}</span>
                    ))}
                  </div>
                  <button 
                    className="area-select-btn"
                    onClick={() => {
                      setAreaPreference(area.type);
                      toast.info(`${area.name} 지역이 선택되었습니다.`);
                    }}
                  >
                    이 지역 선택
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* 지도 컨테이너 */}
      <div className="map-container">
        <MapContainer
          center={currentLocation || [37.5665, 126.9780]}
          zoom={13}
          style={{ height: '600px', width: '100%' }}
          ref={mapRef}
        >
          <TileLayer
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          />
          
          {/* 현재 위치 마커 */}
          {currentLocation && (
            <Marker position={[currentLocation.lat, currentLocation.lng]}>
              <Popup>
                <div>
                  <h4>📍 현재 위치</h4>
                  <p>운동 시작 지점</p>
                  <small>위도: {currentLocation.lat.toFixed(6)}</small><br/>
                  <small>경도: {currentLocation.lng.toFixed(6)}</small>
                </div>
              </Popup>
            </Marker>
          )}
          
          {/* 운동 경로 표시 */}
          {exerciseRoute && exerciseRoute.waypoints && (
            <>
              <Polyline
                positions={exerciseRoute.waypoints.map(wp => [wp.lat, wp.lng])}
                color={getRouteColor(exerciseRoute.route_type)}
                weight={5}
                opacity={0.8}
                dashArray={exerciseRoute.route_type?.includes('out_and_back') ? '10, 5' : null}
              />
              
              {/* 시작/끝 지점 표시 */}
              {exerciseRoute.waypoints.length > 0 && (
                <>
                  <CircleMarker
                    center={[exerciseRoute.waypoints[0].lat, exerciseRoute.waypoints[0].lng]}
                    radius={8}
                    color="#4CAF50"
                    fillColor="#4CAF50"
                    fillOpacity={0.8}
                  >
                    <Popup>
                      <div>
                        <h4>🚀 시작 지점</h4>
                        <p>운동을 시작하세요!</p>
                      </div>
                    </Popup>
                  </CircleMarker>
                  
                  {exerciseRoute.waypoints.length > 1 && (
                    <CircleMarker
                      center={[
                        exerciseRoute.waypoints[exerciseRoute.waypoints.length - 1].lat,
                        exerciseRoute.waypoints[exerciseRoute.waypoints.length - 1].lng
                      ]}
                      radius={8}
                      color="#F44336"
                      fillColor="#F44336"
                      fillOpacity={0.8}
                    >
                      <Popup>
                        <div>
                          <h4>🏁 도착 지점</h4>
                          <p>수고하셨습니다!</p>
                        </div>
                      </Popup>
                    </CircleMarker>
                  )}
                </>
              )}
              
              {/* 우회한 위험지역 표시 */}
              {exerciseRoute.avoided_zones && exerciseRoute.avoided_zones.map((zone, index) => (
                <CircleMarker
                  key={index}
                  center={[zone.lat, zone.lng]}
                  radius={15}
                  color="#FF5722"
                  fillColor="#FF5722"
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
          
          {/* 추천 운동 지역 표시 */}
          {exerciseAreas.map((area, index) => (
            <CircleMarker
              key={index}
              center={[area.center.lat, area.center.lng]}
              radius={area.radius_km * 2}
              color="#2196F3"
              fillColor="#2196F3"
              fillOpacity={0.1}
              weight={1}
            >
              <Popup>
                <div>
                  <h4>🏞️ {area.name}</h4>
                  <p><strong>타입:</strong> {area.type_description}</p>
                  <p><strong>반경:</strong> {area.radius_km}km</p>
                  <p><strong>난이도:</strong> {area.difficulty === 'easy' ? '쉬움' : area.difficulty === 'medium' ? '보통' : '어려움'}</p>
                  <div className="popup-facilities">
                    <strong>시설:</strong> {area.facilities.join(', ')}
                  </div>
                </div>
              </Popup>
            </CircleMarker>
          ))}
        </MapContainer>
      </div>

      {/* 하단 정보 패널 */}
      <div className="bottom-info">
        <div className="info-section">
          <h3>🎯 운동 목표 가이드</h3>
          <div className="guide-grid">
            <div className="guide-item">
              <h4>초보자 (주 3-4회)</h4>
              <p>5,000-8,000걸음 / 20-30분</p>
              <p>공원이나 평지 위주</p>
            </div>
            <div className="guide-item">
              <h4>중급자 (주 4-5회)</h4>
              <p>8,000-12,000걸음 / 30-45분</p>
              <p>다양한 지형 도전</p>
            </div>
            <div className="guide-item">
              <h4>고급자 (주 5-6회)</h4>
              <p>12,000걸음 이상 / 45분 이상</p>
              <p>경사로, 산길 포함</p>
            </div>
          </div>
        </div>

        <div className="info-section">
          <h3>💡 운동 팁</h3>
          <ul className="tips-list">
            <li>🥤 운동 전후 충분한 수분 섭취</li>
            <li>👟 편안하고 잘 맞는 운동화 착용</li>
            <li>🌡️ 날씨와 시간대 고려하여 운동</li>
            <li>📱 스마트워치나 앱으로 기록 관리</li>
            <li>🤝 가족이나 친구와 함께 운동</li>
            <li>⚡ 무리하지 말고 점진적으로 강도 증가</li>
          </ul>
        </div>
      </div>
    </div>
  );
};

export default ExerciseRoute;