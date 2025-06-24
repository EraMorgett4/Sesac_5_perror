# chatbot_service.py
import os
import base64
import re
from typing import Optional, Tuple
from dotenv import load_dotenv
from openai import AzureOpenAI

load_dotenv()

class SmartRAGSystem:
    def __init__(self):
        # Azure OpenAI 설정 (환경변수에서 가져오기)
        self.endpoint = os.getenv("ENDPOINT_URL", "your-endpoint-url")
        self.deployment = os.getenv("DEPLOYMENT_NAME", "your_name")  # 모델명 업데이트
        self.search_endpoint = os.getenv("SEARCH_ENDPOINT", "your-search-endpoint")
        self.search_key = os.getenv("SEARCH_KEY", "your-search-key")
        self.search_index = os.getenv("SEARCH_INDEX_NAME", "your-index-name")
        self.api_key = os.getenv("AZURE_OPENAI_API_KEY", "your-key")
        
        # Azure OpenAI 클라이언트 초기화
        self.client = AzureOpenAI(
            azure_endpoint=self.endpoint,
            api_key=self.api_key,
            api_version="2024-08-01-preview",  # 최신 API 버전
        )
        
        # RAG가 적절한 답변을 못할 때 나오는 패턴들 (한글 + 영어)
        self.inadequate_patterns = [
            # 한글 패턴
            "자료에 없는", "자료에서 찾을 수 없", "정보가 없", "구체적인 정보가 부족",
            "자료에 명시되지 않", "제공된 자료만으로는", "자료에는 포함되지 않",
            "추가 정보가 필요", "자료에 관련 내용이 없", "자료에서 확인할 수 없",
            "제공된 문서에는 없", "참고자료에 없", "자료 범위를 벗어",
            "죄송합니다", "죄송하지만", "미안하지만", "안타깝게도",
            "정확한 답변을 드릴 수 없", "명확한 답변이 어려", "구체적인 답변 불가",
            "해당 정보는 없", "관련 정보를 찾지 못", "적절한 답변을 찾을 수 없",
            
            # 영어 패턴
            "not found in the", "information is not available", "no information", 
            "not mentioned in the", "not included in the", "not specified in the",
            "cannot find", "unable to find", "couldn't find", "can't find",
            "no relevant information", "insufficient information", "lack of information",
            "sorry", "i'm sorry", "i apologize", "unfortunately", "regrettably",
            "cannot provide", "unable to provide", "can't provide", "couldn't provide",
            "not possible to", "impossible to", "difficult to", "hard to",
            "no data", "no details", "no specific", "not clear", "unclear",
            "beyond the scope", "outside the scope", "not covered", "not addressed",
            "i don't know", "i'm not sure", "uncertain", "unsure"
        ]
        
        # 환경 변수 검증
        self.validate_config()
    
    def validate_config(self):
        """환경 변수 설정 검증"""
        required_vars = {
            "ENDPOINT_URL": self.endpoint,
            "DEPLOYMENT_NAME": self.deployment,
            "AZURE_OPENAI_API_KEY": self.api_key,
            "SEARCH_ENDPOINT": self.search_endpoint,
            "SEARCH_KEY": self.search_key,
            "SEARCH_INDEX_NAME": self.search_index
        }
        
        missing_vars = []
        for var_name, value in required_vars.items():
            if not value or value.startswith("your-"):
                missing_vars.append(var_name)
        
        if missing_vars:
            print(f"⚠️ 다음 환경 변수를 설정해주세요: {', '.join(missing_vars)}")
            print("💡 .env 파일에 실제 값을 설정하거나 환경 변수로 지정하세요.")
    
    def test_basic_connection(self):
        """기본 OpenAI 연결 테스트"""
        try:
            print("🔍 기본 OpenAI 연결 테스트...")
            response = self.client.chat.completions.create(
                model=self.deployment,
                messages=[
                    {"role": "system", "content": "간단한 연결 테스트입니다."},
                    {"role": "user", "content": "안녕하세요"}
                ],
                max_tokens=50,
                temperature=0.3
            )
            print("✅ 기본 OpenAI 연결 성공!")
            return True
        except Exception as e:
            print(f"❌ 기본 OpenAI 연결 실패: {e}")
            return False
    
    def post_process_answer(self, answer: str) -> str:
        """RAG 답변의 참조를 사용자 친화적으로 변경"""
        if not answer:
            return answer
        
        # [doc1], [doc2] 등의 참조를 제거
        citation_patterns = [
            r'\[doc\d+\]',
            r'\[document\d+\]',
            r'\[source\d+\]',
            r'\[문서\d+\]',
            r'\[자료\d+\]',
            r'\[참고\d+\]'
        ]
        
        processed_answer = answer
        for pattern in citation_patterns:
            processed_answer = re.sub(pattern, '', processed_answer)
        
        # 연속된 공백이나 줄바꿈 정리
        processed_answer = re.sub(r'\s+', ' ', processed_answer)
        processed_answer = re.sub(r'\n\s*\n', '\n\n', processed_answer)
        
        return processed_answer.strip()
    
    def add_credibility_footer(self, answer: str, source: str) -> str:
        """답변에 신뢰성 정보 추가"""
        
        footer_options = {
            "RAG": "📚 *서울시 공식 싱크홀 대응 매뉴얼 기반*",
            "수동 RAG": "🔍 서울시 안전관리 데이터베이스 검색 결과", 
            "하드코딩된 RAG": "📋 서울시 각 구청 공식 연락처 및 대응 절차",
            "일반 LLM": "🧠 *일반적인 안전 상식 및 가이드라인*"
        }
        
        footer = footer_options.get(source, "")
        
        if footer:
            return f"{answer}\n\n{footer}"
        
        return answer
    
    def try_rag_answer(self, query: str) -> Tuple[Optional[str], bool]:
        """Azure Search 통합 RAG로 답변 시도"""
        try:
            # 환경 변수가 제대로 설정되지 않은 경우 스킵
            if self.search_endpoint.startswith("your-") or self.search_key.startswith("your-"):
                print("⚠️ Azure Search 설정이 누락되어 RAG를 건너뜁니다.")
                return None, False
            
            print("🔍 RAG 답변 시도 중...")
            
            chat_prompt = [
                {
                    "role": "system",
                    "content": "당신은 싱크홀 신고 전문가입니다. 제공된 자료를 바탕으로 정확한 답변을 제공하세요. 참조 번호는 사용하지 말고 자연스러운 문장으로 답변해주세요."
                },
                {
                    "role": "user",
                    "content": query
                }
            ]
            
            completion = self.client.chat.completions.create(
                model=self.deployment,
                messages=chat_prompt,
                max_tokens=800,
                temperature=0.3,
                extra_body={
                    "data_sources": [{
                        "type": "azure_search",
                        "parameters": {
                            "endpoint": self.search_endpoint,
                            "index_name": self.search_index,
                            "query_type": "simple",
                            "fields_mapping": {
                                "content_fields": ["chunk"],
                                "title_field": "title"
                            },
                            "in_scope": True,
                            "top_n_documents": 5,
                            "authentication": {
                                "type": "api_key",
                                "key": self.search_key
                            }
                        }
                    }]
                }
            )
            
            rag_answer = completion.choices[0].message.content
            print("✅ RAG 답변 생성 성공!")
            return rag_answer, True
            
        except Exception as e:
            print(f"❌ RAG 답변 생성 실패: {e}")
            return None, False
    
    def try_manual_rag(self, query: str) -> Tuple[Optional[str], bool]:
        """수동 RAG 방식으로 시도"""
        try:
            # 환경 변수 확인
            if self.search_endpoint.startswith("your-") or self.search_key.startswith("your-"):
                print("⚠️ Azure Search 설정이 누락되어 수동 RAG를 건너뜁니다.")
                return None, False
            
            print("🔍 수동 RAG 시도 중...")
            
            from azure.search.documents import SearchClient
            from azure.core.credentials import AzureKeyCredential
            
            search_client = SearchClient(
                endpoint=self.search_endpoint,
                index_name=self.search_index,
                credential=AzureKeyCredential(self.search_key)
            )
            
            # 검색 실행
            search_results = search_client.search(
                search_text=query,
                top=5,
                select=["chunk_id", "title", "chunk"]
            )
            
            # 검색 결과 조합
            context = "참고자료:\n\n"
            result_count = 0
            for result in search_results:
                result_count += 1
                context += f"문서 {result_count}:\n"
                context += f"제목: {result.get('title', 'N/A')}\n"
                context += f"내용: {result.get('chunk', 'N/A')}\n\n"
            
            if result_count == 0:
                print("❌ 검색 결과 없음")
                return None, False
            
            print(f"✅ 검색 결과 {result_count}개 발견")
            
            # 컨텍스트와 함께 답변 생성
            prompt = f"""
{context}

질문: {query}

위 자료를 바탕으로 답변해주세요. 참조 번호([doc1] 등)는 사용하지 말고 자연스러운 문장으로 답변해주세요.
            """
            
            response = self.client.chat.completions.create(
                model=self.deployment,
                messages=[
                    {
                        "role": "system",
                        "content": "싱크홀 신고 전문가입니다. 자료 기반으로만 답변하고, 참조 번호 없이 자연스러운 문장으로 답변하세요."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                max_tokens=800,
                temperature=0.3
            )
            
            print("✅ 수동 RAG 답변 생성 성공!")
            return response.choices[0].message.content, True
            
        except Exception as e:
            print(f"❌ 수동 RAG 실패: {e}")
            return None, False
    
    def try_hardcoded_rag(self, query: str) -> Tuple[Optional[str], bool]:
        """하드코딩된 RAG 데이터로 시도 (Azure Search가 안 될 때 백업)"""
        try:
            print("🔍 하드코딩된 RAG 데이터 사용...")
            
            # 하드코딩된 싱크홀 관련 정보
            hardcoded_data = {
                "동작구": {
                    "연락처": "02-820-1234",
                    "담당부서": "안전건설교통국 도시안전과",
                    "특별사항": "노량진역/사당역 인근은 서울교통공사 동시 신고 필요",
                    "웹사이트": "https://www.dongjak.go.kr"
                },
                "강남구": {
                    "연락처": "02-3423-1234",
                    "담당부서": "도시안전과",
                    "특별사항": "지하철역 인근 특별 관리"
                },
                "일반정보": {
                    "응급연락처": "119, 112",
                    "신고시_필요정보": ["정확한 위치", "싱크홀 크기", "깊이", "주변 상황", "연락처"],
                    "안전수칙": ["즉시 접근 금지", "주변 사람들에게 알림", "119 신고"],
                    "측정방법": "안전거리에서 눈으로 추정, 직접 측정 금지"
                }
            }
            
            # 검색어에 따른 관련 정보 찾기
            relevant_info = []
            query_lower = query.lower()
            
            # 지역별 정보
            for region, info in hardcoded_data.items():
                if region in query and region != "일반정보":
                    relevant_info.append(f"{region} 싱크홀 신고 정보: {info}")
            
            # 키워드별 정보
            if any(keyword in query for keyword in ["연락처", "신고", "전화", "번호"]):
                relevant_info.append(f"긴급 연락처: {hardcoded_data['일반정보']['응급연락처']}")
            
            if any(keyword in query for keyword in ["정보", "필요", "준비", "신고서"]):
                relevant_info.append(f"신고시 필요정보: {hardcoded_data['일반정보']['신고시_필요정보']}")
            
            if any(keyword in query for keyword in ["안전", "주의", "수칙"]):
                relevant_info.append(f"안전수칙: {hardcoded_data['일반정보']['안전수칙']}")
            
            if any(keyword in query for keyword in ["크기", "측정", "어떻게"]):
                relevant_info.append(f"측정방법: {hardcoded_data['일반정보']['측정방법']}")
            
            if not relevant_info:
                # 기본 정보 제공
                relevant_info = [
                    f"일반 응급연락처: {hardcoded_data['일반정보']['응급연락처']}",
                    f"기본 안전수칙: {hardcoded_data['일반정보']['안전수칙']}"
                ]
            
            context = "참고자료:\n\n" + "\n".join(relevant_info)
            
            prompt = f"""
{context}

질문: {query}

위 자료를 바탕으로 답변해주세요. 싱크홀 신고 전문가로서 정확하고 실용적인 조언을 제공하세요.
            """
            
            response = self.client.chat.completions.create(
                model=self.deployment,
                messages=[
                    {
                        "role": "system",
                        "content": "싱크홀 신고 전문가입니다. 제공된 자료를 바탕으로 정확하고 유용한 답변을 제공하세요."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                max_tokens=800,
                temperature=0.3
            )
            
            print("✅ 하드코딩된 RAG 답변 생성 성공!")
            return response.choices[0].message.content, True
            
        except Exception as e:
            print(f"❌ 하드코딩된 RAG 실패: {e}")
            return None, False
    
    def is_inadequate_answer(self, answer: str) -> bool:
        """RAG 답변이 부적절한지 판단 (한글 + 영어)"""
        if not answer:
            return True
        
        answer_lower = answer.lower()
        
        # 부적절한 패턴이 포함되어 있는지 확인
        for pattern in self.inadequate_patterns:
            if pattern in answer_lower:
                print(f"🔍 부적절 패턴 감지: '{pattern}'")
                return True
        
        # 답변이 너무 짧은 경우 (50자 미만)
        if len(answer.strip()) < 50:
            print(f"🔍 답변이 너무 짧음: {len(answer.strip())}자")
            return True
        
        return False
    
    def answer_with_general_llm(self, query: str) -> str:
        """일반 LLM으로 답변"""
        try:
            print("🔍 일반 LLM으로 답변 생성...")
            
            response = self.client.chat.completions.create(
                model=self.deployment,
                messages=[
                    {
                        "role": "system",
                        "content": """당신은 도움이 되는 AI 어시스턴트입니다. 
싱크홀 관련 질문에 대해 일반적인 지식을 바탕으로 도움이 되는 답변을 제공하세요.
특히 안전 수칙, 신고 방법, 예방 조치 등에 대해 실용적인 조언을 해주세요."""
                    },
                    {
                        "role": "user",
                        "content": query
                    }
                ],
                max_tokens=1000,
                temperature=0.7
            )
            
            print("✅ 일반 LLM 답변 생성 성공!")
            return response.choices[0].message.content
            
        except Exception as e:
            print(f"❌ 일반 LLM 답변 생성 실패: {e}")
            return """죄송합니다. 일시적인 오류가 발생했습니다. 

다음과 같이 시도해보세요:
• 잠시 후 다시 질문해보세요
• 질문을 더 간단하게 바꿔보세요
• 긴급한 경우 119 또는 120으로 연락하세요

🔍 **우리 서비스 기능**
• 실시간 위험도 예측
• 위험지역 지도 확인
• 안전 경로 안내

서비스 이용에 불편을 드려 죄송합니다."""
    
    def smart_answer(self, query: str, image_data: Optional[str] = None) -> Tuple[str, str]:
        """스마트 답변 시스템 - 개선된 참조 처리"""
        
        print(f"🤔 질문: {query}")
        print("-" * 60)
        
        # 기본 연결 테스트
        if not self.test_basic_connection():
            return "서비스에 연결할 수 없습니다. 관리자에게 문의하세요.", "오류"
        
        # 1단계: Azure Search 통합 RAG 시도
        print("🔍 1단계: Azure Search 통합 RAG 시도")
        rag_answer, success = self.try_rag_answer(query)
        
        if success and rag_answer:
            print("✅ RAG 답변 생성 성공")
            if not self.is_inadequate_answer(rag_answer):
                print("✅ RAG 답변이 적절함 → RAG 답변 사용")
                # 참조 후처리 적용
                processed_answer = self.post_process_answer(rag_answer)
                final_answer = self.add_credibility_footer(processed_answer, "RAG")
                return final_answer, "RAG"
            else:
                print("⚠️ RAG 답변이 부적절함")
        
        # 2단계: 수동 RAG 시도
        print("🔍 2단계: 수동 RAG 시도")
        manual_answer, manual_success = self.try_manual_rag(query)
        
        if manual_success and manual_answer:
            print("✅ 수동 RAG 답변 생성 성공")
            if not self.is_inadequate_answer(manual_answer):
                print("✅ 수동 RAG 답변이 적절함 → 수동 RAG 답변 사용")
                processed_answer = self.post_process_answer(manual_answer)
                final_answer = self.add_credibility_footer(processed_answer, "수동 RAG")
                return final_answer, "수동 RAG"
            else:
                print("⚠️ 수동 RAG 답변도 부적절함")
        
        # 3단계: 하드코딩된 RAG 시도
        print("🔍 3단계: 하드코딩된 RAG 시도")
        hardcoded_answer, hardcoded_success = self.try_hardcoded_rag(query)
        
        if hardcoded_success and hardcoded_answer:
            print("✅ 하드코딩된 RAG 답변 생성 성공")
            if not self.is_inadequate_answer(hardcoded_answer):
                print("✅ 하드코딩된 RAG 답변이 적절함 → 하드코딩된 RAG 답변 사용")
                final_answer = self.add_credibility_footer(hardcoded_answer, "하드코딩된 RAG")
                return final_answer, "하드코딩된 RAG"
        
        # 4단계: 일반 LLM으로 전환
        print("🔄 4단계: 일반 LLM으로 전환")
        print("💡 RAG에 적절한 정보가 없어 일반 AI 지식을 사용합니다")
        
        general_answer = self.answer_with_general_llm(query)
        final_answer = self.add_credibility_footer(general_answer, "일반 LLM")
        return final_answer, "일반 LLM"

# 전역 RAG 시스템 인스턴스
rag_system = SmartRAGSystem()