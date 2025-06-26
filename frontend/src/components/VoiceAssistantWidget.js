import React, { useState, useEffect, useRef } from 'react';

const VoiceAssistantWidget = () => {
  const [isRecording, setIsRecording] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [showResponse, setShowResponse] = useState(false);
  const [responseData, setResponseData] = useState({ question: '', answer: '', source: '' });
  const [showOverlay, setShowOverlay] = useState(false);
  const [statusText, setStatusText] = useState('');
  const [statusIcon, setStatusIcon] = useState('🎤');
  const [recordedAudio, setRecordedAudio] = useState(null);
  const [mediaRecorder, setMediaRecorder] = useState(null);
  const [useBackendSTT, setUseBackendSTT] = useState(false); // STT 방식 선택

  const recognitionRef = useRef(null);
  const speechSynthesisRef = useRef(window.speechSynthesis);
  const audioChunksRef = useRef([]);

  // 컴포넌트 마운트 시 음성 인식 초기화
  useEffect(() => {
    initSpeechRecognition();
    //initMediaRecorder();
    
    // 컴포넌트 언마운트 시 정리
    return () => {
      if (recognitionRef.current) {
        recognitionRef.current.abort();
      }
      speechSynthesisRef.current.cancel();
      if (mediaRecorder && mediaRecorder.state === 'recording') {
      mediaRecorder.stop();
    }
    };
  }, []);

  // MediaRecorder 초기화 (백엔드 STT용)
  // const initMediaRecorder = async () => {
  //   try {
  //     const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  //     const recorder = new MediaRecorder(stream);
      
  //     recorder.ondataavailable = (event) => {
  //       if (event.data.size > 0) {
  //         audioChunksRef.current.push(event.data);
  //       }
  //     };
      
  //     recorder.onstop = () => {
  //       const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/wav' });
  //       setRecordedAudio(audioBlob);
  //       audioChunksRef.current = [];
        
  //       // 백엔드 STT 사용 시 자동으로 처리
  //       if (useBackendSTT) {
  //         processBackendSTT(audioBlob);
  //       }
  //     };
      
  //     setMediaRecorder(recorder);
  //     console.log('✅ MediaRecorder 초기화 완료');
  //   } catch (error) {
  //     console.error('❌ MediaRecorder 초기화 실패:', error);
  //   }
  // };

  // 음성 인식 초기화
  const initSpeechRecognition = () => {
    if ('webkitSpeechRecognition' in window) {
      recognitionRef.current = new window.webkitSpeechRecognition();
    } else if ('SpeechRecognition' in window) {
      recognitionRef.current = new window.SpeechRecognition();
    } else {
      console.error('이 브라우저는 음성 인식을 지원하지 않습니다.');
      return false;
    }

    const recognition = recognitionRef.current;
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.lang = 'ko-KR';

    recognition.onstart = () => {
      console.log('🎤 음성 인식 시작');
      updateStatus('recording', '🔴', '음성 인식 중...', '지금 말씀해주세요');
    };

    recognition.onresult = (event) => {
      const transcript = event.results[0][0].transcript;
      console.log('✅ 인식된 텍스트:', transcript);
      hideOverlay();
      processVoiceQuery(transcript);
    };

    recognition.onerror = (event) => {
      console.error('❌ 음성 인식 오류:', event.error);
      hideOverlay();
      resetButton();
      
      let errorMessage = '음성 인식 중 오류가 발생했습니다.';
      if (event.error === 'no-speech') {
        errorMessage = '음성이 감지되지 않았습니다. 다시 시도해주세요.';
      } else if (event.error === 'network') {
        errorMessage = '네트워크 오류가 발생했습니다.';
      }
      
      displayResponse('오류', errorMessage, '오류');
    };

    recognition.onend = () => {
      console.log('🔚 음성 인식 종료');
      setIsRecording(false);
      if (!isProcessing) {
        hideOverlay();
        resetButton();
      }
    };

    return true;
  };

  // 백엔드 STT 처리
  const processBackendSTT = async (audioBlob) => {
    setIsProcessing(true);
    updateStatus('processing', '🎯', '음성을 텍스트로 변환 중...', '백엔드 STT 처리 중');
    
    try {
      const formData = new FormData();
      formData.append('audio', audioBlob, 'recording.wav');
      
      const response = await fetch('http://localhost:8000/chatbot/voice-to-text', {
        method: 'POST',
        body: formData
      });
      
      if (!response.ok) {
        throw new Error(`STT 서버 오류: ${response.status}`);
      }
      
      const data = await response.json();
      const recognizedText = data.recognized_text;
      
      console.log('✅ 백엔드 STT 결과:', recognizedText);
      
      if (recognizedText && recognizedText.trim()) {
        hideOverlay();
        processVoiceQuery(recognizedText.trim());
      } else {
        throw new Error('음성에서 텍스트를 인식할 수 없습니다.');
      }
      
    } catch (error) {
      console.error('❌ 백엔드 STT 오류:', error);
      hideOverlay();
      resetButton();
      displayResponse('STT 오류', error.message, '오류');
    }
  };

  // 완전한 음성 대화 (STT + LLM + TTS)
  const processVoiceChatComplete = async (audioBlob) => {
    setIsProcessing(true);
    updateStatus('processing', '🎯', '음성 대화 처리 중...', 'STT → LLM → TTS 처리 중');
    
    try {
      const formData = new FormData();
      formData.append('audio', audioBlob, 'recording.wav');
      formData.append('voice_name', 'ko-KR-HyunsuMultilingualNeural');
      
      const response = await fetch('http://localhost:8000/chatbot/voice-chat', {
        method: 'POST',
        body: formData
      });
      
      if (!response.ok) {
        throw new Error(`음성 대화 서버 오류: ${response.status}`);
      }
      
      const data = await response.json();
      console.log('✅ 완전한 음성 대화 결과:', data);
      
      const recognizedText = data.recognized_text;
      const answer = data.answer;
      const source = data.source;
      
      // 응답 표시
      displayResponse(recognizedText, answer, source);
      
      // 백엔드에서 생성된 음성 재생
      if (data.audio_data) {
        playBackendAudio(data.audio_data);
      } else {
        // 백엔드 TTS 실패 시 브라우저 TTS로 대체
        speakText(answer);
      }
      
    } catch (error) {
      console.error('❌ 완전한 음성 대화 오류:', error);
      hideOverlay();
      resetButton();
      displayResponse('음성 대화 오류', error.message, '오류');
    } finally {
      setIsProcessing(false);
    }
  };

  // 음성 상호작용 시작/중지
  const startVoiceInteraction = () => {
    // 음성 재생 중이면 중지
    if (isSpeaking) {
      stopSpeaking();
      return;
    }

    // 녹음 중이면 중지
    if (isRecording) {
      stopRecording();
      return;
    }

    // 처리 중이면 취소
    if (isProcessing) {
      cancelVoiceInteraction();
      return;
    }

    // 새로운 음성 인식 시작
    showVoiceOverlay();
    setIsRecording(true);

    if (useBackendSTT ) {
      // 백엔드 STT 사용: 오디오 녹음

      startBackendRecording();
  } else {
    // 브라우저 STT 사용: Web Speech API (권한 요청 없음)
    if (!recognitionRef.current) {
      hideOverlay();
      resetButton();
      return;
    }
      

      try {
        recognitionRef.current.start();
      } catch (error) {
        console.error('음성 인식 시작 오류:', error);
        hideOverlay();
        resetButton();
      }
    }
  };


const startBackendRecording = async () => {
  try {
    // 🔧 여기서 마이크 권한 요청 (사용할 때만)
    const stream = await navigator.mediaDevices.getUserMedia({ 
      audio: {
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true
      }
    });
    
    // 🔧 매번 새로운 MediaRecorder 생성
    const recorder = new MediaRecorder(stream, {
      mimeType: MediaRecorder.isTypeSupported('audio/wav') ? 'audio/wav' : 'audio/webm'
    });
    
    audioChunksRef.current = [];
    
    recorder.ondataavailable = (event) => {
      if (event.data.size > 0) {
        audioChunksRef.current.push(event.data);
      }
    };
    
    recorder.onstop = () => {
      const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/wav' });
      setRecordedAudio(audioBlob);
      audioChunksRef.current = [];
      
      // 🔧 스트림 정리 (권한 해제)
      stream.getTracks().forEach(track => track.stop());
      
      // 백엔드 STT 처리
      processBackendSTT(audioBlob);
    };
    
    // 🔧 현재 MediaRecorder 참조 저장
    setMediaRecorder(recorder);
    
    recorder.start();
    updateStatus('recording', '🔴', '음성 녹음 중...', '완료되면 자동으로 처리됩니다');
    
  } catch (error) {
    console.error('마이크 권한 요청 실패:', error);
    hideOverlay();
    resetButton();
    
    // 🔧 구체적인 에러 메시지
    if (error.name === 'NotAllowedError') {
      alert('마이크 권한이 필요합니다. 브라우저에서 마이크 접근을 허용해주세요.');
    } else if (error.name === 'NotFoundError') {
      alert('마이크를 찾을 수 없습니다. 마이크가 연결되어 있는지 확인해주세요.');
    } else {
      alert('마이크 접근 중 오류가 발생했습니다.');
    }
  }
};


  // 음성 재생 중지
  const stopSpeaking = () => {
    console.log('🔇 음성 재생 중지 요청');
    
    // 브라우저 TTS 중지
    if (speechSynthesisRef.current.speaking) {
      console.log('🔇 브라우저 TTS 중지');
      speechSynthesisRef.current.cancel();
    }
    
    // 백엔드 오디오 중지
    if (window.currentBackendAudio) {
      console.log('🔇 백엔드 오디오 중지');
      window.currentBackendAudio.pause();
      window.currentBackendAudio.currentTime = 0;
      window.currentBackendAudio = null;
    }
    
    setIsSpeaking(false);
    hideOverlay();
    resetButton();
  };
// 🔧 수정 5: stopRecording 함수 수정
const stopRecording = () => {
  console.log('⏹️ 녹음 중지');
  
  if (useBackendSTT && mediaRecorder && mediaRecorder.state === 'recording') {
    mediaRecorder.stop();
    // 🔧 MediaRecorder 참조 정리
    setMediaRecorder(null);
  }
  
  if (recognitionRef.current) {
    recognitionRef.current.stop();
  }
  
  setIsRecording(false);
  hideOverlay();
  resetButton();
};

  // 음성 쿼리 처리 (백엔드 TTS 사용 옵션)
  const processVoiceQuery = async (query) => {
    setIsProcessing(true);
    updateStatus('processing', '⚙️', 'AI가 생각 중입니다...', '잠시만 기다려주세요');
    
    try {
      console.log('🔄 API 서버에 질문 전송:', query);
      
      // 백엔드 TTS 사용 여부 (true면 서버 TTS, false면 브라우저 TTS)
      const useBackendTTS = false;
      
      if (useBackendTTS) {
        // 백엔드 TTS 사용
        const formData = new FormData();
        formData.append('query', query);
        formData.append('voice_name', 'ko-KR-HyunsuMultilingualNeural');

        const response = await fetch('http://localhost:8000/chatbot/ask-with-voice', {
          method: 'POST',
          body: formData
        });

        if (!response.ok) {
          throw new Error(`서버 오류: ${response.status}`);
        }

        const data = await response.json();
        console.log('✅ API 응답 수신 (TTS 포함):', data);

        const answer = data.answer || '응답을 받을 수 없습니다.';
        const source = data.source || '알 수 없음';

        // 응답 표시
        displayResponse(query, answer, source);
        
        // 백엔드에서 생성된 음성 재생
        if (data.audio_data) {
          playBackendAudio(data.audio_data);
        } else {
          // 백엔드 TTS 실패 시 브라우저 TTS로 대체
          speakText(answer);
        }
      } else {
        // 기존 방식: 브라우저 TTS 사용
        const formData = new FormData();
        formData.append('query', query);

        const response = await fetch('http://localhost:8000/chatbot/ask', {
          method: 'POST',
          body: formData
        });

        if (!response.ok) {
          throw new Error(`서버 오류: ${response.status}`);
        }

        const data = await response.json();
        console.log('✅ API 응답 수신:', data);

        const answer = data.answer || '응답을 받을 수 없습니다.';
        const source = data.source || '알 수 없음';

        // 응답 표시
        displayResponse(query, answer, source);
        
        // 브라우저 TTS로 음성 출력
        speakText(answer);
      }

    } catch (error) {
      console.error('❌ API 호출 오류:', error);
      
      let errorMessage = '서버에 연결할 수 없습니다.';
      if (error.message.includes('fetch')) {
        errorMessage = '백엔드 서버(localhost:8000)에 연결할 수 없습니다.\n\n• 서버가 실행 중인지 확인해주세요\n• 잠시 후 다시 시도해주세요';
      }
      
      displayResponse(query, errorMessage, '연결 오류');
    } finally {
      setIsProcessing(false);
      hideOverlay();
      resetButton();
    }
  };

  // 백엔드에서 생성된 음성 재생
  const playBackendAudio = (audioBase64) => {
    try {
      updateStatus('speaking', '🔊', 'AI가 답변하고 있습니다...', '백엔드 TTS로 음성 출력 중');
      setIsSpeaking(true);
      
      // Base64를 Blob으로 변환
      const audioBytes = atob(audioBase64);
      const audioArray = new Uint8Array(audioBytes.length);
      for (let i = 0; i < audioBytes.length; i++) {
        audioArray[i] = audioBytes.charCodeAt(i);
      }
      
      const audioBlob = new Blob([audioArray], { type: 'audio/wav' });
      const audioUrl = URL.createObjectURL(audioBlob);
      
      const audio = new Audio(audioUrl);
      
      audio.onloadstart = () => {
        console.log('🔊 백엔드 TTS 로딩 시작');
      };
      
      audio.onplay = () => {
        console.log('🔊 백엔드 TTS 재생 시작');
        setIsSpeaking(true);
        updateStatus('speaking', '🔇', 'AI가 답변 중입니다', '버튼을 눌러 중지할 수 있습니다');
      };
      
      audio.onended = () => {
        console.log('✅ 백엔드 TTS 재생 완료');
        setIsSpeaking(false);
        hideOverlay();
        resetButton();
        URL.revokeObjectURL(audioUrl); // 메모리 정리
      };
      
      audio.onerror = (error) => {
        console.error('❌ 오디오 재생 오류:', error);
        setIsSpeaking(false);
        hideOverlay();
        resetButton();
        URL.revokeObjectURL(audioUrl);
      };

      // 백엔드 오디오 중지를 위해 참조 저장
      window.currentBackendAudio = audio;
      
      audio.play();
      
    } catch (error) {
      console.error('백엔드 오디오 재생 오류:', error);
      setIsSpeaking(false);
      hideOverlay();
      resetButton();
    }
  };

  // 텍스트를 음성으로 변환 (브라우저 TTS)
  const speakText = (text) => {
    updateStatus('speaking', '🔊', 'AI가 답변하고 있습니다...', '음성으로 듣고 계세요');
    setIsSpeaking(true);
    
    // 기존 음성 중지
    speechSynthesisRef.current.cancel();

    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = 'ko-KR';
    utterance.rate = 1.0;
    utterance.pitch = 1.0;
    utterance.volume = 0.8;

    // 한국어 음성 선택
    const voices = speechSynthesisRef.current.getVoices();
    const koreanVoice = voices.find(voice => 
      voice.lang.includes('ko') || voice.name.includes('Korean')
    );
    if (koreanVoice) {
      utterance.voice = koreanVoice;
    }

    utterance.onstart = () => {
      console.log('🔊 브라우저 TTS 시작');
      setIsSpeaking(true);
      updateStatus('speaking', '🔇', 'AI가 답변 중입니다', '버튼을 눌러 중지할 수 있습니다');
    };

    utterance.onend = () => {
      console.log('✅ 브라우저 TTS 완료');
      setIsSpeaking(false);
      hideOverlay();
      resetButton();
    };

    utterance.onerror = (event) => {
      console.error('❌ TTS 오류:', event);
      setIsSpeaking(false);
      hideOverlay();
      resetButton();
    };

    speechSynthesisRef.current.speak(utterance);
  };

  // 상태 업데이트
  const updateStatus = (type, icon, text, subText) => {
    setStatusIcon(icon);
    setStatusText(text);
    setShowOverlay(true);
  };

  // 오버레이 표시
  const showVoiceOverlay = () => {
    setShowOverlay(true);
  };

  // 오버레이 숨기기
  const hideOverlay = () => {
    setShowOverlay(false);
  };

  // 버튼 리셋
  const resetButton = () => {
    setIsRecording(false);
    setIsProcessing(false);
    setIsSpeaking(false);
  };

  // 응답 표시
  const displayResponse = (question, answer, source) => {
    setResponseData({ question, answer, source });
    setShowResponse(true);
  };

  // 음성 상호작용 취소
  const cancelVoiceInteraction = () => {
    console.log('⏹️ 음성 상호작용 취소');
    
    // 녹음 중지
    if (useBackendSTT && mediaRecorder && mediaRecorder.state === 'recording') {
      mediaRecorder.stop();
    }
    if (recognitionRef.current) {
      recognitionRef.current.abort();
    }
    
    // 음성 재생 중지
    stopSpeaking();
    
    hideOverlay();
    resetButton();
  };

  // 응답 창 닫기
  const closeResponse = () => {
    setShowResponse(false);
  };

  // 버튼 클래스 결정
  const getButtonClass = () => {
    if (isRecording) return 'voice-floating-btn recording';
    if (isProcessing) return 'voice-floating-btn processing';
    if (isSpeaking) return 'voice-floating-btn speaking';
    return 'voice-floating-btn';
  };

  // 버튼 아이콘 결정
  const getButtonIcon = () => {
    if (isRecording) return '⏹️';  // 녹음 중 → 중지 아이콘
    if (isProcessing) return '⏹️'; // 처리 중 → 중지 아이콘
    if (isSpeaking) return '🔇';   // 음성 재생 중 → 음소거 아이콘
    return '🎤';                  // 기본 → 마이크 아이콘
  };

  // 버튼 타이틀 결정
  const getButtonTitle = () => {
    if (isRecording) return '녹음 중지';
    if (isProcessing) return '처리 취소';
    if (isSpeaking) return '음성 중지';
    return '음성으로 질문하기';
  };

  // 소스 표시 텍스트
  const getSourceDisplay = (source) => {
    const sourceMap = {
      'RAG': '📚 전문자료',
      '하드코딩된 RAG': '📋 기본정보',
      '수동 RAG': '🔍 검색자료',
      '일반 LLM': '🧠 AI지식',
      '연결 오류': '⚠️ 연결오류',
      '오류': '❌ 오류'
    };
    return sourceMap[source] || '🤖 AI';
  };

  return (
    <div style={{ position: 'relative' }}>
      {/* 음성 상태 오버레이 */}
      {showOverlay && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          width: '100vw',
          height: '100vh',
          background: 'rgba(0, 0, 0, 0.7)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 9999,
          animation: 'fadeIn 0.3s ease'
        }}>
          <div style={{
            background: 'white',
            padding: '40px',
            borderRadius: '20px',
            textAlign: 'center',
            boxShadow: '0 20px 60px rgba(0, 0, 0, 0.3)',
            maxWidth: '400px',
            width: '90%',
            transform: 'scale(1)',
            animation: 'scaleIn 0.3s ease'
          }}>
            <span style={{ fontSize: '60px', marginBottom: '20px', display: 'block' }}>
              {statusIcon}
            </span>
            <div style={{ fontSize: '18px', fontWeight: '600', color: '#333', marginBottom: '10px' }}>
              {statusText}
            </div>
            <div style={{ fontSize: '14px', color: '#666', marginBottom: '30px' }}>
              {isSpeaking ? 
                '🔇 음성 재생 중입니다. 버튼을 눌러 중지하세요.' :
                useBackendSTT ? 
                (isRecording ? '녹음 중... 말씀이 끝나면 중지 버튼을 눌러주세요' : '마이크에 대고 말씀해주세요') :
                '마이크에 대고 말씀해주세요'
              }
            </div>
            <div style={{ marginBottom: '20px' }}>
              {isRecording && useBackendSTT && (
                <button
                  onClick={stopRecording}
                  style={{
                    background: '#28a745',
                    color: 'white',
                    border: 'none',
                    padding: '10px 20px',
                    borderRadius: '6px',
                    cursor: 'pointer',
                    fontSize: '14px',
                    marginRight: '10px'
                  }}
                >
                  녹음 완료
                </button>
              )}
              {(isRecording || isProcessing || isSpeaking) && (
                <button
                  onClick={cancelVoiceInteraction}
                  style={{
                    background: '#dc3545',
                    color: 'white',
                    border: 'none',
                    padding: '10px 20px',
                    borderRadius: '6px',
                    cursor: 'pointer',
                    fontSize: '14px'
                  }}
                >
                  {isSpeaking ? '🔇 음성 중지' : '⏹️ 취소'}
                </button>
              )}
            </div>
            <div style={{ fontSize: '12px', color: '#888', marginBottom: '20px' }}>
              STT 방식: {useBackendSTT ? '백엔드 (Azure Speech)' : '브라우저 (Web Speech API)'}
            </div>
            <button
              onClick={cancelVoiceInteraction}
              style={{
                background: '#ff4757',
                color: 'white',
                border: 'none',
                padding: '12px 24px',
                borderRadius: '8px',
                cursor: 'pointer',
                fontSize: '16px',
                fontWeight: '600'
              }}
            >
              닫기
            </button>
          </div>
        </div>
      )}

      {/* 응답 팝업 */}
      {showResponse && (
        <div style={{
          position: 'fixed',
          bottom: '120px',
          right: '30px',
          width: '350px',
          maxWidth: 'calc(100vw - 60px)',
          background: 'white',
          borderRadius: '16px',
          boxShadow: '0 10px 40px rgba(0, 0, 0, 0.15)',
          padding: '20px',
          zIndex: 9998,
          animation: 'slideUp 0.3s ease'
        }}>
          <div style={{ marginBottom: '20px' }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
              <input
                type="checkbox"
                checked={useBackendSTT}
                onChange={(e) => setUseBackendSTT(e.target.checked)}
              />
              <span style={{ fontSize: '14px' }}>백엔드 STT 사용 (Azure Speech Service)</span>
            </label>
          </div>
          
          <div style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            marginBottom: '15px',
            paddingBottom: '10px',
            borderBottom: '1px solid #eee'
          }}>
            <div style={{
              fontWeight: '600',
              color: '#333',
              display: 'flex',
              alignItems: 'center',
              gap: '8px'
            }}>
              <span>🤖</span>
              <span>AI 어시스턴트</span>
            </div>
            <button
              onClick={closeResponse}
              style={{
                background: 'none',
                border: 'none',
                fontSize: '18px',
                cursor: 'pointer',
                color: '#999',
                padding: 0,
                width: '24px',
                height: '24px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center'
              }}
            >
              ✕
            </button>
          </div>
          
          {responseData.question && (
            <div style={{
              background: '#f0f8ff',
              padding: '10px',
              borderRadius: '8px',
              marginBottom: '10px',
              fontSize: '14px',
              color: '#555'
            }}>
              <strong>질문:</strong> {responseData.question}
            </div>
          )}
          
          <div style={{
            color: '#555',
            lineHeight: '1.5',
            fontSize: '14px',
            whiteSpace: 'pre-wrap',
            maxHeight: '300px',
            overflowY: 'auto'
          }}>
            {responseData.answer}
          </div>
          
          {responseData.source && (
            <div style={{
              fontSize: '12px',
              color: '#888',
              marginTop: '10px',
              paddingTop: '10px',
              borderTop: '1px solid #eee'
            }}>
              출처: {getSourceDisplay(responseData.source)}
            </div>
          )}
        </div>
      )}

      {/* 플로팅 음성 버튼 */}
      <button
        className={getButtonClass()}
        onClick={startVoiceInteraction}
        title={getButtonTitle()}
        style={{
          position: 'fixed',
          bottom: '30px',
          right: '30px',
          width: '70px',
          height: '70px',
          background: isRecording 
            ? 'linear-gradient(135deg, #ff4757 0%, #c44569 100%)'
            : isProcessing 
            ? 'linear-gradient(135deg, #ffa502 0%, #ff6348 100%)'
            : isSpeaking
            ? 'linear-gradient(135deg, #2ed573 0%, #1e90ff 100%)'
            : 'linear-gradient(135deg, #ff6b6b 0%, #ee5a52 100%)',
          border: 'none',
          borderRadius: '50%',
          cursor: 'pointer',
          boxShadow: '0 8px 30px rgba(255, 107, 107, 0.4)',
          transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
          zIndex: 10000,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: 'white',
          fontSize: '28px',
          outline: 'none',
          animation: isRecording 
            ? 'pulse 1.5s infinite'
            : isProcessing 
            ? 'spin 1s linear infinite'
            : isSpeaking
            ? 'wave 1s ease-in-out infinite alternate'
            : 'none'
        }}
      >
        {getButtonIcon()}
      </button>

      {/* 애니메이션 스타일 */}
      <style>{`
        @keyframes pulse {
          0% { transform: scale(1); }
          50% { transform: scale(1.1); box-shadow: 0 12px 40px rgba(255, 71, 87, 0.6); }
          100% { transform: scale(1); }
        }

        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }

        @keyframes wave {
          0% { transform: scale(1); }
          100% { transform: scale(1.08); }
        }

        @keyframes fadeIn {
          from { opacity: 0; }
          to { opacity: 1; }
        }

        @keyframes scaleIn {
          from { transform: scale(0.9); }
          to { transform: scale(1); }
        }

        @keyframes slideUp {
          from { transform: translateY(20px); opacity: 0; }
          to { transform: translateY(0); opacity: 1; }
        }

        .voice-floating-btn:hover {
          transform: translateY(-3px) scale(1.05) !important;
          box-shadow: 0 12px 40px rgba(255, 107, 107, 0.5) !important;
        }
      `}</style>
    </div>
  );
};

export default VoiceAssistantWidget;