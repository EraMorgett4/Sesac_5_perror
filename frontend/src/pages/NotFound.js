// pages/NotFound.js
import React from 'react';
import { Link } from 'react-router-dom';
import '../styles/NotFound.css'; // 스타일링 파일 (선택사항)

const NotFound = () => {
  return (
    <div className="not-found-container">
      <div className="not-found-content">
        <h1>404</h1>
        <h2>페이지를 찾을 수 없습니다</h2>
        <p>요청하신 페이지가 존재하지 않거나 이동되었을 수 있습니다.</p>
        <div className="not-found-actions">
          <Link to="/dashboard" className="btn btn-primary">
            대시보드로 이동
          </Link>
          <Link to="/" className="btn btn-secondary">
            홈으로 이동
          </Link>
        </div>
      </div>
    </div>
  );
};

export default NotFound;