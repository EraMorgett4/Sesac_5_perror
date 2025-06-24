// App.js
import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { ToastContainer } from 'react-toastify';
import 'react-toastify/dist/ReactToastify.css';
import 'leaflet/dist/leaflet.css';

// AuthProvider 추가
import AuthProvider from './contexts/AuthContext';
import Navbar from './components/Navbar';
import Login from './pages/Login';
import Register from './pages/Register';
import Dashboard from './pages/Dashboard';
import RiskMap from './pages/RiskMap';
import RouteSearch from './pages/RouteSearch';
import ReportChatbot from './pages/ReportChatbot'; // 새로 추가
import './styles/App.css';
import VoiceAssistantWidget from './components/VoiceAssistantWidget';

function App() {
  return (
    <AuthProvider>
      <Router future={{ v7_startTransition: true }}>
        <div className="App">
          <Navbar />
          <main className="main-content">
            <Routes>
              <Route path="/login" element={<Login />} />
              <Route path="/register" element={<Register />} />
              <Route path="/dashboard" element={<Dashboard />} />
              <Route path="/map" element={<RiskMap />} />
              <Route path="/route" element={<RouteSearch />} />
              <Route path="/report" element={<ReportChatbot />} /> {/* 신고 페이지 추가 */}
              
              

              <Route path="/" element={<Navigate to="/dashboard" />} />
            </Routes>
            <VoiceAssistantWidget />
          </main>
          
          <ToastContainer position="top-right" autoClose={3000} />
        </div>
      </Router>
    </AuthProvider>
  );
}

export default App;