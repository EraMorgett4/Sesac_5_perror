import React, { useState, useRef, useEffect } from 'react';
import '../styles/ReportChatbot.css';

const ReportChatbot = () => {
  const [messages, setMessages] = useState([
    {
      id: 1,
      type: 'bot',
      content: '안녕하세요! 싱크홀 신고 도우미입니다. 어떤 도움이 필요하신가요?\n\n📸 사진과 함께 신고하시거나\n💬 텍스트로 질문해주세요!',
      timestamp: new Date()
    }
  ]);
  const [inputText, setInputText] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [selectedImage, setSelectedImage] = useState(null);
  const [previewImage, setPreviewImage] = useState(null);
  
  const messagesEndRef = useRef(null);
  const fileInputRef = useRef(null);
  const chatContainerRef = useRef(null);

  // 메시지 스크롤 자동 이동
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // 이미지 파일 선택 처리
  const handleImageSelect = (e) => {
    const file = e.target.files[0];
    if (file) {
      if (file.type.startsWith('image/')) {
        setSelectedImage(file);
        
        // 이미지 미리보기
        const reader = new FileReader();
        reader.onload = (e) => {
          setPreviewImage(e.target.result);
        };
        reader.readAsDataURL(file);
      } else {
        alert('이미지 파일만 업로드 가능합니다.');
      }
    }
  };

  // 이미지 선택 취소
  const handleImageCancel = () => {
    setSelectedImage(null);
    setPreviewImage(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  // RAG 시스템 API 호출 (실제 백엔드 연결)
  const callRAGSystem = async (query, imageFile = null) => {
    try {
      // 실제 백엔드 API 엔드포인트로 호출
      const formData = new FormData();
      formData.append('query', query);
      if (imageFile) {
        formData.append('image', imageFile);
      }

      console.log('🔄 백엔드 API 호출 중...', { query, hasImage: !!imageFile });

      // 실제 백엔드 RAG API 호출
      const response = await fetch('http://localhost:8000/chatbot/ask', {
        method: 'POST',
        body: formData,
        // Content-Type은 FormData 사용시 자동 설정되므로 생략
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      
      console.log('✅ API 응답 성공:', data);

      // 백엔드 응답 형식에 맞게 변환
      return {
        answer: data.answer || '응답을 받을 수 없습니다.',
        source: data.source || '알 수 없음'
      };

    } catch (error) {
      console.error('❌ RAG API 호출 오류:', error);
      
      // 네트워크 오류나 서버 오류시 fallback
      if (error.name === 'TypeError' && error.message.includes('fetch')) {
        return {
          answer: '❌ 서버에 연결할 수 없습니다.\n\n• 백엔드 서버가 실행 중인지 확인해주세요 (http://localhost:8000)\n• 잠시 후 다시 시도해주세요',
          source: '연결 오류'
        };
      }
      
      return {
        answer: '죄송합니다. 현재 서비스에 문제가 발생했습니다.\n\n• 잠시 후 다시 시도해주세요\n• 문제가 지속되면 관리자에게 문의하세요',
        source: '오류'
      };
    }
  };

  // 메시지 전송
  const handleSendMessage = async () => {
    if (!inputText.trim() && !selectedImage) return;

    const userMessage = {
      id: Date.now(),
      type: 'user',
      content: inputText.trim(),
      image: previewImage,
      timestamp: new Date()
    };

    setMessages(prev => [...prev, userMessage]);
    setIsLoading(true);

    // 입력 초기화
    const query = inputText.trim();
    const imageFile = selectedImage;
    setInputText('');
    setSelectedImage(null);
    setPreviewImage(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }

    try {
      // RAG 시스템 호출
      const response = await callRAGSystem(query, imageFile);
      
      const botMessage = {
        id: Date.now() + 1,
        type: 'bot',
        content: response.answer,
        source: response.source,
        timestamp: new Date()
      };

      setMessages(prev => [...prev, botMessage]);
    } catch (error) {
      const errorMessage = {
        id: Date.now() + 1,
        type: 'bot',
        content: '죄송합니다. 답변 생성 중 오류가 발생했습니다. 다시 시도해주세요.',
        timestamp: new Date()
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  // 엔터 키 처리
  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  // 미리 정의된 질문 클릭
  const handleQuickQuestion = (question) => {
    setInputText(question);
  };

  const quickQuestions = [
    "싱크홀 발견했는데 어디로 신고하나요?",
    "신고할 때 어떤 정보가 필요한가요?",
    "긴급상황 연락처 알려주세요",
    "싱크홀 크기는 어떻게 측정하나요?"
  ];

  return (
    <div className="report-chatbot">
      <div className="chatbot-container">
        <div className="chatbot-header">
          <h1>🕳️ 싱크홀 신고 도우미</h1>
          <p>사진과 함께 신고하거나 궁금한 점을 질문해보세요!</p>
        </div>

        <div className="chat-messages" ref={chatContainerRef}>
          {messages.map((message) => (
            <div key={message.id} className={`message ${message.type}`}>
              <div className="message-avatar">
                {message.type === 'user' ? '👤' : '🤖'}
              </div>
              <div className="message-content">
                {message.image && (
                  <div className="message-image">
                    <img src={message.image} alt="첨부 이미지" />
                  </div>
                )}
                <div className="message-text">
                  {message.content.split('\n').map((line, index) => (
                    <React.Fragment key={index}>
                      {line}
                      {index < message.content.split('\n').length - 1 && <br />}
                    </React.Fragment>
                  ))}
                </div>
                <div className="message-info">
                  <span className="message-time">
                    {message.timestamp.toLocaleTimeString('ko-KR', { 
                      hour: '2-digit', 
                      minute: '2-digit' 
                    })}
                  </span>
                  {message.source && (
                    <span className={`message-source ${message.source === 'RAG' ? 'rag' : 'llm'}`}>
                      {message.source === 'RAG' ? '📚 전문자료' : 
                       message.source === '하드코딩된 RAG' ? '📋 기본정보' :
                       message.source === '수동 RAG' ? '🔍 검색자료' :
                       message.source === '일반 LLM' ? '🧠 AI지식' :
                       message.source === '연결 오류' ? '⚠️ 연결오류' :
                       message.source === '오류' ? '❌ 오류' : '🤖 AI'}
                    </span>
                  )}
                </div>
              </div>
            </div>
          ))}
          
          {isLoading && (
            <div className="message bot">
              <div className="message-avatar">🤖</div>
              <div className="message-content">
                <div className="typing-indicator">
                  <span></span>
                  <span></span>
                  <span></span>
                </div>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* 빠른 질문 버튼들 */}
        {messages.length === 1 && (
          <div className="quick-questions">
            <p>자주 묻는 질문:</p>
            <div className="quick-question-buttons">
              {quickQuestions.map((question, index) => (
                <button
                  key={index}
                  className="quick-question-btn"
                  onClick={() => handleQuickQuestion(question)}
                >
                  {question}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* 이미지 미리보기 */}
        {previewImage && (
          <div className="image-preview">
            <div className="preview-container">
              <img src={previewImage} alt="업로드 예정 이미지" />
              <button className="remove-image-btn" onClick={handleImageCancel}>
                ✕
              </button>
            </div>
          </div>
        )}

        {/* 입력 영역 */}
        <div className="chat-input-container">
          <div className="input-row">
            <input
              type="file"
              ref={fileInputRef}
              onChange={handleImageSelect}
              accept="image/*"
              style={{ display: 'none' }}
            />
            
            <button
              className="image-upload-btn"
              onClick={() => fileInputRef.current?.click()}
              title="이미지 첨부"
            >
              📷
            </button>

            <textarea
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder="싱크홀 관련 질문을 입력하거나 사진을 첨부해주세요..."
              className="chat-input"
              rows="1"
              disabled={isLoading}
            />

            <button
              onClick={handleSendMessage}
              disabled={(!inputText.trim() && !selectedImage) || isLoading}
              className="send-btn"
            >
              {isLoading ? '⏳' : '전송'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ReportChatbot;