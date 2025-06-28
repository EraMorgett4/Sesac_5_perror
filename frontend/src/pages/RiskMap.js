import React, { useState, useEffect } from "react";
import { MapContainer, TileLayer, Marker, Popup, Circle } from "react-leaflet";
import L from "leaflet";
import axios from "axios";
import { toast } from "react-toastify";
import ConstructionZoneLayer from "../components/ConstructionZoneLayer";

// Leaflet 기본 아이콘 설정
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: require("leaflet/dist/images/marker-icon-2x.png"),
  iconUrl: require("leaflet/dist/images/marker-icon.png"),
  shadowUrl: require("leaflet/dist/images/marker-shadow.png"),
});

// 위험도별 색상 설정
const getRiskColor = (risk) => {
  if (risk >= 0.8) return "#ff0000"; // 매우 위험 - 빨간색
  if (risk >= 0.6) return "#ff8800"; // 위험 - 주황색
  if (risk >= 0.4) return "#ffaa00"; // 보통 - 노란색
  if (risk >= 0.2) return "#88aa00"; // 낮음 - 연두색
  return "#00aa00"; // 안전 - 초록색
};

// 위험도별 아이콘 생성
const createRiskIcon = (risk) => {
  const color = getRiskColor(risk);
  const size = Math.max(20, Math.min(40, 20 + risk * 20)); // 20-40px

  return L.divIcon({
    html: `
      <div style="
        background-color: ${color};
        width: ${size}px;
        height: ${size}px;
        border-radius: 50%;
        border: 3px solid white;
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: bold;
        color: white;
        font-size: 12px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.3);
      ">
        ⚠️
      </div>
    `,
    className: "risk-marker",
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
  });
};

const RiskMap = () => {
  const [riskZones, setRiskZones] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showRiskZones, setShowRiskZones] = useState(true);
  const [showConstructions, setShowConstructions] = useState(true);
  const [constructionFilter, setConstructionFilter] = useState("all"); // 'all', 'active', 'completed', 'planned'
  const [mapCenter] = useState([37.5665, 126.978]); // 서울 중심

  useEffect(() => {
    fetchRiskZones();
  }, []);

  const fetchRiskZones = async () => {
    try {
      setLoading(true);
      const response = await axios.get("/risk-zones");
      setRiskZones(response.data.zones || []);
    } catch (error) {
      console.error("위험지역 정보 로드 실패:", error);
      toast.error("위험지역 정보를 불러올 수 없습니다.");
    } finally {
      setLoading(false);
    }
  };

  const getRiskLevel = (risk) => {
    if (risk >= 0.8) return "매우 위험";
    if (risk >= 0.6) return "위험";
    if (risk >= 0.4) return "보통";
    if (risk >= 0.2) return "낮음";
    return "안전";
  };

  if (loading) {
    return (
      <div className="risk-map-container">
        <p>지도 정보를 불러오는 중...</p>
        <div className="loading-spinner">
          <div className="spinner"></div>
        </div>
      </div>
    );
  }

  return (
    <div className="risk-map-container">
      <div className="map-header">
        <h2>서울시 싱크홀 위험지도</h2>
        <div className="map-controls">
          {/* 레이어 토글 컨트롤 */}
          <div className="layer-controls">
            <label>
              <input type="checkbox" checked={showRiskZones} onChange={(e) => setShowRiskZones(e.target.checked)} />
              싱크홀 위험지역 표시
            </label>

            <label>
              <input type="checkbox" checked={showConstructions} onChange={(e) => setShowConstructions(e.target.checked)} />
              공사지역 표시
            </label>
          </div>

          {/* 공사 필터 */}
          {showConstructions && (
            <div className="construction-filter">
              <label>공사 상태 필터:</label>
              <select value={constructionFilter} onChange={(e) => setConstructionFilter(e.target.value)}>
                <option value="all">전체</option>
                <option value="active">진행중만</option>
                <option value="completed">완료됨</option>
                <option value="planned">예정됨</option>
              </select>
            </div>
          )}
        </div>
      </div>

      <div className="map-wrapper">
        <MapContainer center={mapCenter} zoom={11} style={{ height: "600px", width: "100%" }}>
          <TileLayer attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors' url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />

          {/* 싱크홀 위험지역 마커 */}
          {showRiskZones &&
            riskZones.map((zone, index) => (
              <React.Fragment key={`risk-${index}`}>
                <Marker position={[zone.lat, zone.lng]} icon={createRiskIcon(zone.risk)}>
                  <Popup>
                    <div style={{ minWidth: "200px" }}>
                      <h4 style={{ color: getRiskColor(zone.risk), margin: "0 0 10px 0" }}>⚠️ 싱크홀 위험지역</h4>
                      <p>
                        <strong>지역:</strong> {zone.name}
                      </p>
                      <p>
                        <strong>위험도:</strong> {(zone.risk * 100).toFixed(1)}% ({getRiskLevel(zone.risk)})
                      </p>
                      <p>
                        <strong>좌표:</strong> {zone.lat.toFixed(6)}, {zone.lng.toFixed(6)}
                      </p>

                      <div
                        style={{
                          background: "#f5f5f5",
                          padding: "8px",
                          borderRadius: "4px",
                          marginTop: "10px",
                          fontSize: "12px",
                        }}>
                        <strong>안전 수칙:</strong>
                        <br />
                        {zone.risk >= 0.8 ? "즉시 우회 권장" : zone.risk >= 0.6 ? "주의 깊게 통행" : zone.risk >= 0.4 ? "일반적인 주의" : "정상 통행 가능"}
                      </div>
                    </div>
                  </Popup>
                </Marker>

                {/* 위험지역 주변 원형 표시 */}
                <Circle
                  center={[zone.lat, zone.lng]}
                  radius={zone.risk * 200 + 50} // 위험도에 따라 반경 조정
                  color={getRiskColor(zone.risk)}
                  fillColor={getRiskColor(zone.risk)}
                  fillOpacity={0.1}
                  weight={2}
                />
              </React.Fragment>
            ))}

          {/* 공사지역 레이어 */}
          <ConstructionZoneLayer showConstructions={showConstructions} filterStatus={constructionFilter} />
        </MapContainer>

        {/* 지도 범례 */}
        <div className="map-legend">
          <h4>범례</h4>

          {showRiskZones && (
            <div className="legend-section">
              <h5>🕳️ 싱크홀 위험도</h5>
              <div className="legend-item">
                <span className="legend-color" style={{ backgroundColor: "#ff0000" }}></span>
                매우 위험 (80% 이상)
              </div>
              <div className="legend-item">
                <span className="legend-color" style={{ backgroundColor: "#ff8800" }}></span>
                위험 (60-80%)
              </div>
              <div className="legend-item">
                <span className="legend-color" style={{ backgroundColor: "#ffaa00" }}></span>
                보통 (40-60%)
              </div>
              <div className="legend-item">
                <span className="legend-color" style={{ backgroundColor: "#88aa00" }}></span>
                낮음 (20-40%)
              </div>
              <div className="legend-item">
                <span className="legend-color" style={{ backgroundColor: "#00aa00" }}></span>
                안전 (20% 미만)
              </div>
            </div>
          )}

          {showConstructions && (
            <div className="legend-section">
              <h5>🚧 공사 현황</h5>
              <div className="legend-item">
                <span style={{ fontSize: "16px" }}>🚧</span>
                진행중 공사
              </div>
              <div className="legend-item">
                <span style={{ fontSize: "16px" }}>✅</span>
                완료된 공사
              </div>
              <div className="legend-item">
                <span style={{ fontSize: "16px" }}>📅</span>
                예정된 공사
              </div>
            </div>
          )}
        </div>
      </div>

      {/* 통계 정보 */}
      <div className="map-stats">
        <div className="stats-grid">
          <div className="stat-card">
            <h4>전체 위험지역</h4>
            <p className="stat-number">{riskZones.length}</p>
            <small>싱크홀 위험지역</small>
          </div>
          <div className="stat-card">
            <h4>고위험 지역</h4>
            <p className="stat-number">{riskZones.filter((z) => z.risk >= 0.8).length}</p>
            <small>80% 이상</small>
          </div>
          <div className="stat-card">
            <h4>중위험 지역</h4>
            <p className="stat-number">{riskZones.filter((z) => z.risk >= 0.6 && z.risk < 0.8).length}</p>
            <small>60-80%</small>
          </div>
        </div>
      </div>

      <style jsx>{`
        .risk-map-container {
          padding: 20px;
          max-width: 1200px;
          margin: 0 auto;
        }

        .map-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 20px;
          flex-wrap: wrap;
          gap: 15px;
        }

        .map-header h2 {
          margin: 0;
          color: #333;
        }

        .map-controls {
          display: flex;
          gap: 20px;
          align-items: center;
          flex-wrap: wrap;
        }

        .layer-controls {
          display: flex;
          gap: 15px;
          flex-direction: column;
        }

        .layer-controls label {
          display: flex;
          align-items: center;
          gap: 5px;
          font-size: 14px;
          cursor: pointer;
        }

        .construction-filter {
          display: flex;
          align-items: center;
          gap: 8px;
          font-size: 14px;
        }

        .construction-filter select {
          padding: 4px 8px;
          border: 1px solid #ddd;
          border-radius: 4px;
          font-size: 14px;
        }

        .map-wrapper {
          position: relative;
          border-radius: 8px;
          overflow: hidden;
          box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        }

        .map-legend {
          position: absolute;
          top: 10px;
          right: 10px;
          background: white;
          padding: 15px;
          border-radius: 8px;
          box-shadow: 0 2px 10px rgba(0, 0, 0, 0.15);
          z-index: 1000;
          max-width: 200px;
        }

        .map-legend h4 {
          margin: 0 0 10px 0;
          font-size: 16px;
          color: #333;
        }

        .legend-section {
          margin-bottom: 15px;
        }

        .legend-section h5 {
          margin: 0 0 8px 0;
          font-size: 14px;
          color: #666;
        }

        .legend-item {
          display: flex;
          align-items: center;
          gap: 8px;
          margin-bottom: 4px;
          font-size: 12px;
        }

        .legend-color {
          width: 16px;
          height: 16px;
          border-radius: 50%;
          border: 2px solid white;
          box-shadow: 0 1px 3px rgba(0, 0, 0, 0.3);
        }

        .map-stats {
          margin-top: 20px;
        }

        .stats-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
          gap: 15px;
        }

        .stat-card {
          background: white;
          padding: 20px;
          border-radius: 8px;
          box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
          text-align: center;
        }

        .stat-card h4 {
          margin: 0 0 10px 0;
          color: #666;
          font-size: 14px;
          font-weight: 500;
        }

        .stat-number {
          font-size: 28px;
          font-weight: bold;
          color: #333;
          margin: 0 0 5px 0;
        }

        .stat-card small {
          color: #999;
          font-size: 12px;
        }

        .loading-spinner {
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          height: 400px;
        }

        .spinner {
          width: 40px;
          height: 40px;
          border: 4px solid #f3f3f3;
          border-top: 4px solid #3498db;
          border-radius: 50%;
          animation: spin 1s linear infinite;
          margin-bottom: 20px;
        }

        @keyframes spin {
          0% {
            transform: rotate(0deg);
          }
          100% {
            transform: rotate(360deg);
          }
        }

        @media (max-width: 768px) {
          .risk-map-container {
            padding: 10px;
          }

          .map-header {
            flex-direction: column;
            align-items: flex-start;
          }

          .map-controls {
            width: 100%;
            justify-content: space-between;
          }

          .layer-controls {
            flex-direction: row;
            gap: 10px;
          }

          .map-legend {
            position: relative;
            top: 0;
            right: 0;
            margin-top: 15px;
            max-width: none;
          }

          .stats-grid {
            grid-template-columns: 1fr;
          }
        }
      `}</style>
    </div>
  );
};

export default RiskMap;
