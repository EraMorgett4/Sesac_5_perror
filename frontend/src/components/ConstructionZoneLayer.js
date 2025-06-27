// ConstructionZoneLayer.js 개선된 버전
import React, { useEffect, useState } from 'react';
import { Marker, Popup, useMap } from 'react-leaflet';
import L from 'leaflet';
import axios from 'axios';

// 공사 상태별 아이콘 생성
const createConstructionIcon = (status, riskLevel) => {
  let color = '#orange';
  let symbol = '🚧';
  
  switch(status) {
    case '진행중':
      color = riskLevel > 0.7 ? '#ff4444' : '#ff8800';
      symbol = '🚧';
      break;
    case '완료':
      color = '#888888';
      symbol = '✅';
      break;
    case '예정':
      color = '#4488ff';
      symbol = '📅';
      break;
    default:
      color = '#999999';
      symbol = '❓';
  }
  
  return L.divIcon({
    html: `
      <div style="
        background-color: ${color};
        width: 25px;
        height: 25px;
        border-radius: 50%;
        border: 2px solid white;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 12px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.3);
      ">
        ${symbol}
      </div>
    `,
    className: 'construction-marker',
    iconSize: [25, 25],
    iconAnchor: [12, 12]
  });
};

const ConstructionZoneLayer = ({ showConstructions = true, filterStatus = 'all' }) => {
  const [constructions, setConstructions] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const map = useMap();

  useEffect(() => {
    console.log(`🏗️ ConstructionZoneLayer 효과 실행:`, {
      showConstructions,
      filterStatus
    });
    
    if (showConstructions) {
      fetchConstructions();
    } else {
      console.log('🚫 공사장 표시 비활성화됨');
      setConstructions([]);
    }
  }, [showConstructions, filterStatus]);

  const fetchConstructions = async () => {
    setLoading(true);
    setError(null);
    
    try {
      console.log('📡 공사장 데이터 요청 시작...');
      
      let url = '/construction-zones';
      if (filterStatus === 'active') {
        url = '/construction-zones/active';
      }
      
      console.log(`📡 요청 URL: ${url}`);
      
      const response = await axios.get(url);
      console.log('📡 공사장 API 원본 응답:', response.data);
      
      let allConstructions = response.data.zones || [];
      console.log(`📊 전체 공사장 수: ${allConstructions.length}건`);
      
      // 상태별 필터링
      let filteredConstructions = allConstructions;
      if (filterStatus !== 'all') {
        const statusMap = {
          'active': '진행중',
          'completed': '완료',
          'planned': '예정'
        };
        
        const targetStatus = statusMap[filterStatus] || filterStatus;
        filteredConstructions = allConstructions.filter(
          construction => construction.status === targetStatus
        );
        
        console.log(`🔧 필터링 결과 (${targetStatus}): ${filteredConstructions.length}건`);
      }
      
      // 좌표 유효성 검사
      const validConstructions = filteredConstructions.filter(construction => {
        const hasValidCoords = construction.lat && construction.lng && 
          !isNaN(construction.lat) && !isNaN(construction.lng);
        
        if (!hasValidCoords) {
          console.warn('⚠️ 유효하지 않은 좌표:', construction);
        }
        
        return hasValidCoords;
      });
      
      console.log(`✅ 유효한 좌표를 가진 공사장: ${validConstructions.length}건`);
      
      if (validConstructions.length > 0) {
        console.log('📋 공사장 샘플 (처음 3개):', validConstructions.slice(0, 3));
        
        // 상태별 통계
        const statusCounts = {};
        validConstructions.forEach(c => {
          statusCounts[c.status] = (statusCounts[c.status] || 0) + 1;
        });
        console.log('📊 상태별 통계:', statusCounts);
      }
      
      setConstructions(validConstructions);
      
    } catch (err) {
      console.error('❌ 공사정보 로드 실패:', err);
      console.error('❌ 오류 상세:', err.response?.data || err.message);
      setError('공사정보를 불러올 수 없습니다.');
    } finally {
      setLoading(false);
    }
  };

  const getStatusColor = (status) => {
    switch(status) {
      case '진행중': return '#ff4444';
      case '완료': return '#888888';
      case '예정': return '#4488ff';
      default: return '#999999';
    }
  };

  const formatAddress = (address) => {
    return address.length > 30 ? address.substring(0, 30) + '...' : address;
  };

  // 컴포넌트 렌더링 로그
  console.log(`🖼️ ConstructionZoneLayer 렌더링:`, {
    showConstructions,
    constructionsCount: constructions.length,
    loading,
    error
  });

  if (!showConstructions) {
    console.log('🚫 공사장 표시 비활성화 - 컴포넌트 숨김');
    return null;
  }

  if (loading) {
    console.log('⏳ 공사장 데이터 로딩 중...');
    return (
      <div style={{
        position: 'absolute',
        top: '10px',
        right: '10px',
        background: 'white',
        padding: '10px',
        borderRadius: '5px',
        boxShadow: '0 2px 5px rgba(0,0,0,0.3)',
        zIndex: 1000
      }}>
        🚧 공사정보 로딩 중...
      </div>
    );
  }

  if (error) {
    console.log('❌ 공사장 데이터 로드 오류 표시');
    return (
      <div style={{
        position: 'absolute',
        top: '10px',
        right: '10px',
        background: '#ffebee',
        color: '#c62828',
        padding: '10px',
        borderRadius: '5px',
        boxShadow: '0 2px 5px rgba(0,0,0,0.3)',
        zIndex: 1000
      }}>
        ❌ {error}
      </div>
    );
  }

  if (constructions.length === 0) {
    console.log('📍 표시할 공사장이 없음');
    return (
      <div style={{
        position: 'absolute',
        bottom: '20px',
        left: '20px',
        background: 'white',
        padding: '10px',
        borderRadius: '5px',
        boxShadow: '0 2px 5px rgba(0,0,0,0.3)',
        zIndex: 1000,
        fontSize: '12px'
      }}>
        <div style={{ fontWeight: 'bold', marginBottom: '5px' }}>🚧 공사정보</div>
        <div>표시할 공사장이 없습니다.</div>
      </div>
    );
  }

  console.log(`🗺️ 지도에 공사장 마커 표시: ${constructions.length}개`);

  return (
    <>
      {constructions.map((construction, index) => {
        console.log(`📍 마커 생성 ${index + 1}/${constructions.length}:`, {
          id: construction.id,
          lat: construction.lat,
          lng: construction.lng,
          status: construction.status
        });
        
        return (
          <Marker
            key={construction.id || `construction-${index}`}
            position={[construction.lat, construction.lng]}
            icon={createConstructionIcon(construction.status, construction.risk_level)}
          >
            <Popup>
              <div style={{ minWidth: '200px' }}>
                <h4 style={{ 
                  margin: '0 0 10px 0', 
                  color: getStatusColor(construction.status),
                  display: 'flex',
                  alignItems: 'center',
                  gap: '5px'
                }}>
                  🚧 {construction.type || '도로굴착공사'}
                </h4>
                
                <div style={{ marginBottom: '8px' }}>
                  <strong>위치:</strong> {formatAddress(construction.address)}
                </div>
                
                <div style={{ marginBottom: '8px' }}>
                  <strong>상태:</strong>
                  <span style={{
                    background: getStatusColor(construction.status),
                    color: 'white',
                    padding: '2px 6px',
                    borderRadius: '3px',
                    fontSize: '12px',
                    marginLeft: '5px'
                  }}>
                    {construction.status}
                  </span>
                </div>
                
                <div style={{ marginBottom: '8px' }}>
                  <strong>위험도:</strong>
                  <div style={{
                    background: '#f0f0f0',
                    borderRadius: '10px',
                    height: '6px',
                    marginTop: '3px'
                  }}>
                    <div style={{
                      background: construction.risk_level > 0.7 ? '#ff4444' : 
                                 construction.risk_level > 0.4 ? '#ff8800' : '#44aa44',
                      width: `${construction.risk_level * 100}%`,
                      height: '100%',
                      borderRadius: '10px'
                    }}></div>
                  </div>
                  <small>{Math.round(construction.risk_level * 100)}%</small>
                </div>
                
                {construction.estimated_completion && (
                  <div style={{ marginBottom: '8px' }}>
                    <strong>완료예정:</strong> {construction.estimated_completion}
                  </div>
                )}
                
                <div style={{
                  fontSize: '11px',
                  color: '#666',
                  borderTop: '1px solid #eee',
                  paddingTop: '5px',
                  marginTop: '8px'
                }}>
                  ID: {construction.id}
                </div>
              </div>
            </Popup>
          </Marker>
        );
      })}
      
      {/* 범례 */}
      <div style={{
        position: 'absolute',
        bottom: '20px',
        left: '20px',
        background: 'white',
        padding: '10px',
        borderRadius: '5px',
        boxShadow: '0 2px 5px rgba(0,0,0,0.3)',
        zIndex: 1000,
        fontSize: '12px'
      }}>
        <div style={{ fontWeight: 'bold', marginBottom: '5px' }}>🚧 공사정보</div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '5px', marginBottom: '3px' }}>
          <span style={{ color: '#ff4444' }}>🚧</span> 진행중 ({constructions.filter(c => c.status === '진행중').length}개)
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '5px', marginBottom: '3px' }}>
          <span style={{ color: '#888888' }}>✅</span> 완료 ({constructions.filter(c => c.status === '완료').length}개)
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
          <span style={{ color: '#4488ff' }}>📅</span> 예정 ({constructions.filter(c => c.status === '예정').length}개)
        </div>
        <div style={{ marginTop: '5px', fontSize: '10px', color: '#666' }}>
          총 {constructions.length}건 표시 중
        </div>
      </div>
    </>
  );
};

export default ConstructionZoneLayer;