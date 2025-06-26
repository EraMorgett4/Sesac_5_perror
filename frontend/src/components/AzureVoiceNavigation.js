// frontend/src/components/AzureVoiceNavigation.js - 완전한 파일

import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import { toast } from 'react-toastify';

const AzureVoiceNavigation = ({ onRouteFound, onLocationUpdate, onServiceShutdown }) => {
  const [isListening, setIsListening] = useState(false);
  const [currentLocation, setCurrentLocation] = useState(null);
  const [destination, setDestination] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);
  const [isPlaying, setIsPlaying] = useState(false);
  const [route, setRoute] = useState(null);
  const [step, setStep] = useState('location'); // 'location', 'destination', 'navigation'
  const [navigationIndex, setNavigationIndex] = useState(0);
  const [debugInfo, setDebugInfo] = useState(null);
  
  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);
  const audioRef = useRef(null);
  const streamRef = useRef(null); // ❗️ 스트림을 직접 관리하기 위한 ref 추가

  useEffect(() => {
    getCurrentLocation();
    
    // ❗️ 컴포넌트 언마운트 시 모든 리소스를 확실하게 정리합니다.
    return () => {
      if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
        mediaRecorderRef.current.stop();
      }
      if (streamRef.current) {
        streamRef.current.getTracks().forEach(track => track.stop());
      }
      if (audioRef.current) {
        audioRef.current.src = '';
      }
      if (onServiceShutdown) {
        onServiceShutdown();
      }
    };
  }, [onServiceShutdown]);

  // ❗️ 디버깅을 위해 객체 데이터도 함께 로깅하도록 개선
  const log = (message, type = 'info', data = null) => {
    const timestamp = new Date().toLocaleTimeString('ko-KR');
    const logMessage = `[Azure Voice] ${timestamp}: ${message}`;
    
    const logData = data ? data : '';
    
    switch (type) {
      case 'error':
        console.error(logMessage, logData);
        break;
      case 'success':
        console.log(`✅ ${logMessage}`, logData);
        break;
      default:
        console.log(`ℹ️ ${logMessage}`, logData);
    }
  };

  const getCurrentLocation = () => {
    if (navigator.geolocation) {
      log('현재 위치 확인 중...');
      navigator.geolocation.getCurrentPosition(
        (position) => {
          const location = {
            lat: position.coords.latitude,
            lng: position.coords.longitude
          };
          setCurrentLocation(location);
          onLocationUpdate?.(location);
          log(`📍 현재 위치 확인 성공: ${location.lat}, ${location.lng}`, 'success', { accuracy: position.coords.accuracy });
          speak('현재 위치를 확인했습니다. 목적지를 말씀해 주세요.');
        },
        (error) => {
          log(`❌ 위치 확인 실패: ${error.message}`, 'error', error);
          toast.error('위치 권한을 허용해주세요.');
        },
        { enableHighAccuracy: true, timeout: 10000, maximumAge: 300000 }
      );
    } else {
      log('❌ 브라우저가 위치 서비스를 지원하지 않습니다', 'error');
      toast.error('이 브라우저는 위치 서비스를 지원하지 않습니다.');
    }
  };

  const speak = async (text, voiceName = 'ko-KR-HyunsuMultilingualNeural') => {
    if (!text || text.trim().length === 0) {
      log('❌ TTS: 빈 텍스트입니다', 'error');
      return;
    }

    try {
      setIsPlaying(true);
      log(`🔊 TTS 요청: "${text.slice(0, 50)}${text.length > 50 ? '...' : ''}"`);

      const formData = new FormData();
      formData.append('text', text.trim());
      formData.append('voice_name', voiceName);

      const response = await axios.post('/api/tts', formData, {
        timeout: 15000
      });

      if (response.data.success && response.data.audio_data) {
        log(`✅ TTS 성공`, 'success', { base64_length: response.data.audio_data.length });
        
        const audioBlob = base64ToBlob(response.data.audio_data, 'audio/wav');
        const audioUrl = URL.createObjectURL(audioBlob);
        
        if (audioRef.current) {
          audioRef.current.src = audioUrl;
          await audioRef.current.play();
          log('🎵 오디오 재생 시작', 'success');
        }
      } else {
        throw new Error(response.data.error || 'TTS 응답 데이터가 올바르지 않습니다');
      }
    } catch (error) {
      log(`❌ Azure TTS 오류`, 'error', error);
      
      if (error.response) {
        log(`❌ 응답 상태: ${error.response.status}`, 'error', error.response.data);
      }
      
      log('🔄 Web Speech API로 대체 시도');
      try {
        const utterance = new SpeechSynthesisUtterance(text);
        utterance.lang = 'ko-KR';
        speechSynthesis.speak(utterance);
        log('✅ Web Speech API 재생 성공', 'success');
      } catch (fallbackError) {
        log(`❌ Web Speech API도 실패`, 'error', fallbackError);
        toast.error('음성 안내를 재생할 수 없습니다.');
      }
    } finally {
      setIsPlaying(false);
    }
  };

  const base64ToBlob = (base64, mimeType) => {
    const byteCharacters = atob(base64);
    const byteNumbers = new Array(byteCharacters.length);
    for (let i = 0; i < byteCharacters.length; i++) {
      byteNumbers[i] = byteCharacters.charCodeAt(i);
    }
    const byteArray = new Uint8Array(byteNumbers);
    return new Blob([byteArray], { type: mimeType });
  };

  // ❗️ 안정성을 위해 개선된 녹음 시작 함수
  const startRecording = async () => {
    if (isListening) return;
    
    try {
      log('🎤 음성 녹음 시작 요청');
      const stream = await navigator.mediaDevices.getUserMedia({ 
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true
        } 
      });
      streamRef.current = stream; // 스트림 참조 저장
      
      // 브라우저 호환성을 고려하여 녹음 포맷 결정
      let mimeType = 'audio/webm';
      if (MediaRecorder.isTypeSupported('audio/wav; codecs=MS_PCM')) {
          mimeType = 'audio/wav; codecs=MS_PCM';
      } else if (MediaRecorder.isTypeSupported('audio/webm; codecs=opus')) {
          mimeType = 'audio/webm; codecs=opus';
      }
      log(`📼 녹음 포맷 결정: ${mimeType}`);
      
      // 녹음 시작 시점에 MediaRecorder 새로 생성
      const recorder = new MediaRecorder(stream, { mimeType });
      mediaRecorderRef.current = recorder;
      audioChunksRef.current = [];
      
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
          log(`📊 오디오 청크 수신: ${event.data.size} bytes`);
        }
      };
      
      recorder.onstop = () => {
        log('🎤 녹음 중지됨');
        const audioBlob = new Blob(audioChunksRef.current, { type: mimeType });
        log(`📁 녹음 완료`, 'success', { size: audioBlob.size, type: audioBlob.type });
        processVoiceInput(audioBlob);

        // 녹음이 완전히 끝나면 스트림의 모든 트랙을 중지하여 마이크 사용 해제
        stream.getTracks().forEach(track => track.stop());
        streamRef.current = null;
      };

      recorder.onerror = (event) => {
        log('❌ 녹음 중 오류 발생', 'error', event.error);
        setIsListening(false);
      };
      
      recorder.start();
      setIsListening(true);
      log('✅ 음성 녹음 시작됨', 'success');
      
    } catch (error) {
      log(`❌ 녹음 시작 실패`, 'error', error);
      if (error.name === 'NotAllowedError') {
        toast.error('마이크 권한을 허용해주세요.');
      } else {
        toast.error('마이크를 사용할 수 없습니다.');
      }
    }
  };
  
  // ❗️ 안정성을 위해 개선된 녹음 중지 함수
  const stopRecording = () => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
      log('🛑 녹음 중지 요청');
      mediaRecorderRef.current.stop();
      setIsListening(false);
    }
  };

  const processVoiceInput = async (audioBlob) => {
    setIsProcessing(true);
    
    try {
      log(`🔍 음성 처리 시작`, 'info', { size: audioBlob.size, type: audioBlob.type });
      
      const formData = new FormData();
      // 백엔드에서 포맷을 변환하므로, 확장자는 크게 중요하지 않지만 명시적으로 보냄
      const fileExtension = audioBlob.type.includes('wav') ? 'wav' : 'webm';
      const fileName = `voice.${fileExtension}`;
      formData.append('audio', audioBlob, fileName);
      formData.append('min_confidence', '0.6');

      log(`📤 STT 요청 전송`, 'info', { fileName, size: audioBlob.size });

      const response = await axios.post('/api/stt-with-destination-processing', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
        timeout: 30000
      });

      log(`📄 STT 응답 수신`, 'info', response.data);

      if (response.data.success) {
        const { recognized_text, recommended_search_text, should_proceed } = response.data;
        log(`✅ STT 성공: "${recognized_text}"`, 'success');
        
        if (step === 'destination') {
          setDestination(recognized_text);
          
          if (should_proceed) {
            speak(`목적지 "${recommended_search_text}"를 확인했습니다. 경로를 찾고 있습니다.`);
            await findRoute(recommended_search_text);
          } else {
            speak(`"${recognized_text}"(으)로 인식되었습니다. 좀 더 명확한 목적지를 말씀해 주세요.`);
          }
        }
      } else {
        log(`❌ STT 실패`, 'error', { error: response.data.error });
        speak('음성을 인식할 수 없습니다. 다시 말씀해 주세요.');
      }
      
    } catch (error) {
      log(`❌ 음성 처리 API 오류`, 'error', error);
      
      if (error.response?.data) {
        setDebugInfo(error.response.data);
        log(`🔍 서버 오류 상세`, 'error', error.response.data);
      }
      
      speak('음성 처리 중 오류가 발생했습니다. 다시 시도해 주세요.');
    } finally {
      setIsProcessing(false);
    }
  };

  const findRoute = async (destination) => {
    if (!currentLocation) {
      speak('현재 위치를 확인할 수 없습니다.');
      return;
    }

    try {
      log(`🗺️ 경로 검색: ${destination}`);
      
      const places = await searchDestination(destination);
      if (places.length === 0) {
        speak('목적지를 찾을 수 없습니다. 다른 목적지를 말씀해 주세요.');
        return;
      }

      const destCoords = { 
        lat: parseFloat(places[0].y), 
        lng: parseFloat(places[0].x) 
      };

      const routeResponse = await axios.post('/safe-walking-route', {
        start_latitude: currentLocation.lat,
        start_longitude: currentLocation.lng,
        end_latitude: destCoords.lat,
        end_longitude: destCoords.lng
      });

      if (routeResponse.data) {
        setRoute(routeResponse.data);
        setStep('navigation');
        setNavigationIndex(0);
        
        onRouteFound?.(routeResponse.data, currentLocation, destCoords);
        
        const distance = (routeResponse.data.distance || 0).toFixed(1);
        const time = routeResponse.data.estimated_time || 0;
        
        speak(`${destination}까지 ${distance}킬로미터, 약 ${time}분 소요 예상입니다. 안내를 시작합니다.`);
        
        log(`✅ 경로 찾기 성공: ${distance}km, ${time}분`, 'success');
      }
      
    } catch (error) {
      log(`❌ 경로 검색 오류: ${error.message}`, 'error');
      speak('경로를 찾을 수 없습니다. 다른 목적지를 말씀해 주세요.');
    }
  };

  const searchDestination = async (query) => {
    try {
      const response = await axios.get('/search-location-combined', {
        params: { query: query.trim() }
      });
      return response.data.places || [];
    } catch (error) {
      log(`❌ 목적지 검색 오류: ${error.message}`, 'error');
      return [];
    }
  };

  const handleStartDestinationInput = () => {
    if (!currentLocation) {
      speak('먼저 현재 위치를 확인하고 있습니다.');
      getCurrentLocation();
      return;
    }
    
    setStep('destination');
    speak('목적지를 말씀해 주세요.');
  };

  const handleNextStep = () => {
    if (route && route.steps && navigationIndex < route.steps.length - 1) {
      const nextIndex = navigationIndex + 1;
      setNavigationIndex(nextIndex);
      const instruction = route.steps[nextIndex].instruction || '직진하세요';
      speak(instruction);
    } else {
      speak('목적지에 도착했습니다.');
    }
  };

  const handleResetNavigation = () => {
    setStep('location');
    setDestination('');
    setRoute(null);
    setNavigationIndex(0);
    setDebugInfo(null);
    speak('음성 안내를 초기화했습니다. 목적지를 말씀해 주세요.');
  };

  // 테스트용 함수들
  const testTTS = () => {
    speak('Azure TTS 테스트입니다. 음성이 정상적으로 들리나요?');
  };

  const testAudioFormats = () => {
    log('🔍 지원되는 오디오 포맷 확인:');
    const formats = [
      'audio/wav',
      'audio/webm; codecs=opus',
      'audio/webm',
      'audio/mp4',
      'audio/mpeg'
    ];
    
    formats.forEach(format => {
      const supported = MediaRecorder.isTypeSupported(format);
      log(`${supported ? '✅' : '❌'} ${format}: ${supported ? '지원됨' : '지원 안됨'}`);
    });
  };

  return (
    <div className="azure-voice-navigation">
      <div className="voice-controls">
        <h3>🎤 음성 안내 시스템</h3>
        
        <div className="current-step">
          <p><strong>현재 단계:</strong> 
            {step === 'location' && ' 위치 확인'}
            {step === 'destination' && ' 목적지 입력'}
            {step === 'navigation' && ' 경로 안내'}
          </p>
          
          {currentLocation && (
            <p><strong>현재 위치:</strong> {currentLocation.lat.toFixed(4)}, {currentLocation.lng.toFixed(4)}</p>
          )}
          
          {destination && (
            <p><strong>목적지:</strong> {destination}</p>
          )}
        </div>

        <div className="voice-buttons">
          {step === 'location' && (
            <button 
              onClick={handleStartDestinationInput}
              disabled={!currentLocation}
              className="voice-btn start-btn"
            >
              🎯 목적지 말하기
            </button>
          )}
          
          {step === 'destination' && (
            <>
              <button 
                onClick={startRecording}
                disabled={isListening || isProcessing}
                className="voice-btn record-btn"
              >
                {isListening ? '🎤 녹음 중...' : '🎤 녹음 시작'}
              </button>
              
              {isListening && (
                <button 
                  onClick={stopRecording}
                  className="voice-btn stop-btn"
                >
                  🛑 녹음 종료
                </button>
              )}
            </>
          )}
          
          {step === 'navigation' && (
            <>
              <button 
                onClick={handleNextStep}
                className="voice-btn next-btn"
              >
                ➡️ 다음 안내
              </button>
              
              <button 
                onClick={handleResetNavigation}
                className="voice-btn reset-btn"
              >
                🔄 새로운 경로
              </button>
            </>
          )}
          
          {/* 테스트 버튼들 */}
          <button 
            onClick={testTTS}
            className="voice-btn test-btn"
            disabled={isPlaying}
          >
            🔊 TTS 테스트
          </button>
          
          <button 
            onClick={testAudioFormats}
            className="voice-btn test-btn"
          >
            🔍 오디오 포맷 확인
          </button>
        </div>

        {isProcessing && (
          <div className="processing-indicator">
            <p>🔄 음성 처리 중...</p>
          </div>
        )}

        {isPlaying && (
          <div className="playing-indicator">
            <p>🔊 음성 안내 중...</p>
          </div>
        )}

        {route && step === 'navigation' && (
          <div className="navigation-info">
            <h4>📍 경로 정보</h4>
            <p><strong>거리:</strong> {(route.distance || 0).toFixed(1)}km</p>
            <p><strong>예상 시간:</strong> {route.estimated_time || 0}분</p>
            <p><strong>현재 단계:</strong> {navigationIndex + 1} / {route.steps?.length || 0}</p>
            
            {route.steps && route.steps[navigationIndex] && (
              <div className="current-instruction">
                <p><strong>현재 안내:</strong></p>
                <p>{route.steps[navigationIndex].instruction}</p>
              </div>
            )}
          </div>
        )}

        {debugInfo && (
          <div className="debug-info">
            <h4>🔍 디버그 정보</h4>
            <pre style={{ fontSize: '12px', maxHeight: '200px', overflow: 'auto' }}>
              {JSON.stringify(debugInfo, null, 2)}
            </pre>
          </div>
        )}
      </div>

      <audio 
        ref={audioRef} 
        onEnded={() => setIsPlaying(false)}
        onError={(e) => {
          log(`❌ 오디오 재생 오류: ${e.target.error?.message}`, 'error');
          setIsPlaying(false);
        }}
      />
    </div>
  );
};

export default AzureVoiceNavigation;