

import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import { toast } from 'react-toastify';
import '../styles/VoiceNavigation.css';

const AzureVoiceNavigation = ({ onRouteFound, onLocationUpdate, onServiceShutdown }) => {
  const [isActive, setIsActive] = useState(false);
  const [status, setStatus] = useState('대기 중');
  const [isListening, setIsListening] = useState(false);
  const [pendingDestination, setPendingDestination] = useState(null); // 확인 대기 중인 목적지
  
  const recognitionRef = useRef(null);
  const audioQueueRef = useRef([]);
  const isSpeakingRef = useRef(false);
  const isMountedRef = useRef(true);
  const currentLocationRef = useRef(null);

  useEffect(() => {
    isMountedRef.current = true;
    if (isActive) {
      log('음성 안내 서비스 시작');
      setupRecognition();
      startNavigationSequence();
    }
    return () => {
      if (isActive) {
        log('음성 안내 서비스 정리');
        if (recognitionRef.current) recognitionRef.current.stop();
        isSpeakingRef.current = false;
        audioQueueRef.current = [];
        onServiceShutdown?.();
      }
      isMountedRef.current = false;
    };
  }, [isActive]);

  const log = (message) => console.log(`[INFO] ${new Date().toLocaleTimeString()}: ${message}`);

  const handleStartService = () => setIsActive(true);
  const handleStopService = () => {
    setIsActive(false);
    setStatus('안내 종료됨');
    setPendingDestination(null);
    toast.info("음성 안내가 종료되었습니다.");
  };
  
  const startNavigationSequence = async () => {
    setStatus('현재 위치 확인 중...');
    const location = await getCurrentLocation();
    if (location && isMountedRef.current) {
      await speak('현재 위치를 확인했습니다. 목적지를 말씀해 주세요.');
      if (isMountedRef.current) startListening();
    } else if (isMountedRef.current) {
      await speak('위치 정보를 가져올 수 없습니다.');
      handleStopService();
    }
  };

  const getCurrentLocation = () => new Promise(resolve => {
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const loc = { lat: pos.coords.latitude, lng: pos.coords.longitude };
        currentLocationRef.current = loc;
        onLocationUpdate?.(loc);
        resolve(loc);
      },
      () => { toast.error('위치 권한을 허용해주세요.'); resolve(null); },
      { enableHighAccuracy: true, timeout: 10000 }
    );
  });

  const speak = (text) => new Promise(resolve => {
    audioQueueRef.current.push({ text, resolve });
    if (!isSpeakingRef.current) processAudioQueue();
  });

  const processAudioQueue = async () => {
    if (isSpeakingRef.current || audioQueueRef.current.length === 0) return;
    isSpeakingRef.current = true;
    const { text, resolve } = audioQueueRef.current.shift();
    if (!isMountedRef.current) return;
    setStatus(`안내: "${text}"`);
    try {
      const response = await axios.post('/api/tts', `text=${encodeURIComponent(text.trim())}`, {
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        timeout: 15000,
      });
      const audioData = response.data.audio_data;
      const audioBlob = new Blob([Uint8Array.from(atob(audioData), c => c.charCodeAt(0))], { type: 'audio/wav' });
      const audio = new Audio(URL.createObjectURL(audioBlob));
      audio.onended = () => {
        isSpeakingRef.current = false;
        if (isMountedRef.current) processAudioQueue();
        resolve();
      };
      audio.play();
    } catch (error) {
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.lang = 'ko-KR';
      utterance.onend = () => {
        isSpeakingRef.current = false;
        if (isMountedRef.current) processAudioQueue();
        resolve();
      };
      window.speechSynthesis.speak(utterance);
    }
  };

  const setupRecognition = () => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      setStatus('음성 인식을 지원하지 않습니다.');
      return;
    }
    const recognition = new SpeechRecognition();
    recognition.lang = 'ko-KR';
    recognition.continuous = false;
    
    recognition.onstart = () => { if(isMountedRef.current) setIsListening(true); };
    recognition.onend = () => { if(isMountedRef.current) setIsListening(false); };
    recognition.onerror = () => { if(isMountedRef.current) setStatus('음성을 인식하지 못했습니다.'); };
    
    recognition.onresult = (event) => {
      if(!isMountedRef.current) return;
      const transcript = event.results[0][0].transcript.trim();
      if (pendingDestination) {
        processConfirmation(transcript);
      } else {
        handleRecognitionResult(transcript);
      }
    };
    recognitionRef.current = recognition;
  };

  // --- 신규 기능: 인식 결과 처리 및 확인 요청 ---
  const handleRecognitionResult = async (transcript) => {
    setPendingDestination(transcript);
    setStatus(`"${transcript}" 맞나요?`);
    await speak(`"${transcript}" 맞나요?`);
    if(isMountedRef.current) startListening();
  };

  // --- 신규 기능: '네/아니오' 답변 처리 ---
  const processConfirmation = async (answer) => {
    const affirmative = ['네', '예', '맞아', '맞아요', '응', '그래'].some(word => answer.includes(word));
    const negative = ['아니', '아니요', '틀려', '틀렸어'].some(word => answer.includes(word));

    if (affirmative) {
        await speak(`네, "${pendingDestination}"(으)로 경로를 찾습니다.`);
        handleDestinationInput(pendingDestination);
        setPendingDestination(null);
    } else if (negative) {
        setPendingDestination(null);
        await speak('죄송합니다. 목적지를 다시 말씀해주세요.');
        if(isMountedRef.current) startListening();
    } else {
        await speak('"네" 또는 "아니오"로 답해주세요.');
        if(isMountedRef.current) startListening();
    }
  };

  const startListening = () => {
    if (recognitionRef.current && !isListening) {
      try {
        recognitionRef.current.start();
      } catch(e) { log('음성 인식 시작 오류'); }
    }
  };

  const handleDestinationInput = async (destinationText) => {
    try {
      const places = await searchDestination(destinationText);
      if (!places || places.length === 0) {
        await speak('목적지를 찾을 수 없습니다. 다시 말씀해 주세요.');
        startListening(); return;
      }
      
      const destCoords = { lat: parseFloat(places[0].y), lng: parseFloat(places[0].x) };
      const routeResponse = await axios.post('/safe-walking-route', {
        start_latitude: currentLocationRef.current.lat,
        start_longitude: currentLocationRef.current.lng,
        end_latitude: destCoords.lat,
        end_longitude: destCoords.lng,
      });

      if (routeResponse.data) {
        onRouteFound?.(routeResponse.data, currentLocationRef.current, destCoords, places[0].place_name);
        await speak(`${places[0].place_name}까지 안내를 시작합니다.`);
        handleStopService();
      } else { throw new Error('경로 데이터가 없습니다.'); }
    } catch (error) {
      await speak('경로를 찾지 못했습니다. 다른 목적지를 말씀해 주세요.');
      startListening();
    }
  };

  const searchDestination = async (query) => {
    try {
      const response = await axios.get('/search-location-combined', { params: { query } });
      return response.data.places || [];
    } catch (error) { return []; }
  };

  return (
    <div className="voice-navigation azure-voice">
      {!isActive ? (
        <div className="voice-controls">
          <button onClick={handleStartService} className="start-voice-btn azure-btn">
            🎤 음성 안내 시작
          </button>
        </div>
      ) : (
        <div className="navigation-status">
          <div className="nav-info">
            <h3>{status}</h3>
            {isListening && <div className="voice-level-meter"><div className="voice-level-bar active"></div><div className="voice-level-bar active"></div><div className="voice-level-bar active"></div></div>}
          </div>

          {/* --- 신규 기능: 확인 버튼 UI --- */}
          {pendingDestination && !isListening && (
            <div className="confirmation-dialog">
              <p>"{pendingDestination}"으로 알아들었습니다. 맞나요?</p>
              <div className="confirmation-buttons">
                <button onClick={() => processConfirmation('네')} className="confirm-btn yes-btn">✔️ 네</button>
                <button onClick={() => processConfirmation('아니오')} className="confirm-btn no-btn">❌ 아니오</button>
              </div>
            </div>
          )}

          <button onClick={handleStopService} className="stop-nav-btn">
            🚫 안내 종료
          </button>
        </div>
      )}
    </div>
  );
};

export default AzureVoiceNavigation;