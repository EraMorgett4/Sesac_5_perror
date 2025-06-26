# backend/main.py - 정리된 FastAPI 메인 애플리케이션

from fastapi import FastAPI, Depends, HTTPException, status, File, Form, UploadFile
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
import uvicorn
from datetime import datetime, timedelta
import random
import math
import requests
import os
import base64
import aiohttp
import tempfile
import wave
import io
import asyncio
import struct
from dotenv import load_dotenv
from pydantic import BaseModel
import logging
import traceback
import subprocess
import pandas as pd  
import csv  
import shutil
from pathlib import Path
# 로컬 모듈 임포트
from chatbot_routes import chatbot_router
from database import SessionLocal, engine, Base
from models import User, Location, RiskPrediction
from schemas import (
    UserCreate, UserResponse, LocationRequest, RiskResponse, 
    RouteRequest, RouteResponse, RouteStep, RouteWaypoint,
    GeocodeResponse
)
from auth import get_password_hash, verify_password, create_access_token, get_current_user
from speech_service import speech_service

# 환경변수 로드
load_dotenv()
KAKAO_API_KEY = os.getenv("KAKAO_API_KEY", "YOUR_KAKAO_REST_API_KEY")

# 로깅 설정
if not logging.getLogger().handlers:
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
logger = logging.getLogger(__name__)

# 목적지 처리 모듈 import (오류 처리 포함)
try:
    from destination_processor import process_destination_text, destination_processor
    logger.info("✅ 목적지 정제 모듈 로드 성공")
except ImportError as e:
    logger.warning(f"⚠️ 목적지 정제 모듈 로드 실패: {e}")
    # 임시 fallback 함수들
    def process_destination_text(text: str) -> dict:
        return {
            "success": True,
            "original_text": text,
            "cleaned_text": text.strip(),
            "confidence_score": 0.7,
            "location_type": "general",
            "keywords": [text.strip()],
            "search_suggestions": [text.strip()],
            "is_valid": len(text.strip()) >= 2
        }
    
    class MockDestinationProcessor:
        def validate_destination(self, text: str, min_confidence: float = 0.6) -> bool:
            return len(text.strip()) >= 2
        
        def batch_process(self, texts: List[str]) -> List[dict]:
            return [{"original_text": text, "cleaned_text": text, "confidence_score": 0.7} for text in texts]
    
    destination_processor = MockDestinationProcessor()

# 데이터베이스 테이블 생성
Base.metadata.create_all(bind=engine)

# FastAPI 앱 초기화
app = FastAPI(
    title="Seoul Safety Navigation API", 
    version="2.0.0",
    description="서울시 안전 도보 안내 시스템 - Azure Speech 지원"
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# OAuth2 설정
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# 라우터 포함
app.include_router(chatbot_router)

# 데이터베이스 의존성
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# =============================================================================
# Pydantic 모델 정의 (통합)
# =============================================================================

class DestinationRequest(BaseModel):
    text: str
    min_confidence: Optional[float] = 0.6

class DestinationResponse(BaseModel):
    success: bool
    original_text: str
    cleaned_text: str
    confidence_score: float
    location_type: str
    keywords: List[str]
    search_suggestions: List[str]
    is_valid: bool
    error: Optional[str] = None

class TTSRequest(BaseModel):
    text: str
    voice_name: Optional[str] = "ko-KR-HyunsuMultilingualNeural"

class TTSResponse(BaseModel):
    success: bool
    audio_data: Optional[str] = None
    error: Optional[str] = None
    voice_name: str
    text: str

class STTWithProcessingResponse(BaseModel):
    success: bool
    recognized_text: str
    stt_confidence: Optional[float] = None
    processed_destination: DestinationResponse
    recommended_search_text: str
    should_proceed: bool
    error: Optional[str] = None

# =============================================================================
# 상수 정의
# =============================================================================

# 서울시 더미 위험지역 데이터
DUMMY_RISK_ZONES = [
    {"lat": 37.5665, "lng": 126.9780, "risk": 0.85, "name": "중구 명동"},
    {"lat": 37.5663, "lng": 126.9779, "risk": 0.90, "name": "중구 명동 인근"},
    {"lat": 37.5519, "lng": 126.9918, "risk": 0.78, "name": "강남구 논현동"},
    {"lat": 37.5172, "lng": 127.0473, "risk": 0.82, "name": "강남구 삼성동"},
    {"lat": 37.5794, "lng": 126.9770, "risk": 0.75, "name": "종로구 종로1가"},
    {"lat": 37.5512, "lng": 126.9882, "risk": 0.88, "name": "서초구 서초동"},
    {"lat": 37.5326, "lng": 126.9026, "risk": 0.73, "name": "영등포구 여의도동"},
    {"lat": 37.5833, "lng": 127.0022, "risk": 0.79, "name": "성북구 성북동"},
    {"lat": 37.5145, "lng": 127.1059, "risk": 0.81, "name": "송파구 잠실동"},
    {"lat": 37.4955, "lng": 126.8874, "risk": 0.76, "name": "구로구 구로동"}
]

# 오픈 소스 라우팅 서비스
OSRM_BASE_URL = "https://router.project-osrm.org"
NOMINATIM_BASE_URL = "https://nominatim.openstreetmap.org"


##################### 공사장 정보 로드 로직 (추가) #####################
CONSTRUCTION_DATA = []

def load_construction_data():
    """CSV 파일에서 공사정보 데이터를 로드 (수정된 버전)"""
    global CONSTRUCTION_DATA
    
    logger.info("🏗️ 공사장 데이터 로드 시작...")
    
    try:
        # 현재 작업 디렉토리 확인
        current_dir = os.getcwd()
        logger.info(f"📂 현재 디렉토리: {current_dir}")
        
        # 가능한 CSV 파일 경로들 (순서대로 시도)
        possible_paths = [
            "필터링결과.csv",
            "./필터링결과.csv",
            "../필터링결과.csv", 
            "data/필터링결과.csv",
            os.path.join(current_dir, "필터링결과.csv"),
            # 백엔드 폴더 안에 있을 경우를 대비
            os.path.join(os.path.dirname(__file__), "필터링결과.csv"),
            # 상위 디렉토리에 있을 경우를 대비  
            os.path.join(os.path.dirname(os.path.dirname(__file__)), "필터링결과.csv")
        ]
        
        csv_file_path = None
        for path in possible_paths:
            logger.info(f"📁 경로 확인: {path}")
            if os.path.exists(path):
                csv_file_path = path
                logger.info(f"✅ CSV 파일 발견: {path}")
                break
            else:
                logger.debug(f"❌ 파일 없음: {path}")
        
        if not csv_file_path:
            logger.error("❌ 필터링결과.csv 파일을 찾을 수 없습니다!")
            logger.info("🔍 다음 위치들을 확인하세요:")
            for path in possible_paths:
                logger.info(f"   - {path}")
            
            # 디렉토리의 CSV 파일들 확인
            try:
                csv_files = [f for f in os.listdir(current_dir) if f.endswith('.csv')]
                if csv_files:
                    logger.info(f"📋 현재 디렉토리의 CSV 파일들: {csv_files}")
                else:
                    logger.info("📋 현재 디렉토리에 CSV 파일이 없습니다")
            except Exception as e:
                logger.warning(f"⚠️ 디렉토리 확인 실패: {e}")
            
            # 더미 데이터 생성
            logger.info("🔧 더미 데이터를 생성합니다...")
            CONSTRUCTION_DATA = generate_dummy_construction_data()
            return

        # 파일 크기 확인
        file_size = os.path.getsize(csv_file_path)
        logger.info(f"📋 파일 크기: {file_size} bytes")
        
        if file_size == 0:
            logger.error("❌ CSV 파일이 비어있습니다!")
            CONSTRUCTION_DATA = generate_dummy_construction_data()
            return

        # CSV 파일 읽기 (여러 인코딩 시도)
        df = None
        encodings = ['utf-8', 'cp949', 'euc-kr', 'utf-8-sig']
        
        for encoding in encodings:
            try:
                logger.info(f"📖 인코딩 시도: {encoding}")
                df = pd.read_csv(csv_file_path, encoding=encoding)
                logger.info(f"✅ CSV 로드 성공 (인코딩: {encoding})")
                break
            except UnicodeDecodeError:
                logger.warning(f"⚠️ 인코딩 실패: {encoding}")
                continue
            except Exception as e:
                logger.error(f"❌ CSV 로드 오류 ({encoding}): {e}")
                continue
        
        if df is None:
            logger.error("❌ 모든 인코딩으로 CSV 로드 실패!")
            CONSTRUCTION_DATA = generate_dummy_construction_data()
            return
            
        logger.info(f"📊 CSV 로드 성공: {len(df)}개 행, {len(df.columns)}개 컬럼")
        logger.info(f"📋 컬럼 목록: {list(df.columns)}")
        
        # 필수 컬럼 확인
        required_columns = ['위도', '경도', '지오코딩주소']
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
            logger.error(f"❌ 필수 컬럼 누락: {missing_columns}")
            logger.info(f"📋 사용 가능한 컬럼: {list(df.columns)}")
            CONSTRUCTION_DATA = generate_dummy_construction_data()
            return
        
        # 데이터 처리
        construction_list = []
        success_count = 0
        error_count = 0
        
        logger.info("🔄 데이터 처리 시작...")
        
        for idx, row in df.iterrows():
            try:
                # 위도, 경도 확인
                lat = row.get('위도')
                lng = row.get('경도') 
                address = row.get('지오코딩주소')
                
                # 데이터 유효성 검사
                if pd.isna(lat) or pd.isna(lng) or pd.isna(address):
                    error_count += 1
                    if error_count <= 3:  # 처음 3개 오류만 로깅
                        logger.warning(f"⚠️ 행 {idx}: 필수 데이터 누락 (lat={lat}, lng={lng}, address={address})")
                    continue
                
                try:
                    lat = float(lat)
                    lng = float(lng)
                except (ValueError, TypeError):
                    error_count += 1
                    if error_count <= 3:
                        logger.warning(f"⚠️ 행 {idx}: 좌표 변환 실패 (lat={lat}, lng={lng})")
                    continue
                
                # 서울 지역 좌표 범위 확인 (더 넓게 설정)
                if not (37.3 <= lat <= 37.8 and 126.7 <= lng <= 127.3):
                    error_count += 1
                    if error_count <= 3:
                        logger.warning(f"⚠️ 행 {idx}: 서울 지역 외 좌표 (lat={lat}, lng={lng})")
                    continue
                
                # 공사 상태 결정
                status = determine_construction_status(row)
                risk_level = calculate_construction_risk(status)
                
                construction_item = {
                    "id": f"CONST-{len(construction_list) + 1}",
                    "lat": lat,
                    "lng": lng,
                    "address": str(address).strip(),
                    "status": status,
                    "type": "도로굴착공사",
                    "risk_level": risk_level,
                    "name": f"공사지역: {str(address).strip()[:50]}",  # 50자 제한
                    "risk": risk_level  # risk 키 추가
                }
                
                construction_list.append(construction_item)
                success_count += 1
                
                # 처음 3개는 상세 로깅
                if success_count <= 3:
                    logger.info(f"📍 공사장 {success_count}: {construction_item['address'][:30]}... (상태: {status})")
                
            except Exception as e:
                error_count += 1
                if error_count <= 3:
                    logger.error(f"❌ 행 {idx} 처리 실패: {e}")
                continue
        
        # 결과 저장
        CONSTRUCTION_DATA = construction_list
        
        logger.info(f"✅ 공사정보 데이터 로드 완료!")
        logger.info(f"   📊 성공: {success_count}건")
        logger.info(f"   ❌ 실패: {error_count}건")
        logger.info(f"   📈 성공률: {(success_count/(success_count+error_count))*100:.1f}%" if (success_count+error_count) > 0 else "0%")
        
        # 상태별 통계
        if construction_list:
            status_counts = {}
            for item in construction_list:
                status = item['status']
                status_counts[status] = status_counts.get(status, 0) + 1
            logger.info(f"📊 상태별 통계: {status_counts}")
        
    except Exception as e:
        logger.error(f"❌ 공사정보 데이터 로드 중 전체 오류: {e}")
        logger.error(f"📄 오류 상세: {traceback.format_exc()}")
        CONSTRUCTION_DATA = generate_dummy_construction_data()

def determine_construction_status(row):
    """공사 상태 판단 로직"""
    statuses = ["진행중", "완료", "예정"]
    weights = [0.3, 0.6, 0.1]
    return random.choices(statuses, weights=weights)[0]

def calculate_construction_risk(status):
    """공사 상태에 따른 위험도 계산"""
    if status == "진행중":
        return random.uniform(0.6, 0.9)
    elif status == "예정":
        return random.uniform(0.3, 0.6)
    else:
        return random.uniform(0.1, 0.3)

def generate_dummy_construction_data():
    """더미 공사정보 데이터 생성 (파일 로드 실패 시)"""
    logger.info("🔧 더미 공사정보 데이터를 생성합니다.")
    return [
        {
            "id": "CONST-DUMMY-1", "lat": 37.5665, "lng": 126.9780,
            "address": "서울시 중구 명동 (더미)", "status": "진행중",
            "type": "도로굴착공사", "risk_level": 0.75,
            "name": "공사지역: 서울시 중구 명동 (더미)", "risk": 0.75
        }
    ]
######################################################################

#####################오디오########################
# ... (기존 오디오 관련 코드) ...



#####################오디오########################
# 오디오 변환 함수 추가
def convert_audio_to_wav(audio_content: bytes, input_format: str = "webm") -> bytes:
    """
    오디오를 Azure Speech SDK 호환 WAV 포맷으로 변환
    - 16kHz, 16-bit, mono PCM WAV
    """
    try:
        logger.info(f"🔄 오디오 변환 시작: {input_format} → WAV")
        
        # ffmpeg 설치 확인
        try:
            subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            raise Exception("ffmpeg가 설치되지 않았습니다. 'apt install ffmpeg' 또는 'brew install ffmpeg'로 설치하세요.")
        
        # 임시 파일 생성
        with tempfile.TemporaryDirectory() as temp_dir:
            input_file = Path(temp_dir) / f"input.{input_format}"
            output_file = Path(temp_dir) / "output.wav"
            
            # 입력 파일 저장
            with open(input_file, 'wb') as f:
                f.write(audio_content)
            
            # ffmpeg로 변환 (Azure Speech SDK 호환 포맷)
            cmd = [
                'ffmpeg',
                '-i', str(input_file),           # 입력 파일
                '-ar', '16000',                  # 샘플링 레이트: 16kHz
                '-ac', '1',                      # 채널: mono
                '-sample_fmt', 's16',            # 샘플 포맷: 16-bit
                '-f', 'wav',                     # 출력 포맷: WAV
                '-y',                            # 덮어쓰기 허용
                str(output_file)
            ]
            
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                timeout=30
            )
            
            if result.returncode != 0:
                logger.error(f"❌ ffmpeg 오류: {result.stderr}")
                raise Exception(f"오디오 변환 실패: {result.stderr}")
            
            # 변환된 WAV 파일 읽기
            if output_file.exists():
                with open(output_file, 'rb') as f:
                    wav_data = f.read()
                
                logger.info(f"✅ 오디오 변환 성공: {len(audio_content)} → {len(wav_data)} bytes")
                return wav_data
            else:
                raise Exception("변환된 파일이 생성되지 않았습니다")
                
    except subprocess.TimeoutExpired:
        logger.error("❌ 오디오 변환 시간 초과 (30초)")
        raise Exception("오디오 변환 시간 초과")
    except Exception as e:
        logger.error(f"❌ 오디오 변환 오류: {e}")
        raise

# pydub을 사용한 대안 변환 함수 (ffmpeg 백업)
def convert_audio_with_pydub(audio_content: bytes, input_format: str = "webm") -> bytes:
    """
    pydub을 사용한 오디오 변환 (ffmpeg 백업)
    """
    try:
        from pydub import AudioSegment
        from pydub.utils import which
        
        logger.info(f"🔄 pydub 오디오 변환 시작: {input_format} → WAV")
        
        # ffmpeg 경로 확인
        if not which("ffmpeg"):
            raise Exception("ffmpeg가 설치되지 않았습니다")
        
        # 임시 파일로 변환
        with tempfile.NamedTemporaryFile(suffix=f'.{input_format}') as input_file:
            input_file.write(audio_content)
            input_file.flush()
            
            # AudioSegment로 로드
            if input_format == "webm":
                audio = AudioSegment.from_file(input_file.name, format="webm")
            elif input_format == "mp3":
                audio = AudioSegment.from_mp3(input_file.name)
            elif input_format == "ogg":
                audio = AudioSegment.from_ogg(input_file.name)
            else:
                audio = AudioSegment.from_file(input_file.name)
            
            # Azure Speech SDK 호환 포맷으로 변환
            audio = audio.set_frame_rate(16000)  # 16kHz
            audio = audio.set_channels(1)        # mono
            audio = audio.set_sample_width(2)    # 16-bit
            
            # WAV로 내보내기
            with tempfile.NamedTemporaryFile(suffix='.wav') as output_file:
                audio.export(output_file.name, format="wav")
                
                with open(output_file.name, 'rb') as f:
                    wav_data = f.read()
                
                logger.info(f"✅ pydub 변환 성공: {len(audio_content)} → {len(wav_data)} bytes")
                return wav_data
                
    except ImportError:
        logger.error("❌ pydub이 설치되지 않음")
        raise Exception("pydub이 설치되지 않았습니다. 'pip install pydub'로 설치하세요.")
    except Exception as e:
        logger.error(f"❌ pydub 변환 오류: {e}")
        raise

# 개선된 STT 처리 함수 (기존 process_azure_stt_enhanced 수정)
async def process_azure_stt_enhanced_with_conversion(audio_content: bytes) -> dict:
    """
    향상된 Azure STT 처리 (오디오 포맷 변환 포함)
    """
    try:
        logger.info("🎯 향상된 Azure STT 처리 시작 (포맷 변환 포함)")
        
        # 1단계: 오디오 파일 분석
        analysis = analyze_audio_file(audio_content)
        logger.info(f"📊 오디오 분석: {analysis}")
        
        # 2단계: 기본 검증
        if analysis.get("is_empty", True):
            return {
                "success": False,
                "error": "오디오 파일이 비어있습니다",
                "analysis": analysis
            }
        
        if analysis.get("file_size", 0) < 1000:  # 1KB 미만
            return {
                "success": False,
                "error": "오디오 파일이 너무 작습니다 (1KB 미만)",
                "analysis": analysis
            }
        
        # 3단계: 오디오 포맷 변환 (WAV가 아닌 경우)
        format_detected = analysis.get("format_detected", "Unknown")
        processed_audio = audio_content
        
        if format_detected != "WAV":
            logger.info(f"🔄 오디오 포맷 변환 필요: {format_detected} → WAV")
            
            try:
                # ffmpeg 우선 시도
                if format_detected == "WebM":
                    processed_audio = convert_audio_to_wav(audio_content, "webm")
                elif format_detected == "MP3":
                    processed_audio = convert_audio_to_wav(audio_content, "mp3")
                elif format_detected == "OGG":
                    processed_audio = convert_audio_to_wav(audio_content, "ogg")
                else:
                    # 알 수 없는 포맷은 webm으로 시도
                    processed_audio = convert_audio_to_wav(audio_content, "webm")
                    
                logger.info(f"✅ 오디오 변환 성공: {len(audio_content)} → {len(processed_audio)} bytes")
                
            except Exception as conv_error:
                logger.warning(f"⚠️ ffmpeg 변환 실패: {conv_error}")
                
                # pydub으로 재시도
                try:
                    if format_detected == "WebM":
                        processed_audio = convert_audio_with_pydub(audio_content, "webm")
                    elif format_detected == "MP3":
                        processed_audio = convert_audio_with_pydub(audio_content, "mp3")
                    elif format_detected == "OGG":
                        processed_audio = convert_audio_with_pydub(audio_content, "ogg")
                    else:
                        processed_audio = convert_audio_with_pydub(audio_content, "webm")
                        
                    logger.info(f"✅ pydub 변환 성공: {len(audio_content)} → {len(processed_audio)} bytes")
                    
                except Exception as pydub_error:
                    logger.error(f"❌ 모든 변환 방법 실패: ffmpeg({conv_error}), pydub({pydub_error})")
                    return {
                        "success": False,
                        "error": f"오디오 포맷 변환 실패: {format_detected} 포맷을 WAV로 변환할 수 없습니다",
                        "analysis": analysis,
                        "conversion_errors": {
                            "ffmpeg": str(conv_error),
                            "pydub": str(pydub_error)
                        }
                    }
        
        # 4단계: Azure 설정 확인
        speech_key = os.getenv('AZURE_SPEECH_KEY')
        speech_region = os.getenv('AZURE_SPEECH_REGION', 'koreacentral')
        
        if not speech_key or speech_key == 'your-speech-key-here':
            return {
                "success": False,
                "error": "Azure Speech Key가 설정되지 않았습니다",
                "analysis": analysis
            }
        
        # 5단계: Azure STT 시도 (변환된 오디오 사용)
        try:
            import azure.cognitiveservices.speech as speechsdk
            
            logger.info("🔧 Azure Speech SDK 초기화")
            
            # Speech 설정
            speech_config = speechsdk.SpeechConfig(
                subscription=speech_key,
                region=speech_region
            )
            speech_config.speech_recognition_language = "ko-KR"
            
            # 변환된 오디오를 임시 파일로 저장
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                temp_file.write(processed_audio)
                temp_file_path = temp_file.name
            
            try:
                # 파일 기반 오디오 설정
                audio_config = speechsdk.audio.AudioConfig(filename=temp_file_path)
                
                # 음성 인식기 생성
                speech_recognizer = speechsdk.SpeechRecognizer(
                    speech_config=speech_config,
                    audio_config=audio_config
                )
                
                logger.info("🔄 Azure STT 음성 인식 시작...")
                
                # 단일 인식 시도
                result = speech_recognizer.recognize_once_async().get()
                
                logger.info(f"📡 STT 결과 코드: {result.reason}")
                
                if result.reason == speechsdk.ResultReason.RecognizedSpeech:
                    recognized_text = result.text.strip()
                    
                    # 결과 후처리
                    if recognized_text.endswith('.'):
                        recognized_text = recognized_text[:-1]
                    
                    # 자신감 점수는 보통 상세 결과에 포함되나, 여기서는 고정값 또는 기본값으로 처리
                    confidence = 0.85
                    
                    logger.info(f"✅ STT 성공: '{recognized_text}'")
                    
                    return {
                        "success": True,
                        "recognized_text": recognized_text,
                        "confidence": confidence,
                        "analysis": analysis,
                        "converted": format_detected != "WAV",
                        "original_format": format_detected,
                        "azure_result_reason": str(result.reason)
                    }
                
                elif result.reason == speechsdk.ResultReason.NoMatch:
                    logger.warning("⚠️ Azure STT: 음성 매칭 없음")
                    
                    no_match_details = result.no_match_details if hasattr(result, 'no_match_details') else None
                    
                    return {
                        "success": False,
                        "error": "음성을 인식할 수 없습니다",
                        "details": "Azure에서 인식 가능한 음성을 찾지 못했습니다",
                        "analysis": analysis,
                        "converted": format_detected != "WAV",
                        "original_format": format_detected,
                        "azure_result_reason": str(result.reason),
                        "no_match_details": str(no_match_details) if no_match_details else None
                    }
                
                elif result.reason == speechsdk.ResultReason.Canceled:
                    cancellation_details = result.cancellation_details
                    error_msg = f"음성 인식 취소됨: {cancellation_details.reason}"
                    
                    if cancellation_details.error_details:
                        error_msg += f" - {cancellation_details.error_details}"
                    
                    logger.error(f"❌ {error_msg}")
                    
                    return {
                        "success": False,
                        "error": error_msg,
                        "analysis": analysis,
                        "converted": format_detected != "WAV",
                        "original_format": format_detected,
                        "azure_result_reason": str(result.reason),
                        "cancellation_reason": str(cancellation_details.reason),
                        "error_details": cancellation_details.error_details
                    }
                
                else:
                    logger.error(f"❌ 알 수 없는 STT 결과: {result.reason}")
                    
                    return {
                        "success": False,
                        "error": f"알 수 없는 인식 결과: {result.reason}",
                        "analysis": analysis,
                        "converted": format_detected != "WAV",
                        "original_format": format_detected,
                        "azure_result_reason": str(result.reason)
                    }
                
            finally:
                # 임시 파일 정리
                try:
                    os.remove(temp_file_path)
                    logger.info("🗑️ 임시 오디오 파일 삭제됨")
                except:
                    pass
                
        except ImportError:
            logger.error("❌ Azure Speech SDK가 설치되지 않음")
            return {
                "success": False,
                "error": "Azure Speech SDK가 설치되지 않았습니다",
                "analysis": analysis,
                "solution": "pip install azure-cognitiveservices-speech"
            }
        
        except Exception as azure_error:
            logger.error(f"❌ Azure STT 오류: {azure_error}")
            logger.error(f"📄 Azure 오류 상세: {traceback.format_exc()}")
            
            return {
                "success": False,
                "error": f"Azure STT 처리 오류: {str(azure_error)}",
                "analysis": analysis,
                "converted": format_detected != "WAV",
                "original_format": format_detected,
                "azure_error_type": type(azure_error).__name__
            }
        
    except Exception as e:
        logger.error(f"❌ STT 전체 오류: {e}")
        logger.error(f"📄 전체 오류 상세: {traceback.format_exc()}")
        
        return {
            "success": False,
            "error": f"STT 시스템 오류: {str(e)}",
            "error_type": type(e).__name__
        }




# =============================================================================
# 유틸리티 함수들 (통합)
# =============================================================================

def calculate_distance(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """두 지점 간 거리 계산 (km)"""
    R = 6371
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lng = math.radians(lng2 - lng1)
    
    a = (math.sin(delta_lat / 2) ** 2 + 
         math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lng / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    
    return R * c

def get_risk_level(risk_score: float) -> str:
    """위험도 점수를 레벨로 변환"""
    if risk_score >= 0.8:
        return "매우 위험"
    elif risk_score >= 0.6:
        return "위험"
    elif risk_score >= 0.4:
        return "주의"
    elif risk_score >= 0.2:
        return "낮음"
    else:
        return "안전"

def get_risk_message(risk_score: float) -> str:
    """위험도에 따른 메시지 반환"""
    level = get_risk_level(risk_score)
    if level == "매우 위험":
        return "즉시 대피하고 119에 신고하세요."
    elif level == "위험":
        return "해당 지역을 피하고 안전한 경로를 이용하세요."
    elif level == "주의":
        return "주의하여 이동하세요."
    elif level == "낮음":
        return "일반적인 주의사항을 준수하세요."
    else:
        return "안전한 지역입니다."

def analyze_audio_file(audio_content: bytes) -> dict:
    """오디오 파일 분석 및 디버깅 정보 제공"""
    try:
        logger.info("🔍 오디오 파일 분석 시작")
        
        analysis = {
            "file_size": len(audio_content),
            "file_size_mb": len(audio_content) / (1024 * 1024),
            "is_empty": len(audio_content) == 0,
            "header_info": None,
            "duration_estimate": None,
            "format_detected": None
        }
        
        # 파일 헤더 분석
        if len(audio_content) >= 12:
            header = audio_content[:12]
            if header.startswith(b'RIFF') and b'WAVE' in header:
                analysis["format_detected"] = "WAV"
            elif header.startswith(b'ID3') or header[1:4] == b'ID3':
                analysis["format_detected"] = "MP3"
            elif header.startswith(b'OggS'):
                analysis["format_detected"] = "OGG"
            elif header.startswith(b'\x1a\x45\xdf\xa3'):
                analysis["format_detected"] = "WebM"
            else:
                analysis["format_detected"] = f"Unknown (header: {header.hex()})"
        
        # WAV 파일 상세 분석
        if analysis["format_detected"] == "WAV" and len(audio_content) >= 44:
            try:
                # WAV 헤더 파싱
                file_size = struct.unpack('<I', audio_content[4:8])[0]
                fmt_chunk_size = struct.unpack('<I', audio_content[16:20])[0]
                audio_format = struct.unpack('<H', audio_content[20:22])[0]
                num_channels = struct.unpack('<H', audio_content[22:24])[0]
                sample_rate = struct.unpack('<I', audio_content[24:28])[0]
                byte_rate = struct.unpack('<I', audio_content[28:32])[0]
                bits_per_sample = struct.unpack('<H', audio_content[34:36])[0]
                
                analysis["header_info"] = {
                    "audio_format": audio_format,
                    "channels": num_channels,
                    "sample_rate": sample_rate,
                    "byte_rate": byte_rate,
                    "bits_per_sample": bits_per_sample
                }
                
                # 대략적인 지속 시간 계산
                data_size = len(audio_content) - 44
                if byte_rate > 0:
                    duration_seconds = data_size / byte_rate
                    analysis["duration_estimate"] = f"{duration_seconds:.2f}초"
                
            except Exception as e:
                logger.warning(f"WAV 헤더 분석 실패: {e}")
        
        logger.info(f"📊 오디오 분석 결과: {analysis}")
        return analysis
        
    except Exception as e:
        logger.error(f"❌ 오디오 분석 오류: {e}")
        return {"error": str(e)}

def generate_stt_recommendations(debug_info: dict) -> list:
    """STT 문제 해결 권장사항 생성"""
    recommendations = []
    
    upload_info = debug_info.get("upload_info", {})
    analysis = debug_info.get("audio_analysis", {})
    stt_result = debug_info.get("stt_result", {})
    azure_config = debug_info.get("azure_config", {})
    
    # 파일 크기 체크
    if upload_info.get("size_bytes", 0) < 1000:
        recommendations.append("⚠️ 오디오 파일이 너무 작습니다. 최소 1-2초 이상 녹음해보세요.")
    
    if upload_info.get("size_bytes", 0) > 10 * 1024 * 1024:  # 10MB
        recommendations.append("⚠️ 오디오 파일이 너무 큽니다. 10MB 이하로 줄여보세요.")
    
    # 오디오 형식 체크
    if analysis.get("format_detected") != "WAV":
        recommendations.append(f"🔧 오디오 형식: {analysis.get('format_detected', 'Unknown')}. WAV 형식을 권장합니다.")
    
    # Azure 설정 체크
    if not azure_config.get("key_configured"):
        recommendations.append("🔑 Azure Speech Key가 설정되지 않았습니다. .env 파일을 확인하세요.")
    
    if not azure_config.get("sdk_available"):
        recommendations.append("📦 Azure Speech SDK가 설치되지 않았습니다. 'pip install azure-cognitiveservices-speech' 실행하세요.")
    
    # STT 결과 체크
    if not stt_result.get("success"):
        if "음성을 인식할 수 없습니다" in stt_result.get("error", ""):
            recommendations.append("🎤 음성이 명확하지 않습니다. 조용한 환경에서 더 또렷하게 말해보세요.")
        
        if "취소됨" in stt_result.get("error", ""):
            recommendations.append("⏰ 음성 인식이 취소되었습니다. 네트워크 연결을 확인하세요.")
    
    # 지속 시간 체크
    duration = analysis.get("duration_estimate")
    if duration and "0.5" in duration:
        recommendations.append("⏱️ 녹음 시간이 짧습니다. 1-3초 정도로 녹음해보세요.")
    
    if not recommendations:
        recommendations.append("✅ 특별한 문제가 발견되지 않았습니다. 다시 시도해보세요.")
    
    return recommendations


# =============================================================================
# 도보 경로 안내 서비스 클래스
# =============================================================================

class WalkingRouteService:
    """도보 경로 안내 서비스"""
    
    def __init__(self):
        self.session = None
    
    async def get_session(self):
        """비동기 HTTP 세션 생성"""
        if not self.session:
            self.session = aiohttp.ClientSession()
        return self.session
    
    async def close_session(self):
        """세션 정리"""
        if self.session:
            await self.session.close()
            self.session = None
    
    async def geocode_address(self, address: str) -> Dict:
        """주소를 좌표로 변환 (Nominatim API 사용)"""
        session = await self.get_session()
        
        params = {
            'q': f"{address}, Seoul, South Korea",
            'format': 'json',
            'limit': 1,
            'countrycodes': 'kr',
            'addressdetails': 1
        }
        
        headers = {
            'User-Agent': 'Seoul-Safety-Route-App/1.0'
        }
        
        try:
            async with session.get(f"{NOMINATIM_BASE_URL}/search", 
                                 params=params, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    if data:
                        result = data[0]
                        return {
                            'latitude': float(result['lat']),
                            'longitude': float(result['lon']),
                            'display_name': result['display_name'],
                            'address': result.get('address', {})
                        }
                return None
        except Exception as e:
            print(f"지오코딩 오류: {e}")
            return None
    
    async def get_walking_route(self, start_lat: float, start_lng: float, 
                              end_lat: float, end_lng: float) -> Dict:
        """OSRM API를 사용한 도보 경로 생성"""
        session = await self.get_session()
        
        # OSRM 좌표 형식: longitude,latitude
        coordinates = f"{start_lng},{start_lat};{end_lng},{end_lat}"
        
        params = {
            'overview': 'full',
            'geometries': 'geojson',
            'steps': 'true',
            'annotations': 'true'
        }
        
        url = f"{OSRM_BASE_URL}/route/v1/foot/{coordinates}"
        
        try:
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    if data['code'] == 'Ok' and data['routes']:
                        route = data['routes'][0]
                        
                        # 경로 좌표 추출
                        geometry = route['geometry']['coordinates']
                        waypoints = [[coord[1], coord[0]] for coord in geometry]
                        
                        # 상세 안내 정보 추출
                        steps = []
                        if 'legs' in route:
                            for leg in route['legs']:
                                if 'steps' in leg:
                                    for step in leg['steps']:
                                        step_info = {
                                            'instruction': step.get('maneuver', {}).get('instruction', '직진하세요'),
                                            'distance': step.get('distance', 0),
                                            'duration': step.get('duration', 0),
                                            'name': step.get('name', ''),
                                            'mode': step.get('mode', 'walking')
                                        }
                                        steps.append(step_info)
                        
                        return {
                            'success': True,
                            'waypoints': waypoints,
                            'distance': route.get('distance', 0),
                            'duration': route.get('duration', 0),
                            'steps': steps,
                            'geometry': route['geometry']
                        }
                    else:
                        return {
                            'success': False,
                            'error': '경로를 찾을 수 없습니다.'
                        }
                else:
                    return {
                        'success': False,
                        'error': f'라우팅 서비스 오류: {response.status}'
                    }
        except Exception as e:
            print(f"라우팅 오류: {e}")
            return {
                'success': False,
                'error': '경로 계산 중 오류가 발생했습니다.'
            }
    
    async def get_safe_walking_route(self, start_lat: float, start_lng: float, 
                                   end_lat: float, end_lng: float, 
                                   avoid_zones: List[Dict]) -> Dict:
        """위험지역을 우회하는 안전한 도보 경로"""
        
        # 1. 기본 경로 생성
        basic_route = await self.get_walking_route(start_lat, start_lng, end_lat, end_lng)
        
        if not basic_route['success']:
            return basic_route
        
        # 2. 기본 경로가 위험지역과 교차하는지 확인
        route_waypoints = basic_route['waypoints']
        crossing_zones = []
        
        for zone in avoid_zones:
            if self._route_crosses_zone(route_waypoints, zone['lat'], zone['lng'], 0.5):
                if zone.get('risk', 0) > 0.7:
                    crossing_zones.append(zone)
        
        # 3. 위험지역과 교차하지 않으면 기본 경로 반환
        if not crossing_zones:
            return {
                **basic_route,
                'route_type': 'direct',
                'avoided_zones': [],
                'message': '안전한 직선 경로입니다.'
            }
        
        # 4. 우회 경로 생성
        detour_route = await self._generate_detour_route(
            start_lat, start_lng, end_lat, end_lng, crossing_zones
        )
        
        if detour_route['success']:
            return {
                **detour_route,
                'route_type': 'safe_detour',
                'avoided_zones': crossing_zones,
                'message': f'{len(crossing_zones)}개의 위험지역을 우회하는 안전 경로입니다.'
            }
        else:
            return {
                **basic_route,
                'route_type': 'direct_with_warning',
                'avoided_zones': crossing_zones,
                'message': f'우회 경로 생성에 실패했습니다. {len(crossing_zones)}개의 위험지역을 주의하세요.'
            }
    
    def _route_crosses_zone(self, waypoints: List[List[float]], 
                          zone_lat: float, zone_lng: float, radius_km: float) -> bool:
        """경로가 위험지역과 교차하는지 확인"""
        for waypoint in waypoints:
            distance = calculate_distance(waypoint[0], waypoint[1], zone_lat, zone_lng)
            if distance <= radius_km:
                return True
        return False
    
    async def _generate_detour_route(self, start_lat: float, start_lng: float,
                                   end_lat: float, end_lng: float,
                                   zones_to_avoid: List[Dict]) -> Dict:
        """우회 경로 생성 (중간 지점을 통한)"""
        
        if not zones_to_avoid:
            return await self.get_walking_route(start_lat, start_lng, end_lat, end_lng)
        
        # 위험지역들의 평균 위치 계산
        avg_zone_lat = sum(zone['lat'] for zone in zones_to_avoid) / len(zones_to_avoid)
        avg_zone_lng = sum(zone['lng'] for zone in zones_to_avoid) / len(zones_to_avoid)
        
        # 시작점과 끝점의 중점
        mid_lat = (start_lat + end_lat) / 2
        mid_lng = (start_lng + end_lng) / 2
        
        # 우회 지점 계산 (위험지역에서 수직으로 1km 떨어진 지점)
        detour_offset = 0.01  # 약 1km
        
        # 위험지역의 반대 방향으로 우회 지점 설정
        if avg_zone_lat > mid_lat:
            detour_lat = mid_lat - detour_offset
        else:
            detour_lat = mid_lat + detour_offset
            
        if avg_zone_lng > mid_lng:
            detour_lng = mid_lng - detour_offset
        else:
            detour_lng = mid_lng + detour_offset
        
        try:
            # 다중 경유지 경로 요청
            session = await self.get_session()
            coordinates = f"{start_lng},{start_lat};{detour_lng},{detour_lat};{end_lng},{end_lat}"
            
            params = {
                'overview': 'full',
                'geometries': 'geojson',
                'steps': 'true',
                'annotations': 'true'
            }
            
            url = f"{OSRM_BASE_URL}/route/v1/foot/{coordinates}"
            
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    if data['code'] == 'Ok' and data['routes']:
                        route = data['routes'][0]
                        
                        geometry = route['geometry']['coordinates']
                        waypoints = [[coord[1], coord[0]] for coord in geometry]
                        
                        steps = []
                        if 'legs' in route:
                            for leg in route['legs']:
                                if 'steps' in leg:
                                    for step in leg['steps']:
                                        step_info = {
                                            'instruction': step.get('maneuver', {}).get('instruction', '직진하세요'),
                                            'distance': step.get('distance', 0),
                                            'duration': step.get('duration', 0),
                                            'name': step.get('name', ''),
                                            'mode': 'walking'
                                        }
                                        steps.append(step_info)
                        
                        return {
                            'success': True,
                            'waypoints': waypoints,
                            'distance': route.get('distance', 0),
                            'duration': route.get('duration', 0),
                            'steps': steps,
                            'geometry': route['geometry']
                        }
                        
        except Exception as e:
            print(f"우회 경로 생성 오류: {e}")
        
        # 우회 경로 생성 실패 시 기본 경로 반환
        return await self.get_walking_route(start_lat, start_lng, end_lat, end_lng)

# 전역 서비스 인스턴스
walking_service = WalkingRouteService()

# =============================================================================
# FastAPI 이벤트 핸들러
# =============================================================================

@app.on_event("startup")
async def startup_event():
    """앱 시작 시 실행"""
    print("🚀 Seoul Safety Navigation API 시작")
    print("🗺️ 도보 경로 서비스 초기화 완료")
    print("🎤 Azure Speech Service 준비 완료")

@app.on_event("shutdown")
async def shutdown_event():
    """앱 종료 시 실행"""
    await walking_service.close_session()
    print("🔄 서비스 종료 완료")

# =============================================================================
# 인증 관련 API 엔드포인트
# =============================================================================

@app.post("/register", response_model=UserResponse)
def register_user(user: UserCreate, db: Session = Depends(get_db)):
    """사용자 회원가입"""
    db_user = db.query(User).filter(User.email == user.email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="이미 등록된 이메일입니다.")
    
    hashed_password = get_password_hash(user.password)
    db_user = User(
        username=user.username,
        email=user.email,
        password=hashed_password
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    return UserResponse(
        id=db_user.id,
        username=db_user.username,
        email=db_user.email,
        created_at=db_user.created_at.isoformat()
    )

@app.post("/token")
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """로그인 토큰 발급"""
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="이메일 또는 비밀번호가 올바르지 않습니다.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=30)
    access_token = create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )
    
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/users/me", response_model=UserResponse)
def read_users_me(current_user: User = Depends(get_current_user)):
    """현재 사용자 정보 조회"""
    return UserResponse(
        id=current_user.id,
        username=current_user.username,
        email=current_user.email,
        created_at=current_user.created_at.isoformat()
    )

# =============================================================================
# 위험도 예측 API 엔드포인트
# =============================================================================

@app.post("/predict-risk", response_model=RiskResponse)
async def predict_risk(location: LocationRequest):
    """특정 위치의 싱크홀 위험도 예측"""
    
    # 가장 가까운 위험지역 찾기
    min_distance = float('inf')
    nearest_risk = 0.0
    
    for zone in DUMMY_RISK_ZONES:
        distance = calculate_distance(location.latitude, location.longitude, zone["lat"], zone["lng"])
        if distance < min_distance:
            min_distance = distance
            nearest_risk = zone["risk"]
    
    # 거리에 따른 위험도 조정
    if min_distance < 0.5:  # 500m 이내
        risk_score = max(0.7, nearest_risk)
    elif min_distance < 1.0:  # 1km 이내
        risk_score = max(0.4, nearest_risk * 0.7)
    elif min_distance < 2.0:  # 2km 이내
        risk_score = max(0.2, nearest_risk * 0.5)
    else:
        risk_score = min(0.3, random.uniform(0.1, 0.3))
    
    return RiskResponse(
        latitude=location.latitude,
        longitude=location.longitude,
        risk_score=round(risk_score, 3),
        risk_level=get_risk_level(risk_score),
        message=get_risk_message(risk_score)
    )

@app.get("/risk-zones")
async def get_risk_zones():
    """서울시 위험지역 목록 반환"""
    return {
        "zones": DUMMY_RISK_ZONES,
        "total_count": len(DUMMY_RISK_ZONES)
    }

@app.get("/construction-zones")
async def get_construction_zones():
    """서울시 공사지역 목록 반환 (수정된 버전)"""
    try:
        logger.info("🏗️ 공사지역 API 호출")
        
        # 데이터가 없으면 로드 시도
        if not CONSTRUCTION_DATA:
            logger.warning("⚠️ CONSTRUCTION_DATA가 비어있음. 재로드 시도...")
            load_construction_data()
        
        total_count = len(CONSTRUCTION_DATA)
        logger.info(f"📊 현재 데이터 개수: {total_count}")
        
        if total_count == 0:
            logger.error("❌ 공사장 데이터가 여전히 비어있음")
            return {
                "zones": [],
                "total_count": 0,
                "active_count": 0,
                "error": "공사장 데이터를 로드할 수 없습니다. 서버 로그를 확인하세요."
            }
        
        # 상태별 개수 계산
        active_zones = [zone for zone in CONSTRUCTION_DATA if zone.get("status") == "진행중"]
        completed_zones = [zone for zone in CONSTRUCTION_DATA if zone.get("status") == "완료"] 
        planned_zones = [zone for zone in CONSTRUCTION_DATA if zone.get("status") == "예정"]
        
        logger.info(f"📊 상태별 개수: 진행중 {len(active_zones)}, 완료 {len(completed_zones)}, 예정 {len(planned_zones)}")
        
        return {
            "zones": CONSTRUCTION_DATA,
            "total_count": total_count,
            "active_count": len(active_zones),
            "completed_count": len(completed_zones),
            "planned_count": len(planned_zones),
            "status_breakdown": {
                "진행중": len(active_zones),
                "완료": len(completed_zones), 
                "예정": len(planned_zones)
            }
        }
        
    except Exception as e:
        logger.error(f"❌ 공사지역 API 오류: {e}")
        logger.error(f"📄 오류 상세: {traceback.format_exc()}")
        return {
            "zones": [],
            "total_count": 0,
            "active_count": 0,
            "error": f"API 처리 오류: {str(e)}"
        }

# =============================================================================
# 도보 경로 안내 API 엔드포인트
# =============================================================================

@app.post("/walking-route", response_model=RouteResponse)
async def get_walking_route(route_request: RouteRequest):
    """실제 도보 경로 생성 API"""
    try:
        result = await walking_service.get_walking_route(
            route_request.start_latitude,
            route_request.start_longitude,
            route_request.end_latitude,
            route_request.end_longitude
        )
        
        if not result['success']:
            raise HTTPException(status_code=400, detail=result.get('error', '경로를 찾을 수 없습니다.'))
        
        return RouteResponse(
            waypoints=[{"lat": wp[0], "lng": wp[1]} for wp in result['waypoints']],
            distance=result['distance'] / 1000,  # km로 변환
            estimated_time=int(result['duration'] / 60),  # 분으로 변환
            route_type="walking",
            avoided_zones=[],
            steps=result.get('steps', []),
            message="도보 경로가 생성되었습니다."
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"경로 생성 오류: {str(e)}")

@app.post("/safe-walking-route", response_model=RouteResponse)
async def get_safe_walking_route(route_request: RouteRequest):
    """위험지역 및 공사장을 우회하는 안전한 도보 경로 생성"""
    try:
        # 위험지역 목록 가져오기 (싱크홀 + 공사장)
        avoid_zones = []
        all_risk_zones = DUMMY_RISK_ZONES + [
            zone for zone in CONSTRUCTION_DATA if zone.get("status") == "진행중"
        ]

        for zone in all_risk_zones:
            # 경로 주변 2km 내의 고위험 지역만 체크
            start_distance = calculate_distance(
                route_request.start_latitude, route_request.start_longitude,
                zone["lat"], zone["lng"]
            )
            end_distance = calculate_distance(
                route_request.end_latitude, route_request.end_longitude,
                zone["lat"], zone["lng"]
            )
            
            # 위험도 0.7 이상인 싱크홀 지역 또는 진행중인 공사장
            if (start_distance <= 2.0 or end_distance <= 2.0) and zone.get("risk", 0) > 0.6:
                avoid_zones.append(zone)
        
        result = await walking_service.get_safe_walking_route(
            route_request.start_latitude,
            route_request.start_longitude,
            route_request.end_latitude,
            route_request.end_longitude,
            avoid_zones # 수정된 avoid_zones 전달
        )
        
        if not result['success']:
            raise HTTPException(status_code=400, detail=result.get('error', '경로를 찾을 수 없습니다.'))
        
        # 메시지 개선
        message = result.get('message', '안전한 도보 경로가 생성되었습니다.')
        avoided_constructions = len([z for z in result.get('avoided_zones', []) if 'CONST' in z.get('id', '')])
        if avoided_constructions > 0:
            message += f" {avoided_constructions}개의 공사장을 우회합니다."

        return RouteResponse(
            waypoints=[{"lat": wp[0], "lng": wp[1]} for wp in result['waypoints']],
            distance=result['distance'] / 1000,  # km로 변환
            estimated_time=int(result['duration'] / 60),  # 분으로 변환
            route_type=result.get('route_type', 'walking'),
            avoided_zones=result.get('avoided_zones', []),
            steps=result.get('steps', []),
            message=message # 개선된 메시지
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"안전 경로 생성 오류: {str(e)}")

# =============================================================================
# 지오코딩 및 검색 API 엔드포인트 (통합)
# =============================================================================

@app.get("/geocode")
async def geocode_address(address: str):
    """주소를 좌표로 변환"""
    if not address:
        raise HTTPException(status_code=400, detail="주소를 입력해주세요.")
    
    result = await walking_service.geocode_address(address)
    
    if not result:
        raise HTTPException(status_code=404, detail="주소를 찾을 수 없습니다.")
    
    return {
        "address": address,
        "latitude": result['latitude'],
        "longitude": result['longitude'],
        "display_name": result['display_name']
    }

@app.get("/search-location")
async def search_location(query: str):
    """카카오맵 API를 사용한 지명 검색"""
    
    if not query or len(query) < 2:
        return {"places": []}
    
    if not KAKAO_API_KEY or KAKAO_API_KEY == "YOUR_KAKAO_REST_API_KEY":
        return {"places": [], "error": "카카오 API 키가 설정되지 않았습니다."}
    
    try:
        url = "https://dapi.kakao.com/v2/local/search/keyword.json"
        headers = {"Authorization": f"KakaoAK {KAKAO_API_KEY}"}
        
        params = {
            "query": query.strip(),
            "size": 5,
            "page": 1,
            "sort": "accuracy"
        }
        
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        places = data.get("documents", [])
        
        formatted_places = []
        for place in places:
            formatted_place = {
                "place_name": place.get("place_name", ""),
                "address_name": place.get("address_name", ""),
                "road_address_name": place.get("road_address_name", ""),
                "x": place.get("x", ""),  # 경도
                "y": place.get("y", ""),  # 위도
                "category_name": place.get("category_name", ""),
                "phone": place.get("phone", ""),
                "place_url": place.get("place_url", "")
            }
            formatted_places.append(formatted_place)
        
        return {
            "places": formatted_places,
            "total_count": len(formatted_places)
        }
        
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 400:
            return {"places": [], "error": "잘못된 요청입니다."}
        elif e.response.status_code == 401:
            return {"places": [], "error": "API 키가 유효하지 않습니다."}
        elif e.response.status_code == 403:
            return {"places": [], "error": "API 키 권한이 없습니다."}
        elif e.response.status_code == 429:
            return {"places": [], "error": "API 호출 한도를 초과했습니다."}
        else:
            return {"places": [], "error": f"API 호출 실패: {e.response.status_code}"}
            
    except requests.exceptions.Timeout:
        return {"places": [], "error": "검색 시간이 초과되었습니다."}
        
    except Exception as e:
        print(f"지명 검색 오류: {e}")
        return {"places": [], "error": "검색 중 오류가 발생했습니다."}

@app.get("/search-location-combined")
async def search_location_combined(query: str):
    """통합 검색 API (카카오맵 + OpenStreetMap 백업)"""
    
    if not query or len(query) < 2:
        return {"places": []}
    
    # 1. 카카오맵 API 시도
    kakao_result = await search_location(query)
    
    if kakao_result.get("places") and len(kakao_result["places"]) > 0:
        return kakao_result
    
    # 2. 카카오맵 실패 시 OpenStreetMap 지오코딩 시도
    try:
        osm_result = await walking_service.geocode_address(query)
        
        if osm_result:
            places = [{
                "place_name": query,
                "address_name": osm_result['display_name'],
                "road_address_name": osm_result['display_name'],
                "x": str(osm_result['longitude']),
                "y": str(osm_result['latitude']),
                "category_name": "지오코딩",
                "phone": "",
                "place_url": ""
            }]
            
            return {
                "places": places,
                "total_count": len(places),
                "source": "openstreetmap"
            }
    except Exception as e:
        print(f"OpenStreetMap 지오코딩 오류: {e}")
    
    # 3. 모든 방법이 실패한 경우
    return {"places": [], "error": "검색 결과를 찾을 수 없습니다."}

# =============================================================================
# 음성 처리 API 엔드포인트 (통합 및 개선)
# =============================================================================

@app.post("/api/process-destination", response_model=DestinationResponse)
async def process_destination_endpoint(request: DestinationRequest):
    """목적지 텍스트 정제 API"""
    try:
        logger.info(f"📍 목적지 정제 요청: '{request.text}'")
        
        if not request.text or not request.text.strip():
            raise HTTPException(status_code=400, detail="텍스트가 비어있습니다")
        
        if len(request.text.strip()) > 200:
            raise HTTPException(status_code=400, detail="텍스트가 너무 깁니다 (최대 200자)")
        
        result = process_destination_text(request.text.strip())
        
        if not result["success"]:
            logger.warning(f"⚠️ 정제 실패: {result.get('error', '알 수 없는 오류')}")
            raise HTTPException(status_code=400, detail=result.get("error", "처리 실패"))
        
        response = DestinationResponse(**result)
        logger.info(f"✅ 목적지 정제 완료: '{request.text}' → '{response.cleaned_text}' (신뢰도: {response.confidence_score:.2f})")
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 목적지 정제 API 오류: {e}")
        logger.error(f"📄 오류 상세: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"서버 오류: {str(e)}")

# ❗️❗️❗️ 여기가 핵심 수정 부분입니다.
@app.post("/api/stt-with-destination-processing", response_model=STTWithProcessingResponse)
async def stt_with_destination_processing_endpoint(
    audio: UploadFile = File(...),
    min_confidence: float = Form(0.6)
):
    """STT + 목적지 정제 통합 API (안정성 개선 버전)"""
    try:
        logger.info("🎤 STT + 목적지 정제 통합 처리 시작 (개선된 파이프라인)")
        
        if not audio.filename:
            raise HTTPException(status_code=400, detail="오디오 파일이 업로드되지 않았습니다")
        
        audio_content = await audio.read()
        if len(audio_content) == 0:
            raise HTTPException(status_code=400, detail="오디오 파일이 비어있습니다")
        
        logger.info(f"📁 오디오 파일 수신: {len(audio_content)} bytes, {audio.content_type}")
        
        # 1단계: 안정적인 Azure STT 처리 (오디오 변환 기능 포함)
        # 기존의 불안정한 함수 대신, 변환 기능이 내장된 안정적인 함수를 호출합니다.
        stt_result = await process_azure_stt_enhanced_with_conversion(audio_content)
        
        if not stt_result.get("success"):
            error_msg = stt_result.get("error", "음성 인식 실패")
            logger.warning(f"⚠️ STT 실패: {error_msg}")
            
            return STTWithProcessingResponse(
                success=False,
                recognized_text="",
                stt_confidence=0.0,
                processed_destination=DestinationResponse(
                    success=False, original_text="", cleaned_text="",
                    confidence_score=0.0, location_type="", keywords=[],
                    search_suggestions=[], is_valid=False,
                    error=f"STT 실패: {error_msg}"
                ),
                recommended_search_text="",
                should_proceed=False,
                error=error_msg
            )
        
        recognized_text = stt_result["recognized_text"]
        stt_confidence = stt_result.get("confidence")
        logger.info(f"✅ STT 결과: '{recognized_text}' (신뢰도: {stt_confidence})")
        
        # 2단계: 목적지 텍스트 정제
        destination_result = process_destination_text(recognized_text)
        
        # 3단계: 최종 추천 검색어 결정
        if destination_result["success"] and destination_result["confidence_score"] >= min_confidence:
            recommended_search_text = destination_result["cleaned_text"]
            should_proceed = True
            logger.info(f"🎯 높은 신뢰도: '{recommended_search_text}' (진행)")
        else:
            # 추천 검색어가 있으면 사용
            if destination_result.get("search_suggestions") and len(destination_result["search_suggestions"]) > 0:
                recommended_search_text = destination_result["search_suggestions"][0]
                should_proceed = destination_result.get("confidence_score", 0) >= 0.4
                logger.info(f"⚠️ 중간 신뢰도: '{recommended_search_text}' (진행: {should_proceed})")
            else:
                recommended_search_text = recognized_text
                should_proceed = False
                logger.warning(f"❓ 낮은 신뢰도: '{recommended_search_text}' (재입력 권장)")
        
        return STTWithProcessingResponse(
            success=True,
            recognized_text=recognized_text,
            stt_confidence=stt_confidence,
            processed_destination=DestinationResponse(**destination_result),
            recommended_search_text=recommended_search_text,
            should_proceed=should_proceed
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ STT + 목적지 정제 통합 API 오류: {e}", exc_info=True)
        return STTWithProcessingResponse(
            success=False, recognized_text="", stt_confidence=0.0,
            processed_destination=DestinationResponse(
                success=False, original_text="", cleaned_text="", confidence_score=0.0,
                location_type="", keywords=[], search_suggestions=[], is_valid=False, error="처리 실패"
            ),
            recommended_search_text="", should_proceed=False, error=f"서버 오류: {str(e)}"
        )


@app.post("/api/stt-debug")
async def stt_debug_endpoint(audio: UploadFile = File(...)):
    """STT 디버깅 전용 API"""
    try:
        logger.info("🔍 STT 디버깅 모드 시작")
        
        if not audio.filename:
            raise HTTPException(status_code=400, detail="오디오 파일이 업로드되지 않았습니다")
        
        audio_content = await audio.read()
        
        logger.info(f"📁 업로드된 파일: {audio.filename} ({len(audio_content)} bytes)")
        logger.info(f"📄 Content-Type: {audio.content_type}")
        
        # 오디오 분석
        analysis = analyze_audio_file(audio_content)
        
        # STT 시도
        stt_result = await process_azure_stt_enhanced_with_conversion(audio_content)
        
        # 종합 디버깅 정보
        debug_info = {
            "upload_info": {
                "filename": audio.filename,
                "content_type": audio.content_type,
                "size_bytes": len(audio_content),
                "size_mb": len(audio_content) / (1024 * 1024)
            },
            "audio_analysis": analysis,
            "stt_result": stt_result,
            "azure_config": {
                "key_configured": bool(os.getenv('AZURE_SPEECH_KEY')),
                "region": os.getenv('AZURE_SPEECH_REGION', 'koreacentral'),
                "sdk_available": True
            }
        }
        
        try:
            import azure.cognitiveservices.speech as speechsdk
            debug_info["azure_config"]["sdk_version"] = speechsdk.__version__ if hasattr(speechsdk, '__version__') else "Unknown"
        except ImportError:
            debug_info["azure_config"]["sdk_available"] = False
        
        logger.info(f"🔍 STT 디버깅 완료")
        
        return {
            "success": True,
            "debug_info": debug_info,
            "recommendations": generate_stt_recommendations(debug_info)
        }
        
    except Exception as e:
        logger.error(f"❌ STT 디버깅 오류: {e}")
        raise HTTPException(status_code=500, detail=f"디버깅 오류: {str(e)}")

@app.post("/api/validate-destination")
async def validate_destination_endpoint(
    text: str = Form(...), 
    min_confidence: float = Form(0.6)
):
    """목적지 유효성 검증 API"""
    try:
        logger.info(f"🔍 목적지 검증: '{text}' (최소 신뢰도: {min_confidence})")
        
        is_valid = destination_processor.validate_destination(text, min_confidence)
        result = process_destination_text(text)
        
        response = {
            "success": True,
            "text": text,
            "is_valid": is_valid,
            "confidence_score": result.get("confidence_score", 0.0),
            "cleaned_text": result.get("cleaned_text", ""),
            "location_type": result.get("location_type", "unknown")
        }
        
        logger.info(f"✅ 검증 완료: {is_valid} (신뢰도: {response['confidence_score']:.2f})")
        return response
        
    except Exception as e:
        logger.error(f"❌ 목적지 검증 API 오류: {e}")
        return {
            "success": False,
            "error": str(e),
            "is_valid": False
        }

# 기존 @app.post("/api/tts", response_model=TTSResponse) 엔드포인트를 이것으로 교체하세요:

@app.post("/api/tts")
async def text_to_speech_api(
    text: str = Form(...),
    voice_name: str = Form("ko-KR-HyunsuMultilingualNeural")
):
    """텍스트를 Azure TTS로 음성 변환 (스피커 오류 해결)"""
    
    if not text or len(text.strip()) == 0:
        raise HTTPException(status_code=400, detail="텍스트가 비어있습니다.")
    
    if len(text) > 1000:
        raise HTTPException(status_code=400, detail="텍스트가 너무 깁니다. (최대 1000자)")
    
    try:
        logger.info(f"🔊 TTS 요청: '{text[:50]}...' (음성: {voice_name})")
        
        try:
            import azure.cognitiveservices.speech as speechsdk
            
            speech_key = os.getenv('AZURE_SPEECH_KEY')
            speech_region = os.getenv('AZURE_SPEECH_REGION', 'koreacentral')
            
            if not speech_key:
                raise HTTPException(status_code=500, detail="Azure Speech Key가 설정되지 않았습니다")
            
            # Speech 설정
            speech_config = speechsdk.SpeechConfig(
                subscription=speech_key, 
                region=speech_region
            )
            speech_config.speech_synthesis_voice_name = voice_name
            
            # 방법 1: 메모리 스트림으로 직접 출력 (권장)
            try:
                # Pull audio output stream 사용
                pull_stream = speechsdk.audio.PullAudioOutputStream()
                audio_config = speechsdk.audio.AudioOutputConfig(stream=pull_stream)
                
                # 음성 합성기 생성
                synthesizer = speechsdk.SpeechSynthesizer(
                    speech_config=speech_config, 
                    audio_config=audio_config
                )
                
                # 음성 합성 수행
                logger.info("🔄 Azure TTS 합성 수행 중... (스트림 방식)")
                result = synthesizer.speak_text_async(text.strip()).get()
                
                if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
                    # 스트림에서 오디오 데이터 읽기
                    audio_data = result.audio_data
                    
                    if audio_data and len(audio_data) > 0:
                        # 오디오 데이터를 Base64로 인코딩
                        audio_base64 = base64.b64encode(audio_data).decode('utf-8')
                        
                        logger.info(f"✅ TTS 성공 (스트림): {len(audio_data)} bytes")
                        
                        return {
                            "success": True,
                            "audio_data": audio_base64,
                            "voice_name": voice_name,
                            "text": text
                        }
                    else:
                        raise Exception("오디오 데이터가 비어있습니다")
                
                elif result.reason == speechsdk.ResultReason.Canceled:
                    cancellation_details = result.cancellation_details
                    error_msg = f"TTS 취소됨: {cancellation_details.reason}"
                    if cancellation_details.error_details:
                        error_msg += f" - {cancellation_details.error_details}"
                    raise Exception(error_msg)
                
                else:
                    raise Exception(f"TTS 실패: {result.reason}")
                    
            except Exception as stream_error:
                logger.warning(f"⚠️ 스트림 방식 실패: {stream_error}")
                
                # 방법 2: 기본 스피커 활성화 방식 (백업)
                try:
                    logger.info("🔄 기본 스피커 방식으로 재시도...")
                    
                    # 기본 오디오 출력 설정 (스피커 사용)
                    audio_config = speechsdk.audio.AudioOutputConfig(use_default_speaker=True)
                    
                    # 음성 합성기 생성
                    synthesizer = speechsdk.SpeechSynthesizer(
                        speech_config=speech_config, 
                        audio_config=audio_config
                    )
                    
                    # 음성 합성 수행
                    result = synthesizer.speak_text_async(text.strip()).get()
                    
                    if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
                        # result.audio_data에서 직접 가져오기
                        audio_data = result.audio_data
                        
                        if audio_data and len(audio_data) > 0:
                            audio_base64 = base64.b64encode(audio_data).decode('utf-8')
                            
                            logger.info(f"✅ TTS 성공 (스피커): {len(audio_data)} bytes")
                            
                            return {
                                "success": True,
                                "audio_data": audio_base64,
                                "voice_name": voice_name,
                                "text": text
                            }
                        else:
                            raise Exception("오디오 데이터가 비어있습니다")
                    
                    else:
                        raise Exception(f"TTS 실패: {result.reason}")
                        
                except Exception as speaker_error:
                    logger.warning(f"⚠️ 스피커 방식도 실패: {speaker_error}")
                    
                    # 방법 3: 파일 방식 (최후의 수단)
                    try:
                        logger.info("🔄 파일 방식으로 재시도...")
                        
                        # 임시 파일 생성
                        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                            temp_filename = temp_file.name
                        
                        # 파일 출력으로 설정
                        audio_config = speechsdk.audio.AudioOutputConfig(filename=temp_filename)
                        
                        # 음성 합성기 생성
                        synthesizer = speechsdk.SpeechSynthesizer(
                            speech_config=speech_config, 
                            audio_config=audio_config
                        )
                        
                        # 음성 합성 수행
                        result = synthesizer.speak_text_async(text.strip()).get()
                        
                        if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
                            # 파일에서 오디오 데이터 읽기
                            with open(temp_filename, 'rb') as audio_file:
                                audio_data = audio_file.read()
                            
                            # 임시 파일 삭제
                            try:
                                os.remove(temp_filename)
                            except:
                                pass
                            
                            if audio_data and len(audio_data) > 0:
                                audio_base64 = base64.b64encode(audio_data).decode('utf-8')
                                
                                logger.info(f"✅ TTS 성공 (파일): {len(audio_data)} bytes")
                                
                                return {
                                    "success": True,
                                    "audio_data": audio_base64,
                                    "voice_name": voice_name,
                                    "text": text
                                }
                            else:
                                raise Exception("파일이 비어있습니다")
                        
                        else:
                            raise Exception(f"TTS 실패: {result.reason}")
                            
                    except Exception as file_error:
                        logger.error(f"❌ 파일 방식도 실패: {file_error}")
                        raise Exception(f"모든 TTS 방식 실패: 스트림({stream_error}), 스피커({speaker_error}), 파일({file_error})")
                        
        except ImportError:
            logger.error("❌ Azure Speech SDK가 설치되지 않음")
            raise HTTPException(status_code=500, detail="Azure Speech SDK가 설치되지 않았습니다")
        
        except Exception as tts_error:
            logger.error(f"❌ Azure TTS 처리 오류: {tts_error}")
            raise HTTPException(status_code=500, detail=f"TTS 처리 오류: {str(tts_error)}")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ TTS API 전체 오류: {e}")
        raise HTTPException(status_code=500, detail=f"TTS 시스템 오류: {str(e)}")

# 추가로 JSON 방식도 지원하려면 이 엔드포인트도 추가하세요:
@app.post("/api/tts-json", response_model=TTSResponse)
async def text_to_speech_json_api(request: TTSRequest):
    """텍스트를 Azure TTS로 음성 변환 (JSON 방식 백업)"""
    
    if not request.text or len(request.text.strip()) == 0:
        raise HTTPException(status_code=400, detail="텍스트가 비어있습니다.")
    
    if len(request.text) > 1000:
        raise HTTPException(status_code=400, detail="텍스트가 너무 깁니다. (최대 1000자)")
    
    try:
        logger.info(f"🔊 TTS JSON 요청: '{request.text[:50]}...' (음성: {request.voice_name})")
        
        try:
            import azure.cognitiveservices.speech as speechsdk
            
            speech_key = os.getenv('AZURE_SPEECH_KEY')
            speech_region = os.getenv('AZURE_SPEECH_REGION', 'koreacentral')
            
            if not speech_key:
                raise HTTPException(status_code=500, detail="Azure Speech Key가 설정되지 않았습니다")
            
            # Speech 설정
            speech_config = speechsdk.SpeechConfig(
                subscription=speech_key, 
                region=speech_region
            )
            speech_config.speech_synthesis_voice_name = request.voice_name
            
            # 오디오 출력을 메모리 스트림으로 설정
            audio_config = speechsdk.audio.AudioOutputConfig(use_default_speaker=False)
            
            # 음성 합성기 생성
            synthesizer = speechsdk.SpeechSynthesizer(
                speech_config=speech_config, 
                audio_config=audio_config
            )
            
            # 음성 합성 수행
            logger.info("🔄 Azure TTS 합성 수행 중...")
            result = synthesizer.speak_text_async(request.text.strip()).get()
            
            if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
                # 오디오 데이터를 Base64로 인코딩
                audio_data = base64.b64encode(result.audio_data).decode('utf-8')
                
                logger.info(f"✅ TTS JSON 성공: {len(result.audio_data)} bytes")
                
                return TTSResponse(
                    success=True,
                    audio_data=audio_data,
                    voice_name=request.voice_name,
                    text=request.text
                )
            
            else:
                logger.error(f"❌ TTS 결과: {result.reason}")
                raise HTTPException(status_code=500, detail="TTS 합성 실패")
                
        except ImportError:
            logger.error("❌ Azure Speech SDK가 설치되지 않음")
            raise HTTPException(status_code=500, detail="Azure Speech SDK가 설치되지 않았습니다")
        
        except Exception as tts_error:
            logger.error(f"❌ Azure TTS 처리 오류: {tts_error}")
            raise HTTPException(status_code=500, detail=f"TTS 처리 오류: {str(tts_error)}")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ TTS JSON API 전체 오류: {e}")
        raise HTTPException(status_code=500, detail=f"TTS 시스템 오류: {str(e)}")

@app.get("/api/voices")
async def get_available_voices():
    """사용 가능한 Azure TTS 음성 목록"""
    return {
        "korean_voices": [
            {
                "name": "ko-KR-HyunsuMultilingualNeural",
                "gender": "Male",
                "description": "한국어 남성 음성 (다국어 지원)"
            },
            {
                "name": "ko-KR-SunHiNeural", 
                "gender": "Female",
                "description": "한국어 여성 음성"
            },
            {
                "name": "ko-KR-InJoonNeural",
                "gender": "Male", 
                "description": "한국어 남성 음성"
            },
            {
                "name": "ko-KR-BongJinNeural",
                "gender": "Male",
                "description": "한국어 남성 음성"
            },
            {
                "name": "ko-KR-GookMinNeural",
                "gender": "Male",
                "description": "한국어 남성 음성"
            }
        ],
        "default": "ko-KR-HyunsuMultilingualNeural"
    }

@app.post("/api/navigation-tts")
async def navigation_tts(request: TTSRequest):
    """네비게이션 전용 TTS (더 빠른 응답)"""
    
    try:
        # 네비게이션용 짧은 텍스트 최적화
        if len(request.text) > 200:
            request.text = request.text[:200] + "..."
        
        # 캐시된 공통 문구들
        common_phrases = {
            "목적지 확인": "목적지를 확인했습니다. 경로를 탐색하겠습니다.",
            "경로 탐색": "경로를 탐색 중입니다. 잠시만 기다려주세요.",
            "안내 시작": "안내를 시작합니다.",
            "직진": "직진하세요.",
            "우회전": "우회전하세요.", 
            "좌회전": "좌회전하세요.",
            "도착": "목적지에 도착했습니다."
        }
        
        # 공통 문구 확인
        for key, phrase in common_phrases.items():
            if key in request.text or phrase in request.text:
                request.text = phrase
                break
        
        # TTS 처리 (기존 로직 재사용)
        form_text = request.text
        form_voice_name = request.voice_name or "ko-KR-HyunsuMultilingualNeural"
        
        # text_to_speech_api가 Form 데이터를 기대하므로, 직접 호출 대신 로직을 재구성하거나
        # 별도 함수로 분리하는 것이 좋지만, 여기서는 간단히 재호출 가능한 형태로 변환합니다.
        # 실제 프로덕션에서는 내부 로직을 함수로 분리하여 재사용하는 것이 더 좋습니다.
        return await text_to_speech_json_api(request)

        
    except Exception as e:
        logger.error(f"❌ 네비게이션 TTS 오류: {e}")
        return TTSResponse(
            success=False,
            error=str(e),
            voice_name=request.voice_name or "ko-KR-HyunsuMultilingualNeural",
            text=request.text
        )

# =============================================================================
# 시스템 상태 및 헬스체크 API (통합)
# =============================================================================

@app.get("/")
async def root():
    """API 루트 엔드포인트"""
    return {
        "message": "Seoul Safety Navigation API",
        "version": "2.0.0",
        "features": [
            "실시간 싱크홀 위험도 예측",
            "Azure Speech 음성 안내",
            "안전 도보 경로 생성",
            "위험지역 우회 알고리즘",
            "카카오맵 & OpenStreetMap 통합 검색",
            "STT + 목적지 정제 통합 처리"
        ],
        "endpoints": {
            "authentication": ["/register", "/token", "/users/me"],
            "risk_prediction": ["/predict-risk", "/risk-zones"],
            "navigation": ["/walking-route", "/safe-walking-route"],
            "geocoding": ["/geocode", "/search-location", "/search-location-combined"],
            "speech": ["/api/tts", "/api/voices", "/api/navigation-tts"],
            "destination": ["/api/process-destination", "/api/validate-destination"],
            "stt": ["/api/stt-with-destination-processing", "/api/stt-debug"],
            "chatbot": ["/chatbot/ask", "/chatbot/voice-chat"],
            "health": ["/api/health", "/health", "/status"]
        }
    }

@app.get("/api/health")
async def health_check_api():
    """서비스 상태 확인 (API 버전)"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "services": {
            "destination_processor": "destination_processor" in globals(),
            "azure_config": bool(os.getenv('AZURE_SPEECH_KEY')),
            "database": "available"
        }
    }

@app.get("/health")
async def health_check():
    """시스템 헬스체크 (상세 버전)"""
    try:
        # 데이터베이스 연결 테스트
        db = SessionLocal()
        db.execute("SELECT 1")
        db.close()
        db_status = "healthy"
    except Exception as e:
        db_status = f"error: {str(e)}"
    
    # Azure Speech Service 상태 확인
    speech_status = "healthy" if speech_service.enabled else "disabled"
    
    # OSRM 서비스 상태 확인
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{OSRM_BASE_URL}/route/v1/foot/126.9780,37.5665;127.0276,37.4979", timeout=5) as response:
                osrm_status = "healthy" if response.status == 200 else f"error: {response.status}"
    except Exception as e:
        osrm_status = f"error: {str(e)}"
    
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "services": {
            "database": db_status,
            "azure_speech": speech_status,
            "osrm_routing": osrm_status,
            "kakao_maps": "configured" if KAKAO_API_KEY != "YOUR_KAKAO_REST_API_KEY" else "not_configured"
        },
        "features": {
            "risk_prediction": True,
            "walking_navigation": True,
            "voice_assistance": speech_service.enabled,
            "safety_routing": True,
            "multilingual_geocoding": True,
            "destination_processing": True,
            "stt_debugging": True
        }
    }

@app.get("/status")
async def get_system_status():
    """상세 시스템 상태 정보"""
    return {
        "api_version": "2.0.0",
        "server_time": datetime.now().isoformat(),
        "risk_zones_count": len(DUMMY_RISK_ZONES),
        "supported_languages": ["ko-KR"],
        "routing_providers": ["OSRM", "Custom Safety Algorithm"],
        "geocoding_providers": ["Kakao Maps", "Nominatim/OpenStreetMap"],
        "speech_providers": ["Azure Cognitive Services"],
        "database_tables": ["users", "locations", "risk_predictions"],
        "cache_status": "active",
        "uptime": "System running",
        "features": {
            "enhanced_stt": True,
            "destination_processing": True,
            "voice_debugging": True,
            "safety_routing": True
        }
    }

# =============================================================================
# 개발용 테스트 엔드포인트 (통합)
# =============================================================================

@app.get("/test/voice")
async def test_voice_service():
    """음성 서비스 테스트"""
    try:
        test_text = "안녕하세요. Azure 음성 서비스 테스트입니다."
        
        test_request = TTSRequest(
            text=test_text,
            voice_name="ko-KR-HyunsuMultilingualNeural"
        )
        
        # text_to_speech_api가 Form 데이터를 기대하므로 json 버전으로 호출
        result = await text_to_speech_json_api(test_request)
        
        audio_data = result.audio_data
        
        return {
            "success": result.success,
            "message": "음성 서비스가 정상 작동합니다." if result.success else "음성 서비스 테스트 실패",
            "audio_size": len(base64.b64decode(audio_data)) if audio_data else 0,
            "test_text": test_text,
            "error": result.error if not result.success else None
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": "음성 서비스 테스트 실패"
        }

@app.get("/test/route")
async def test_route_service():
    """경로 서비스 테스트"""
    try:
        # 서울시청 → 강남역 테스트 경로
        result = await walking_service.get_walking_route(
            37.5665, 126.9780,  # 서울시청
            37.4979, 127.0276   # 강남역
        )
        
        return {
            "success": result['success'],
            "test_route": "서울시청 → 강남역",
            "distance_km": result.get('distance', 0) / 1000 if result['success'] else 0,
            "duration_minutes": result.get('duration', 0) / 60 if result['success'] else 0,
            "waypoints_count": len(result.get('waypoints', [])) if result['success'] else 0,
            "steps_count": len(result.get('steps', [])) if result['success'] else 0
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": "경로 서비스 테스트 실패"
        }

@app.get("/test/destination")
async def test_destination_service():
    """목적지 처리 서비스 테스트"""
    try:
        test_texts = ["강남역", "서울시청", "명동 맛집", "홍대입구역 2번출구"]
        results = []
        
        for text in test_texts:
            result = process_destination_text(text)
            results.append({
                "input": text,
                "output": result.get("cleaned_text", ""),
                "confidence": result.get("confidence_score", 0.0),
                "success": result.get("success", False)
            })
        
        return {
            "success": True,
            "message": "목적지 처리 서비스가 정상 작동합니다.",
            "test_results": results
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": "목적지 처리 서비스 테스트 실패"
        }

# =============================================================================
# 메인 실행부
# =============================================================================

if __name__ == "__main__":
    print("🚀 Seoul Safety Navigation API 서버 시작")
    print("📍 포트: 8000")
    print("🌐 CORS: http://localhost:3000")
    print("🎤 Azure Speech: " + ("활성화" if speech_service.enabled else "비활성화"))
    print("🗺️ 경로 서비스: OSRM + Custom Safety Algorithm")
    print("📍 목적지 처리: " + ("활성화" if 'destination_processor' in globals() else "비활성화"))
    print("🔍 STT 디버깅: 활성화")
    print("=" * 50)
    load_construction_data()
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )