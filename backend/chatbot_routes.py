from fastapi.responses import Response
from fastapi import APIRouter, File, Form, UploadFile, HTTPException
from typing import Optional
import base64
import datetime
from chatbot_service import rag_system
from speech_service import speech_service

# 챗봇 라우터 생성
chatbot_router = APIRouter(prefix="/chatbot", tags=["chatbot"])

@chatbot_router.post("/ask")
async def chatbot_ask(
    query: str = Form(...),
    image: Optional[UploadFile] = File(None)
):
    """챗봇 질문 처리 API"""
    try:
        # 입력 유효성 검사
        if not query or len(query.strip()) < 2:
            raise HTTPException(status_code=400, detail="질문을 입력해주세요.")
        
        # 질문 길이 제한 (보안상)
        if len(query) > 1000:
            raise HTTPException(status_code=400, detail="질문이 너무 깁니다. 1000자 이내로 입력해주세요.")
        
        image_data = None
        if image:
            # 이미지 파일 크기 제한 (10MB)
            contents = await image.read()
            if len(contents) > 10 * 1024 * 1024:  # 10MB
                raise HTTPException(status_code=400, detail="이미지 파일이 너무 큽니다. 10MB 이하로 업로드해주세요.")
            
            # 이미지 형식 확인
            if not image.content_type.startswith('image/'):
                raise HTTPException(status_code=400, detail="이미지 파일만 업로드 가능합니다.")
            
            image_data = base64.b64encode(contents).decode('utf-8')
        
        # 스마트 RAG 시스템으로 답변 생성
        answer, source = rag_system.smart_answer(query.strip(), image_data)
        
        return {
            "success": True,
            "answer": answer,
            "source": source,
            "query": query.strip(),
            "has_image": image is not None,
            "timestamp": "2024-12-19"  # 실제로는 datetime.now() 사용
        }
        
    except HTTPException:
        # HTTPException은 그대로 재발생
        raise
        
    except Exception as e:
        print(f"챗봇 처리 오류: {e}")
        return {
            "success": False,
            "error": "답변 생성 중 오류가 발생했습니다.",
            "answer": """죄송합니다. 일시적인 오류가 발생했습니다. 

다음과 같이 시도해보세요:
• 잠시 후 다시 질문해보세요
• 질문을 더 간단하게 바꿔보세요
• 긴급한 경우 119 또는 120으로 연락하세요

서비스 이용에 불편을 드려 죄송합니다.""",
            "source": "오류"
        }

@chatbot_router.get("/health")
async def chatbot_health():
    """챗봇 시스템 상태 확인"""
    return {
        "status": "healthy",
        "message": "챗봇 시스템이 정상 작동 중입니다.",
        "features": {
            "text_chat": True,
            "image_upload": True,
            "rag_system": True,
            "fallback_llm": True
        },
        "supported_queries": [
            "싱크홀 신고 방법",
            "싱크홀 크기 측정",
            "발생 원인 및 예방",
            "피해 보상 절차",
            "서비스 이용 방법"
        ]
    }

@chatbot_router.get("/examples")
async def get_example_questions():
    """예시 질문 목록 제공"""
    return {
        "categories": {
            "신고_접수": [
                "싱크홀을 발견했는데 어디에 신고해야 하나요?",
                "싱크홀 신고할 때 어떤 정보가 필요한가요?",
                "응급상황일 때 연락처는 어디인가요?"
            ],
            "측정_평가": [
                "싱크홀 크기는 어떻게 측정하나요?",
                "어느 정도 크기부터 위험한가요?",
                "깊이를 알 수 없을 때는 어떻게 하나요?"
            ],
            "원인_예방": [
                "싱크홀이 생기는 원인은 무엇인가요?",
                "싱크홀을 미리 예방할 수 있는 방법이 있나요?",
                "어떤 징후를 봐야 하나요?"
            ],
            "보상_절차": [
                "싱크홀 피해 보상은 어떻게 받나요?",
                "보상 신청에 필요한 서류는 무엇인가요?",
                "보상 처리 기간은 얼마나 걸리나요?"
            ],
            "서비스_이용": [
                "이 서비스는 어떻게 사용하나요?",
                "위험지도는 어디서 볼 수 있나요?",
                "안전 경로 검색 기능은 어떻게 쓰나요?"
            ]
        }
    }



# 기존 라우터에 음성 관련 엔드포인트 추가
@chatbot_router.post("/ask-with-voice")
async def chatbot_ask_with_voice(
    query: str = Form(...),
    image: Optional[UploadFile] = File(None),
    voice_name: str = Form("ko-KR-HyunsuMultilingualNeural")
):
    """챗봇 질문 + TTS 음성 응답 API"""
    try:
        # 기존 챗봇 로직과 동일
        if not query or len(query.strip()) < 2:
            raise HTTPException(status_code=400, detail="질문을 입력해주세요.")
        
        if len(query) > 1000:
            raise HTTPException(status_code=400, detail="질문이 너무 깁니다. 1000자 이내로 입력해주세요.")
        
        image_data = None
        if image:
            contents = await image.read()
            if len(contents) > 10 * 1024 * 1024:  # 10MB
                raise HTTPException(status_code=400, detail="이미지 파일이 너무 큽니다.")
            
            if not image.content_type.startswith('image/'):
                raise HTTPException(status_code=400, detail="이미지 파일만 업로드 가능합니다.")
            
            image_data = base64.b64encode(contents).decode('utf-8')
        
        # RAG 시스템으로 답변 생성
        answer, source = rag_system.smart_answer(query.strip(), image_data)
        
        # TTS로 음성 생성
        try:
            audio_data = speech_service.text_to_speech(answer, voice_name)
            audio_base64 = base64.b64encode(audio_data).decode('utf-8')
        except Exception as tts_error:
            print(f"TTS 오류: {tts_error}")
            audio_base64 = None
        
        return {
            "success": True,
            "answer": answer,
            "source": source,
            "query": query.strip(),
            "has_image": image is not None,
            "audio_data": audio_base64,  # Base64 인코딩된 음성 데이터
            "voice_name": voice_name,
            "timestamp": "2024-12-19"
        }
        
    except HTTPException:
        raise
        
    except Exception as e:
        print(f"챗봇 음성 처리 오류: {e}")
        return {
            "success": False,
            "error": "답변 생성 중 오류가 발생했습니다.",
            "answer": "죄송합니다. 일시적인 오류가 발생했습니다.",
            "source": "오류",
            "audio_data": None
        }

@chatbot_router.post("/text-to-speech")
async def text_to_speech_endpoint(
    text: str = Form(...),
    voice_name: str = Form("ko-KR-HyunsuMultilingualNeural"),
    return_audio: bool = Form(False)  # True면 직접 오디오 반환, False면 Base64
):
    """텍스트를 음성으로 변환하는 독립 API"""
    try:
        if not text or len(text.strip()) < 1:
            raise HTTPException(status_code=400, detail="변환할 텍스트를 입력해주세요.")
        
        if len(text) > 2000:
            raise HTTPException(status_code=400, detail="텍스트가 너무 깁니다. 2000자 이내로 입력해주세요.")
        
        # TTS 실행
        audio_data = speech_service.text_to_speech(text.strip(), voice_name)
        
        if return_audio:
            # 직접 오디오 파일로 반환 (브라우저에서 바로 재생 가능)
            return Response(
                content=audio_data,
                media_type="audio/wav",
                headers={
                    "Content-Disposition": "attachment; filename=speech.wav",
                    "Content-Length": str(len(audio_data))
                }
            )
        else:
            # Base64로 인코딩해서 JSON으로 반환
            audio_base64 = base64.b64encode(audio_data).decode('utf-8')
            return {
                "success": True,
                "text": text.strip(),
                "voice_name": voice_name,
                "audio_data": audio_base64,
                "audio_size": len(audio_data)
            }
        
    except HTTPException:
        raise
        
    except Exception as e:
        print(f"TTS API 오류: {e}")
        raise HTTPException(status_code=500, detail=f"음성 합성 오류: {str(e)}")

@chatbot_router.post("/voice-to-text")
async def voice_to_text_endpoint(
    audio: UploadFile = File(...)
):
    """음성 파일을 텍스트로 변환하는 STT API"""
    try:
        if not audio.content_type.startswith('audio/'):
            raise HTTPException(status_code=400, detail="오디오 파일만 업로드 가능합니다.")
        
        audio_data = await audio.read()
        if len(audio_data) > 25 * 1024 * 1024:  # 25MB
            raise HTTPException(status_code=400, detail="오디오 파일이 너무 큽니다. 25MB 이하로 업로드해주세요.")
        
        # STT 실행
        recognized_text = speech_service.speech_to_text(audio_data)
        
        return {
            "success": True,
            "recognized_text": recognized_text,
            "audio_filename": audio.filename,
            "audio_size": len(audio_data),
            "timestamp": datetime.datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
        
    except Exception as e:
        print(f"STT API 오류: {e}")
        raise HTTPException(status_code=500, detail=f"음성 인식 오류: {str(e)}")

@chatbot_router.post("/voice-chat")
async def voice_chat_endpoint(
    audio: UploadFile = File(...),
    voice_name: str = Form("ko-KR-HyunsuMultilingualNeural"),
    image: Optional[UploadFile] = File(None)
):
    """완전한 음성 대화: STT → LLM → TTS"""
    try:
        # 1. 오디오 파일 검증
        if not audio.content_type.startswith('audio/'):
            raise HTTPException(status_code=400, detail="오디오 파일만 업로드 가능합니다.")
        
        audio_data = await audio.read()
        if len(audio_data) > 25 * 1024 * 1024:  # 25MB
            raise HTTPException(status_code=400, detail="오디오 파일이 너무 큽니다.")
        
        # 2. 이미지 처리 (선택사항)
        image_data = None
        if image:
            image_contents = await image.read()
            if len(image_contents) > 10 * 1024 * 1024:  # 10MB
                raise HTTPException(status_code=400, detail="이미지 파일이 너무 큽니다.")
            
            if not image.content_type.startswith('image/'):
                raise HTTPException(status_code=400, detail="이미지 파일만 업로드 가능합니다.")
            
            image_data = base64.b64encode(image_contents).decode('utf-8')
        
        # 3. STT: 음성을 텍스트로 변환
        try:
            recognized_text = speech_service.speech_to_text(audio_data)
            print(f"🎤 STT 결과: {recognized_text}")
        except Exception as stt_error:
            print(f"❌ STT 오류: {stt_error}")
            raise HTTPException(status_code=400, detail=f"음성 인식 실패: {str(stt_error)}")
        
        if not recognized_text or len(recognized_text.strip()) < 2:
            raise HTTPException(status_code=400, detail="음성에서 텍스트를 인식할 수 없습니다.")
        
        # 4. LLM: RAG 시스템으로 답변 생성
        try:
            answer, source = rag_system.smart_answer(recognized_text.strip(), image_data)
            print(f"🤖 LLM 응답: {answer[:100]}...")
        except Exception as llm_error:
            print(f"❌ LLM 오류: {llm_error}")
            answer = "죄송합니다. 답변 생성 중 오류가 발생했습니다."
            source = "오류"
        
        # 5. TTS: 답변을 음성으로 변환
        try:
            audio_response = speech_service.text_to_speech(answer, voice_name)
            audio_base64 = base64.b64encode(audio_response).decode('utf-8')
            print(f"🔊 TTS 성공: {len(audio_response)} bytes")
        except Exception as tts_error:
            print(f"❌ TTS 오류: {tts_error}")
            audio_base64 = None
        
        return {
            "success": True,
            "recognized_text": recognized_text,
            "answer": answer,
            "source": source,
            "audio_data": audio_base64,
            "voice_name": voice_name,
            "has_image": image is not None,
            "processing_time": "완료",
            "timestamp": datetime.datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
        
    except Exception as e:
        print(f"음성 대화 API 오류: {e}")
        return {
            "success": False,
            "error": "음성 대화 처리 중 오류가 발생했습니다.",
            "recognized_text": "",
            "answer": "죄송합니다. 일시적인 오류가 발생했습니다.",
            "source": "오류",
            "audio_data": None
        }

@chatbot_router.post("/voice-test")
async def voice_test_endpoint():
    """음성 서비스 테스트 API"""
    try:
        # TTS 테스트
        test_text = "안녕하세요. 싱크홀 음성 어시스턴트 테스트입니다."
        audio_data = speech_service.text_to_speech(test_text)
        audio_base64 = base64.b64encode(audio_data).decode('utf-8')
        
        return {
            "success": True,
            "message": "음성 서비스가 정상 작동합니다.",
            "test_text": test_text,
            "audio_data": audio_base64,
            "audio_size": len(audio_data),
            "service_status": {
                "speech_enabled": speech_service.enabled,
                "tts_available": True,
                "stt_available": True
            }
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"음성 서비스 테스트 실패: {str(e)}",
            "service_status": {
                "speech_enabled": speech_service.enabled,
                "tts_available": False,
                "stt_available": False
            }
        }

@chatbot_router.get("/speech/voices")
async def get_available_voices():
    """사용 가능한 음성 목록 반환"""
    return {
        "korean_voices": [
            {
                "name": "ko-KR-HyunsuMultilingualNeural",
                "display_name": "현수 (남성, 다국어)",
                "gender": "Male",
                "recommended": True
            },
            {
                "name": "ko-KR-JiminNeural",
                "display_name": "지민 (여성)",
                "gender": "Female",
                "recommended": True
            },
            {
                "name": "ko-KR-BongJinNeural", 
                "display_name": "봉진 (남성)",
                "gender": "Male",
                "recommended": False
            },
            {
                "name": "ko-KR-SunHiNeural",
                "display_name": "선희 (여성)",
                "gender": "Female", 
                "recommended": False
            }
        ],
        "default_voice": "ko-KR-HyunsuMultilingualNeural",
        "note": "현수 다국어 음성이 가장 자연스럽고 싱크홀 관련 전문 용어 발음에 적합합니다."
    }