import React, { useState, useEffect } from 'react';
import { MapContainer, TileLayer, CircleMarker, Popup, useMapEvents } from 'react-leaflet';
import { toast } from 'react-toastify';
import axios from 'axios';
import L from 'leaflet';
import '../styles/RiskMap.css';

// Leaflet 아이콘 문제 해결
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
});

const LocationMarker = ({ onLocationFound }) => {
  const [position, setPosition] = useState(null);

  useMapEvents({
    click() {
      if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(
          (pos) => {
            const newPos = [pos.coords.latitude, pos.coords.longitude];
            setPosition(newPos);
            onLocationFound(newPos);
          },
          (error) => {
            toast.error('위치 정보를 가져올 수 없습니다: ' + error.message);
          }
        );
      } else {
        toast.error('위치 서비스를 지원하지 않는 브라우저입니다.');
      }
    },
  });

  return position === null ? null : (
    <CircleMarker center={position} radius={10} color="blue">
      <Popup>현재 위치</Popup>
    </CircleMarker>
  );
};

const RiskMap = () => {
  const [riskZones, setRiskZones] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedLocation, setSelectedLocation] = useState(null);

  useEffect(() => {
    fetchRiskZones();
  }, []);

  const fetchRiskZones = async () => {
    try {
      const response = await axios.get('/risk-zones');
      setRiskZones(response.data.zones);
    } catch (error) {
      console.error('위험지역 조회 에러:', error);
      toast.error('위험지역 데이터를 불러오는데 실패했습니다.');
    } finally {
      setLoading(false);
    }
  };

  const getRiskColor = (risk) => {
    if (risk >= 0.8) return '#ff4444';
    if (risk >= 0.6) return '#ff8800';
    if (risk >= 0.4) return '#ffaa00';
    if (risk >= 0.2) return '#88cc00';
    return '#44cc44';
  };

  const getRiskRadius = (risk) => {
    return Math.max(5, risk * 20);
  };

  if (loading) {
    return <div className="map-loading">지도를 불러오는 중...</div>;
  }

  return (
    <div className="risk-map-container">
      <div className="map-header">
        <div>
          <h1>서울시 싱크홀 위험지도</h1>
          <p>로그인 없이 누구나 이용 가능합니다</p>
        </div>
        <div className="legend">
          <h3>위험도 범례</h3>
          <div className="legend-items">
            <div className="legend-item">
              <div className="legend-color" style={{ backgroundColor: '#ff4444' }}></div>
              <span>매우높음 (80%+)</span>
            </div>
            <div className="legend-item">
              <div className="legend-color" style={{ backgroundColor: '#ff8800' }}></div>
              <span>높음 (60-80%)</span>
            </div>
            <div className="legend-item">
              <div className="legend-color" style={{ backgroundColor: '#ffaa00' }}></div>
              <span>보통 (40-60%)</span>
            </div>
            <div className="legend-item">
              <div className="legend-color" style={{ backgroundColor: '#88cc00' }}></div>
              <span>낮음 (20-40%)</span>
            </div>
            <div className="legend-item">
              <div className="legend-color" style={{ backgroundColor: '#44cc44' }}></div>
              <span>매우낮음 (~20%)</span>
            </div>
          </div>
        </div>
      </div>

      <div className="map-wrapper">
        <MapContainer
          center={[37.5665, 126.9780]}
          zoom={11}
          style={{ height: '100%', width: '100%' }}
        >
          <TileLayer
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          />
          
          <LocationMarker onLocationFound={setSelectedLocation} />
          
          {riskZones.map((zone, index) => (
            <CircleMarker
              key={index}
              center={[zone.lat, zone.lng]}
              radius={getRiskRadius(zone.risk)}
              color={getRiskColor(zone.risk)}
              fillColor={getRiskColor(zone.risk)}
              fillOpacity={0.6}
            >
              <Popup>
                <div className="popup-content">
                  <h4>{zone.name}</h4>
                  <p><strong>위험도:</strong> {(zone.risk * 100).toFixed(1)}%</p>
                  <p><strong>위치:</strong> {zone.lat.toFixed(4)}, {zone.lng.toFixed(4)}</p>
                </div>
              </Popup>
            </CircleMarker>
          ))}
        </MapContainer>
      </div>

      <div className="map-info">
        <h3>지도 사용법</h3>
        <ul>
          <li>지도를 클릭하면 현재 위치를 표시합니다</li>
          <li>빨간색 원일수록 위험도가 높은 지역입니다</li>
          <li>각 위험지역을 클릭하면 상세 정보를 볼 수 있습니다</li>
          <li>총 {riskZones.length}개의 위험지역이 표시되어 있습니다</li>
        </ul>
      </div>
    </div>
  );
};

export default RiskMap;