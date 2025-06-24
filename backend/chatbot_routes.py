
from fastapi import APIRouter, File, Form, UploadFile, HTTPException
from typing import Optional
import base64
from chatbot_service import rag_system

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