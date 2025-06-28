// frontend/src/pages/AzureMLTest.js - Azure ML 현재 위치 테스트 페이지

import React, { useState, useEffect } from 'react';
import { toast } from 'react-toastify';
import axios from 'axios';
import '../styles/AzureMltest.css';

const AzureMLTest = () => {
  const [currentLocation, setCurrentLocation] = useState(null);
  const [azureMLResult, setAzureMLResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [testHistory, setTestHistory] = useState([]);

  useEffect(() => {
    // 컴포넌트 마운트 시 현재 위치 확인
    getCurrentLocation();
  }, []);

  // 현재 위치 가져오기
  const getCurrentLocation = () => {
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        (position) => {
          const location = {
            latitude: position.coords.latitude,
            longitude: position.coords.longitude
          };
          setCurrentLocation(location);
          console.log('현재 위치 획득:', location);
        },
        (error) => {
          console.error('위치 정보 오류:', error);
          toast.error('위치 정보를 가져올 수 없습니다: ' + error.message);
        },
        {
          enableHighAccuracy: true,
          timeout: 10000,
          maximumAge: 300000 // 5분
        }
      );
    } else {
      toast.error('이 브라우저는 위치 서비스를 지원하지 않습니다.');
    }
  };

  // Azure ML 테스트 실행
  const runAzureMLTest = async (latitude, longitude, locationName) => {
    setLoading(true);
    
    try {
      console.log(`🤖 Azure ML 테스트 시작: ${locationName} (${latitude}, ${longitude})`);
      
      const response = await axios.get('/test-azure-ml', {
        params: {
          latitude: latitude,
          longitude: longitude,
          location_name: locationName
        }
      });

      console.log('Azure ML 응답:', response.data);
      setAzureMLResult(response.data);

      // 테스트 기록에 추가
      const testRecord = {
        id: Date.now(),
        timestamp: new Date().toLocaleString(),
        locationName: locationName,
        coordinates: { latitude, longitude },
        success: response.data.success,
        result: response.data
      };
      
      setTestHistory(prev => [testRecord, ...prev.slice(0, 4)]); // 최근 5개만 유지

      if (response.data.success) {
        toast.success(`${locationName} Azure ML 분석 완료!`);
      } else {
        toast.error(`분석 실패: ${response.data.error || response.data.message}`);
      }

    } catch (error) {
      console.error('Azure ML 테스트 오류:', error);
      toast.error('Azure ML 테스트 실패: ' + (error.response?.data?.detail || error.message));
      
      setAzureMLResult({
        success: false,
        error: error.response?.data?.detail || error.message
      });
    } finally {
      setLoading(false);
    }
  };

  // 현재 위치로 테스트
  const testCurrentLocation = () => {
    if (!currentLocation) {
      toast.error('현재 위치를 먼저 확인해주세요.');
      return;
    }

    runAzureMLTest(
      currentLocation.latitude,
      currentLocation.longitude,
      '현재 위치'
    );
  };

  // 미리 정의된 위치로 테스트
  const testPredefinedLocation = (location) => {
    runAzureMLTest(location.lat, location.lng, location.name);
  };

  // 위험도 색상 결정
  const getRiskColor = (category) => {
    switch(category) {
      case '최고위험': return '#ff1744';
      case '상위험': return '#ff5722';
      case '중위험': return '#ff9800';
      case '하위험': return '#4caf50';
      case '최저위험': return '#2e7d32';
      default: return '#9e9e9e';
    }
  };

  // 결과 카드 렌더링
  const renderResultCard = (result) => {
    if (!result) return null;

    if (!result.success) {
      return (
        <div className="result-card error-card">
          <h3>❌ 분석 실패</h3>
          <p><strong>오류:</strong> {result.error || result.message}</p>
          <p>서버 콘솔을 확인하여 자세한 오류 정보를 확인하세요.</p>
        </div>
      );
    }

    const azureResult = result.azure_ml_result;
    const testInfo = result.test_info;

    return (
      <div className="result-card success-card">
        <h3>✅ Azure ML 분석 결과</h3>
        
        <div className="result-header">
          <h4>📍 {testInfo.location_name}</h4>
          <p>좌표: ({testInfo.coordinates.latitude.toFixed(6)}, {testInfo.coordinates.longitude.toFixed(6)})</p>
          <p>분석 반경: {testInfo.analysis_radius_km * 1000}m</p>
        </div>

        {azureResult && (
          <div className="analysis-result">
            <div className="risk-score-display">
              <div 
                className="risk-badge"
                style={{ 
                  backgroundColor: getRiskColor(azureResult.predicted_category),
                  color: 'white'
                }}
              >
                <span className="risk-category">{azureResult.predicted_category}</span>
                <span className="confidence">신뢰도: {azureResult.confidence}</span>
              </div>
            </div>

            <div className="probabilities-section">
              <h5>📊 위험도별 확률:</h5>
              <div className="probabilities-grid">
                {Object.entries(azureResult.probabilities).map(([level, probability]) => (
                  <div key={level} className="probability-item">
                    <span className="level-name">{level}:</span>
                    <div className="probability-bar">
                      <div 
                        className="bar-fill"
                        style={{ 
                          width: probability,
                          backgroundColor: getRiskColor(level)
                        }}
                      />
                      <span className="probability-text">{probability}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="feature-summary">
              <h5>🔍 분석 요약:</h5>
              <div className="summary-grid">
                <div className="summary-item">
                  <span className="label">🚧 주변 공사장:</span>
                  <span className="value">{azureResult.feature_summary.constructions}개</span>
                </div>
                <div className="summary-item">
                  <span className="label">🕳️ 위험 지역:</span>
                  <span className="value">{azureResult.feature_summary.risk_zones}개</span>
                </div>
                <div className="summary-item">
                  <span className="label">👥 일일 유동인구:</span>
                  <span className="value">{azureResult.feature_summary.population.toLocaleString()}명</span>
                </div>
                <div className="summary-item">
                  <span className="label">🎯 위험 점수:</span>
                  <span className="value">{azureResult.feature_summary.risk_score.toFixed(1)}/100</span>
                </div>
              </div>
            </div>
          </div>
        )}

        <div className="console-note">
          <p>💡 <strong>상세 분석 과정</strong>은 브라우저 개발자 도구의 콘솔과 서버 터미널에서 확인할 수 있습니다.</p>
        </div>
      </div>
    );
  };

  return (
    <div className="azure-ml-test">
      <div className="page-header">
        <h1>🤖 Azure ML 위험도 분석 테스트</h1>
        <p>현재 위치 또는 특정 위치의 싱크홀 위험도를 Azure Machine Learning으로 분석합니다.</p>
      </div>

      <div className="test-container">
        {/* 현재 위치 정보 */}
        <div className="location-section">
          <h2>📍 현재 위치 정보</h2>
          {currentLocation ? (
            <div className="location-info">
              <p><strong>위도:</strong> {currentLocation.latitude.toFixed(6)}</p>
              <p><strong>경도:</strong> {currentLocation.longitude.toFixed(6)}</p>
              <button 
                onClick={getCurrentLocation} 
                className="btn btn-secondary"
                disabled={loading}
              >
                🔄 위치 새로고침
              </button>
            </div>
          ) : (
            <div className="location-loading">
              <p>📍 위치 정보를 가져오는 중...</p>
              <button onClick={getCurrentLocation} className="btn btn-primary">
                📍 위치 권한 요청
              </button>
            </div>
          )}
        </div>

        {/* 테스트 버튼들 */}
        <div className="test-buttons-section">
          <h2>🧪 테스트 실행</h2>
          <div className="test-buttons">
            <button
              onClick={testCurrentLocation}
              disabled={loading || !currentLocation}
              className="btn btn-primary test-btn"
            >
              {loading ? '🔄 분석 중...' : '📍 현재 위치로 테스트'}
            </button>

            <button
              onClick={() => testPredefinedLocation({
                name: '강남역',
                lat: 37.4979,
                lng: 127.0276
              })}
              disabled={loading}
              className="btn btn-secondary test-btn"
            >
              🏢 강남역으로 테스트
            </button>

            <button
              onClick={() => testPredefinedLocation({
                name: '서울시청',
                lat: 37.5665,
                lng: 126.9780
              })}
              disabled={loading}
              className="btn btn-secondary test-btn"
            >
              🏛️ 서울시청으로 테스트
            </button>

            <button
              onClick={() => testPredefinedLocation({
                name: '홍대입구역',
                lat: 37.5572,
                lng: 126.9245
              })}
              disabled={loading}
              className="btn btn-secondary test-btn"
            >
              🎉 홍대입구역으로 테스트
            </button>
          </div>
        </div>

        {/* 분석 결과 */}
        <div className="result-section">
          <h2>📊 분석 결과</h2>
          {loading ? (
            <div className="loading-display">
              <div className="loading-spinner"></div>
              <p>🤖 Azure ML로 위험도 분석 중...</p>
              <p>잠시만 기다려주세요.</p>
            </div>
          ) : (
            renderResultCard(azureMLResult)
          )}
        </div>

        {/* 테스트 기록 */}
        {testHistory.length > 0 && (
          <div className="history-section">
            <h2>📝 최근 테스트 기록</h2>
            <div className="history-list">
              {testHistory.map((record) => (
                <div key={record.id} className="history-item">
                  <div className="history-header">
                    <span className="location-name">{record.locationName}</span>
                    <span className="timestamp">{record.timestamp}</span>
                    <span className={`status ${record.success ? 'success' : 'error'}`}>
                      {record.success ? '✅' : '❌'}
                    </span>
                  </div>
                  <div className="history-details">
                    <span>좌표: ({record.coordinates.latitude.toFixed(4)}, {record.coordinates.longitude.toFixed(4)})</span>
                    {record.success && record.result.azure_ml_result && (
                      <span>결과: {record.result.azure_ml_result.predicted_category}</span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* 사용 안내 */}
        <div className="usage-guide">
          <h2>💡 사용 안내</h2>
          <div className="guide-content">
            <h3>🔧 개발자 도구 확인</h3>
            <p>더 자세한 분석 과정을 보려면:</p>
            <ol>
              <li><strong>브라우저 개발자 도구</strong> 열기 (F12)</li>
              <li><strong>Console 탭</strong>에서 클라이언트 로그 확인</li>
              <li><strong>서버 터미널</strong>에서 상세한 분석 과정 확인</li>
            </ol>
            
            <h3>📊 결과 해석</h3>
            <ul>
              <li><strong>최고위험/상위험:</strong> 즉시 해당 지역 회피 권장</li>
              <li><strong>중위험:</strong> 주의하여 이동</li>
              <li><strong>하위험/최저위험:</strong> 비교적 안전</li>
            </ul>

            <h3>⚙️ 기술 정보</h3>
            <ul>
              <li><strong>분석 반경:</strong> 100m (0.1km)</li>
              <li><strong>데이터 소스:</strong> 공사장, 싱크홀, 유동인구, 강수량</li>
              <li><strong>ML 모델:</strong> Azure Machine Learning Studio</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
};

export default AzureMLTest;