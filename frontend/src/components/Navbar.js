// Navbar.js
import React from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import '../styles/Navbar.css';

const Navbar = () => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/');
  };

  return (
    <nav className="navbar">
      <div className="nav-container">
        <Link to="/" className="nav-logo">
          🕳️ Seoul Sinkhole Predictor
        </Link>
        
        <div className="nav-menu">
          <Link to="/dashboard" className="nav-link">대시보드</Link>
          <Link to="/map" className="nav-link">위험지도</Link>
          <Link to="/route" className="nav-link">안전경로</Link>
          <Link to="/report" className="nav-link report-link">🚨 신고하기</Link>

         
          
          {user ? (
            // 로그인된 상태
            <>
              <span className="user-info">안녕하세요, {user.name}님</span>
              <button onClick={handleLogout} className="logout-btn">
                로그아웃
              </button>
            </>
          ) : (
            // 로그인되지 않은 상태
            <>
              <Link to="/login" className="nav-link">로그인</Link>
              <Link to="/register" className="nav-link">회원가입</Link>
            </>
          )}
        </div>
      </div>
    </nav>
  );
};

export default Navbar;