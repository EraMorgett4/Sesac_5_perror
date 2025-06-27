# backend/destination_processor.py
# 목적지 텍스트 정제 및 검색 정확도 향상을 위한 백엔드 모듈

import re
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class ProcessedDestination:
    """정제된 목적지 정보"""
    original_text: str
    cleaned_text: str
    confidence_score: float
    extracted_keywords: List[str]
    location_type: str
    suggested_searches: List[str]

class DestinationProcessor:
    """목적지 텍스트 정제 및 분석 클래스"""
    
    def __init__(self):
        # 장소 유형별 키워드 패턴
        self.location_patterns = {
            'station': {
                'keywords': ['역', '지하철역', '전철역', '기차역'],
                'suffixes': ['역'],
                'confidence_boost': 0.3
            },
            'university': {
                'keywords': ['대학교', '대학', '캠퍼스', '학교'],
                'suffixes': ['대학교', '대학', '대'],
                'confidence_boost': 0.25
            },
            'hospital': {
                'keywords': ['병원', '의료원', '클리닉', '의원'],
                'suffixes': ['병원', '의료원', '의원'],
                'confidence_boost': 0.25
            },
            'building': {
                'keywords': ['빌딩', '타워', '센터', '플라자', '몰'],
                'suffixes': ['빌딩', '타워', '센터', 'B', '몰'],
                'confidence_boost': 0.2
            },
            'district': {
                'keywords': ['구', '동', '읍', '면', '리'],
                'suffixes': ['구', '동', '읍', '면', '리'],
                'confidence_boost': 0.15
            },
            'landmark': {
                'keywords': ['공원', '시장', '터미널', '공항', '항구'],
                'suffixes': ['공원', '시장', '터미널', '공항', '항구'],
                'confidence_boost': 0.2
            }
        }
        
        # 불필요한 표현 패턴
        self.noise_patterns = [
            # 감탄사 및 시작 표현
            r'^(음|어|그|저|아|네|예|자|뭐|어디|여기|저기)\s*',
            
            # 이동 관련 표현
            r'\s*(가고\s*싶어|가려고|가줘|가자|갈래|가볼래|가보자)',
            r'\s*(로\s*가|에\s*가|까지\s*가|으로\s*가)',
            r'\s*(이동|출발|도착|가는|향하는)',
            
            # 정중한 표현
            r'\s*(입니다|습니다|해주세요|주세요|부탁|드려요)',
            r'\s*(해줘|줘|좀|좀더|조금)',
            
            # 기타 불필요한 표현
            r'\s*\.$',  # 마침표
            r'\s*[?!]+$',  # 물음표, 느낌표
            r'\s*(하고|하는|한|할|했)',
            r'\s*(것|거|게|께|꺼)',
        ]
        
        # 한국 주요 지역명 (신뢰도 향상용)
        self.major_locations = {
            '서울': ['강남', '홍대', '명동', '신촌', '이태원', '압구정', '청담', '삼성'],
            '부산': ['해운대', '서면', '남포동', '광안리'],
            '대구': ['동성로', '수성구'],
            '인천': ['송도', '부평', '구월동'],
            '광주': ['상무지구', '충장로'],
            '대전': ['유성', '둔산'],
            '울산': ['삼산동', '성남동'],
            '세종': ['조치원', '한솔동']
        }

    def process_destination(self, text: str) -> ProcessedDestination:
        """
        목적지 텍스트를 종합적으로 정제하고 분석
        
        Args:
            text: 원본 음성 인식 텍스트
            
        Returns:
            ProcessedDestination: 정제된 목적지 정보
        """
        logger.info(f"목적지 텍스트 정제 시작: '{text}'")
        
        original_text = text.strip()
        
        # 1단계: 기본 정제
        cleaned_text = self._basic_cleaning(original_text)
        
        # 2단계: 노이즈 제거
        cleaned_text = self._remove_noise(cleaned_text)
        
        # 3단계: 핵심 목적지 추출
        cleaned_text = self._extract_destination_core(cleaned_text)
        
        # 4단계: 장소 유형 분석
        location_type, confidence_boost = self._analyze_location_type(cleaned_text)
        
        # 5단계: 키워드 추출
        keywords = self._extract_keywords(cleaned_text, location_type)
        
        # 6단계: 신뢰도 계산
        confidence = self._calculate_confidence(cleaned_text, location_type, confidence_boost)
        
        # 7단계: 검색 제안 생성
        suggested_searches = self._generate_search_suggestions(cleaned_text, location_type, keywords)
        
        result = ProcessedDestination(
            original_text=original_text,
            cleaned_text=cleaned_text,
            confidence_score=confidence,
            extracted_keywords=keywords,
            location_type=location_type,
            suggested_searches=suggested_searches
        )
        
        logger.info(f"정제 완료: '{original_text}' → '{cleaned_text}' (신뢰도: {confidence:.2f})")
        
        return result

    def _basic_cleaning(self, text: str) -> str:
        """기본적인 텍스트 정제"""
        # 공백 정규화
        text = re.sub(r'\s+', ' ', text).strip()
        
        # 특수문자 정리 (한글, 영문, 숫자, 기본 기호만 유지)
        text = re.sub(r'[^\w\s가-힣ㄱ-ㅎㅏ-ㅣ\-()]', '', text)
        
        return text

    def _remove_noise(self, text: str) -> str:
        """불필요한 표현 제거"""
        for pattern in self.noise_patterns:
            text = re.sub(pattern, '', text, flags=re.IGNORECASE)
        
        return text.strip()

    def _extract_destination_core(self, text: str) -> str:
        """핵심 목적지명 추출"""
        # 장소명 + 유형 패턴 매칭
        destination_patterns = [
            # 역 패턴
            r'(.{1,10}?)\s*(?:지하철|전철|기차)?\s*(역)',
            
            # 대학교 패턴
            r'(.{1,15}?)\s*(대학교|대학|대)',
            
            # 병원 패턴
            r'(.{1,15}?)\s*(병원|의료원|의원|클리닉)',
            
            # 빌딩/센터 패턴
            r'(.{1,15}?)\s*(빌딩|타워|센터|플라자|몰)',
            
            # 지역 패턴
            r'(.{1,10}?)\s*(구|동|읍|면|리)',
            
            # 랜드마크 패턴
            r'(.{1,15}?)\s*(공원|시장|터미널|공항|항구)',
            
            # 일반 장소명 (최소 2글자)
            r'([가-힣]{2,})'
        ]
        
        for pattern in destination_patterns:
            match = re.search(pattern, text)
            if match:
                if len(match.groups()) == 2:
                    # 장소명 + 유형
                    place_name = match.group(1).strip()
                    place_type = match.group(2).strip()
                    if len(place_name) >= 1:
                        return f"{place_name}{place_type}"
                else:
                    # 장소명만
                    place_name = match.group(1).strip()
                    if len(place_name) >= 2:
                        return place_name
        
        # 패턴 매칭 실패시 원본 반환 (최소 길이 체크)
        if len(text) >= 2:
            return text
        
        return ""

    def _analyze_location_type(self, text: str) -> Tuple[str, float]:
        """장소 유형 분석 및 신뢰도 부스트 값 반환"""
        for location_type, config in self.location_patterns.items():
            # 키워드 검사
            for keyword in config['keywords']:
                if keyword in text:
                    return location_type, config['confidence_boost']
            
            # 접미사 검사
            for suffix in config['suffixes']:
                if text.endswith(suffix):
                    return location_type, config['confidence_boost']
        
        return 'general', 0.0

    def _extract_keywords(self, text: str, location_type: str) -> List[str]:
        """검색에 유용한 키워드 추출"""
        keywords = []
        
        # 기본 키워드 (전체 텍스트)
        keywords.append(text)
        
        # 유형별 추가 키워드
        if location_type in self.location_patterns:
            config = self.location_patterns[location_type]
            for suffix in config['suffixes']:
                if text.endswith(suffix):
                    # 접미사 제거한 버전
                    base_name = text[:-len(suffix)].strip()
                    if len(base_name) >= 2:
                        keywords.append(base_name)
        
        # 주요 지역명 확인
        for city, districts in self.major_locations.items():
            if any(district in text for district in districts):
                keywords.append(city)
        
        return list(set(keywords))  # 중복 제거

    def _calculate_confidence(self, text: str, location_type: str, confidence_boost: float) -> float:
        """텍스트 신뢰도 계산 (0~1)"""
        confidence = 0.5  # 기본 신뢰도
        
        # 길이에 따른 신뢰도
        if len(text) >= 2:
            confidence += 0.1
        if len(text) >= 4:
            confidence += 0.1
        if len(text) >= 6:
            confidence += 0.1
        
        # 한글 비율
        korean_chars = len(re.findall(r'[가-힣]', text))
        if korean_chars > 0:
            korean_ratio = korean_chars / len(text.replace(' ', ''))
            confidence += korean_ratio * 0.2
        
        # 장소 유형 보너스
        confidence += confidence_boost
        
        # 주요 지역명 보너스
        for districts in self.major_locations.values():
            if any(district in text for district in districts):
                confidence += 0.15
                break
        
        # 특수 패턴 페널티
        if re.search(r'[0-9]+', text):  # 숫자 포함
            confidence -= 0.1
        if len(text) < 2:  # 너무 짧음
            confidence -= 0.3
        if re.search(r'[a-zA-Z]{3,}', text):  # 긴 영문
            confidence -= 0.1
        
        return max(0.0, min(1.0, confidence))

    def _generate_search_suggestions(self, text: str, location_type: str, keywords: List[str]) -> List[str]:
        """지오코딩/검색 API용 제안 생성"""
        suggestions = []
        
        # 1. 원본 텍스트
        suggestions.append(text)
        
        # 2. 키워드 조합
        for keyword in keywords:
            if keyword != text:
                suggestions.append(keyword)
        
        # 3. 유형별 변형
        if location_type == 'station':
            if not text.endswith('역'):
                suggestions.append(f"{text}역")
            suggestions.append(f"{text}지하철역")
        elif location_type == 'university':
            if not any(text.endswith(suffix) for suffix in ['대학교', '대학', '대']):
                suggestions.append(f"{text}대학교")
        elif location_type == 'hospital':
            if not text.endswith('병원'):
                suggestions.append(f"{text}병원")
        
        # 4. 지역명 조합
        for city, districts in self.major_locations.items():
            if any(district in text for district in districts):
                suggestions.append(f"{city} {text}")
        
        # 중복 제거 및 길이 필터링
        suggestions = list(set(suggestions))
        suggestions = [s for s in suggestions if len(s.strip()) >= 2]
        
        # 신뢰도 순으로 정렬 (원본 우선, 짧은 것 우선)
        suggestions.sort(key=lambda x: (x != text, len(x)))
        
        return suggestions[:5]  # 최대 5개

    def batch_process(self, texts: List[str]) -> List[ProcessedDestination]:
        """여러 텍스트 일괄 처리"""
        return [self.process_destination(text) for text in texts]

    def validate_destination(self, text: str, min_confidence: float = 0.6) -> bool:
        """목적지 유효성 검증"""
        result = self.process_destination(text)
        return result.confidence_score >= min_confidence

# 전역 프로세서 인스턴스
destination_processor = DestinationProcessor()

def process_destination_text(text: str) -> Dict:
    """
    FastAPI용 래퍼 함수
    
    Args:
        text: 음성 인식된 목적지 텍스트
        
    Returns:
        Dict: 정제 결과
    """
    try:
        result = destination_processor.process_destination(text)
        
        return {
            "success": True,
            "original_text": result.original_text,
            "cleaned_text": result.cleaned_text,
            "confidence_score": result.confidence_score,
            "location_type": result.location_type,
            "keywords": result.extracted_keywords,
            "search_suggestions": result.suggested_searches,
            "is_valid": result.confidence_score >= 0.6
        }
    
    except Exception as e:
        logger.error(f"목적지 처리 오류: {e}")
        return {
            "success": False,
            "error": str(e),
            "original_text": text,
            "cleaned_text": "",
            "confidence_score": 0.0
        }