# main.py
from fastapi import FastAPI, Depends, HTTPException, status, File, Form, UploadFile
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List, Optional
import uvicorn
from datetime import datetime, timedelta
import random
import math
import requests
import os

# # RISK_ZONES 데이터 로딩
import sys
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
# project_root = Path(__file__).parent.parent
# sys.path.insert(0, str(project_root))

# from data.risk_zones.risk_zones import load_risk_zones

# RISK_ZONES = load_risk_zones()

# import base64
# import io
# from PIL import Image
from dotenv import load_dotenv
from chatbot_routes import chatbot_router

from database import SessionLocal, engine, Base
from models import User, Location, RiskPrediction
from schemas import (
    UserCreate,
    UserResponse,
    LocationRequest,
    RiskResponse,
    RouteRequest,
    RouteResponse,
)
from auth import (
    get_password_hash,
    verify_password,
    create_access_token,
    get_current_user,
)


load_dotenv()
KAKAO_API_KEY = os.getenv("KAKAO_API_KEY", "YOUR_KAKAO_REST_API_KEY")

# 데이터베이스 테이블 생성
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Seoul Sinkhole Prediction API", version="1.0.0")

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # React 개발 서버
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
app.include_router(chatbot_router)


# 데이터베이스 의존성
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# 서울시 더미 위험지역 데이터 (실제 좌표 기반)
RISK_ZONES = [
    {"lat": 37.5665, "lng": 126.9780, "risk": 0.85, "name": "중구 명동"},
    {"lat": 37.5663, "lng": 126.9779, "risk": 0.90, "name": "중구 명동 인근"},
    {"lat": 37.5519, "lng": 126.9918, "risk": 0.78, "name": "강남구 논현동"},
    {"lat": 37.5172, "lng": 127.0473, "risk": 0.82, "name": "강남구 삼성동"},
    {"lat": 37.5794, "lng": 126.9770, "risk": 0.75, "name": "종로구 종로1가"},
    {"lat": 37.5512, "lng": 126.9882, "risk": 0.88, "name": "서초구 서초동"},
    {"lat": 37.5326, "lng": 126.9026, "risk": 0.73, "name": "영등포구 여의도동"},
    {"lat": 37.5838, "lng": 127.0580, "risk": 0.80, "name": "성동구 성수동"},
    {"lat": 37.5145, "lng": 126.9061, "risk": 0.77, "name": "관악구 신림동"},
    {"lat": 37.6065, "lng": 127.0921, "risk": 0.84, "name": "동대문구 청량리동"},
    {"lat": 37.6495, "lng": 127.0137, "risk": 0.17, "name": "4.19민주묘지역"},
    {"lat": 37.4931, "lng": 127.1183, "risk": 0.79, "name": "가락시장역"},
    {"lat": 37.4804, "lng": 126.8827, "risk": 1.68, "name": "가산디지털단지역"},
    {"lat": 37.5614, "lng": 126.8544, "risk": 0.82, "name": "가양역"},
    {"lat": 37.6415, "lng": 127.0168, "risk": 0.65, "name": "가오리역"},
    {"lat": 37.5688, "lng": 126.9148, "risk": 0.2, "name": "가좌역"},
    {"lat": 37.4771, "lng": 126.9635, "risk": 0.76, "name": "낙성대역"},
    {"lat": 37.4863, "lng": 126.8874, "risk": 0.83, "name": "남구로역"},
    {"lat": 37.4852, "lng": 127.0162, "risk": 1.63, "name": "남부터미널역"},
    {"lat": 37.4848, "lng": 126.9709, "risk": 0.76, "name": "남성역"},
    {"lat": 37.5406, "lng": 126.9713, "risk": 0.65, "name": "남영역"},
    {"lat": 37.4642, "lng": 126.9891, "risk": 0.41, "name": "남태령역"},
    {"lat": 37.4877, "lng": 126.9936, "risk": 0.54, "name": "내방역"},
    {"lat": 37.5127, "lng": 126.9531, "risk": 0.36, "name": "노들역"},
    {"lat": 37.5136, "lng": 126.9409, "risk": 1.01, "name": "노량진역"},
    {"lat": 37.6563, "lng": 127.0634, "risk": 1.59, "name": "노원역"},
    {"lat": 37.6008, "lng": 126.9358, "risk": 0.69, "name": "녹번역"},
    {"lat": 37.5347, "lng": 126.9865, "risk": 1.28, "name": "녹사평역"},
    {"lat": 37.6446, "lng": 127.0514, "risk": 0.07, "name": "녹천역"},
    {"lat": 37.5112, "lng": 127.0217, "risk": 0.7, "name": "논현역"},
    {"lat": 37.567, "lng": 127.0526, "risk": 0.82, "name": "답십리역"},
    {"lat": 37.6702, "lng": 127.0791, "risk": 0.29, "name": "당고개역"},
    {"lat": 37.4902, "lng": 126.9276, "risk": 1.95, "name": "당곡역"},
    {"lat": 37.5348, "lng": 126.9026, "risk": 0.89, "name": "당산역"},
    {"lat": 37.4933, "lng": 126.8949, "risk": 0.82, "name": "대림역"},
    {"lat": 37.4916, "lng": 127.0731, "risk": 0.65, "name": "대모산입구역"},
    {"lat": 37.5134, "lng": 126.9265, "risk": 0.52, "name": "대방역"},
    {"lat": 37.4937, "lng": 127.0795, "risk": 0.15, "name": "대청역"},
    {"lat": 37.4945, "lng": 127.0632, "risk": 0.77, "name": "대치역"},
    {"lat": 37.5476, "lng": 126.9425, "risk": 0.38, "name": "대흥역"},
    {"lat": 37.491, "lng": 127.0555, "risk": 0.78, "name": "도곡역"},
    {"lat": 37.5145, "lng": 126.8826, "risk": 0.36, "name": "도림천역"},
    {"lat": 37.6895, "lng": 127.0461, "risk": 0.73, "name": "도봉산역"},
    {"lat": 37.6792, "lng": 127.0455, "risk": 0.36, "name": "도봉역"},
    {"lat": 37.5745, "lng": 126.9579, "risk": 1.49, "name": "독립문역"},
    {"lat": 37.6184, "lng": 126.9331, "risk": 0.05, "name": "독바위역"},
    {"lat": 37.466, "lng": 126.8895, "risk": 0.38, "name": "독산역"},
    {"lat": 37.6105, "lng": 127.0564, "risk": 0.4, "name": "돌곶이역"},
    {"lat": 37.5717, "lng": 127.0106, "risk": 1.82, "name": "동대문역"},
    {"lat": 37.5657, "lng": 127.009, "risk": 1.18, "name": "동대문역사문화공원역"},
    {"lat": 37.5591, "lng": 127.0053, "risk": 0.95, "name": "동대입구역"},
    {"lat": 37.5732, "lng": 127.0164, "risk": 1.6, "name": "동묘앞역"},
    {"lat": 37.5027, "lng": 126.9785, "risk": 0.38, "name": "동작역"},
    {"lat": 37.5277, "lng": 127.1362, "risk": 0.66, "name": "둔촌동역"},
    {"lat": 37.5194, "lng": 127.1387, "risk": 0.55, "name": "둔촌오륜역"},
    {"lat": 37.5507, "lng": 126.8656, "risk": 0.53, "name": "등촌역"},
    {"lat": 37.576, "lng": 126.9013, "risk": 0.77, "name": "디지털미디어시티역"},
    {"lat": 37.5472, "lng": 127.0474, "risk": 0.34, "name": "뚝섬역"},
    {"lat": 37.5316, "lng": 127.0668, "risk": 0.62, "name": "뚝섬유원지역"},
    {"lat": 37.5667, "lng": 126.8274, "risk": 0.78, "name": "마곡나루역"},
    {"lat": 37.5602, "lng": 126.8247, "risk": 0.37, "name": "마곡역"},
    {"lat": 37.6652, "lng": 127.0577, "risk": 0.78, "name": "마들역"},
    {"lat": 37.5661, "lng": 127.043, "risk": 2.55, "name": "마장역"},
    {"lat": 37.495, "lng": 127.1529, "risk": 0.33, "name": "마천역"},
    {"lat": 37.5635, "lng": 126.9034, "risk": 0.53, "name": "마포구청역"},
    {"lat": 37.5396, "lng": 126.9459, "risk": 0.58, "name": "마포역"},
    {"lat": 37.5993, "lng": 127.0924, "risk": 0.12, "name": "망우역"},
    {"lat": 37.5561, "lng": 126.9101, "risk": 1.02, "name": "망원역"},
    {"lat": 37.4869, "lng": 127.0467, "risk": 0.18, "name": "매봉역"},
    {"lat": 37.6106, "lng": 127.0778, "risk": 0.75, "name": "먹골역"},
    {"lat": 37.5887, "lng": 127.0875, "risk": 0.65, "name": "면목역"},
    {"lat": 37.561, "lng": 126.9864, "risk": 1.04, "name": "명동역"},
    {"lat": 37.5514, "lng": 127.144, "risk": 0.72, "name": "명일역"},
    {"lat": 37.5261, "lng": 126.8646, "risk": 0.54, "name": "목동역"},
    {"lat": 37.5178, "lng": 127.1129, "risk": 0.22, "name": "몽촌토성역"},
    {"lat": 37.5826, "lng": 126.9502, "risk": 0.65, "name": "무악재역"},
    {"lat": 37.518, "lng": 126.8948, "risk": 0.67, "name": "문래역"},
    {"lat": 37.486, "lng": 127.1225, "risk": 0.89, "name": "문정역"},
    {"lat": 37.6133, "lng": 127.0301, "risk": 3.22, "name": "미아사거리역"},
    {"lat": 37.6267, "lng": 127.026, "risk": 0.36, "name": "미아역"},
    {"lat": 37.5082, "lng": 127.0116, "risk": 0.56, "name": "반포역"},
    {"lat": 37.5587, "lng": 126.8377, "risk": 0.61, "name": "발산역"},
    {"lat": 37.4815, "lng": 126.9976, "risk": 0.51, "name": "방배역"},
    {"lat": 37.5088, "lng": 127.1261, "risk": 0.51, "name": "방이역"},
    {"lat": 37.6674, "lng": 127.0443, "risk": 1.05, "name": "방학역"},
    {"lat": 37.5776, "lng": 126.8128, "risk": 0.11, "name": "방화역"},
    {"lat": 37.5478, "lng": 127.0067, "risk": 0.15, "name": "버티고개역"},
    {"lat": 37.4954, "lng": 126.9181, "risk": 0.03, "name": "보라매공원역"},
    {"lat": 37.493, "lng": 126.9235, "risk": 0.11, "name": "보라매병원역"},
    {"lat": 37.4999, "lng": 126.9206, "risk": 0.53, "name": "보라매역"},
    {"lat": 37.5855, "lng": 127.02, "risk": 0.73, "name": "보문역"},
    {"lat": 37.4707, "lng": 127.1267, "risk": 0.5, "name": "복정역"},
    {"lat": 37.5143, "lng": 127.0602, "risk": 1.52, "name": "봉은사역"},
    {"lat": 37.4825, "lng": 126.9417, "risk": 1.53, "name": "봉천역"},
    {"lat": 37.6174, "lng": 127.0914, "risk": 0.14, "name": "봉화산역"},
    {"lat": 37.6121, "lng": 127.0083, "risk": 0.68, "name": "북한산보국문역"},
    {"lat": 37.6629, "lng": 127.0128, "risk": 0.52, "name": "북한산우이역"},
    {"lat": 37.61, "lng": 126.9303, "risk": 1.52, "name": "불광역"},
    {"lat": 37.6702, "lng": 127.0791, "risk": 0.29, "name": "불암산역"},
    {"lat": 37.5809, "lng": 127.0885, "risk": 0.77, "name": "사가정역"},
    {"lat": 37.4766, "lng": 126.9816, "risk": 1.47, "name": "사당역"},
    {"lat": 37.5042, "lng": 127.0153, "risk": 0.52, "name": "사평역"},
    {"lat": 37.5344, "lng": 126.9729, "risk": 0.68, "name": "삼각지역"},
    {"lat": 37.5088, "lng": 127.063, "risk": 1.34, "name": "삼성역"},
    {"lat": 37.513, "lng": 127.053, "risk": 0.49, "name": "삼성중앙역"},
    {"lat": 37.6213, "lng": 127.0205, "risk": 0.04, "name": "삼양사거리역"},
    {"lat": 37.6269, "lng": 127.0182, "risk": 0.62, "name": "삼양역"},
    {"lat": 37.5045, "lng": 127.0874, "risk": 0.49, "name": "삼전역"},
    {"lat": 37.6607, "lng": 127.0734, "risk": 1.33, "name": "상계역"},
    {"lat": 37.5029, "lng": 126.9479, "risk": 0.55, "name": "상도역"},
    {"lat": 37.5969, "lng": 127.0857, "risk": 0.48, "name": "상봉역"},
    {"lat": 37.5478, "lng": 126.9224, "risk": 0.4, "name": "상수역"},
    {"lat": 37.5644, "lng": 127.0293, "risk": 0.72, "name": "상왕십리역"},
    {"lat": 37.6066, "lng": 127.0488, "risk": 0.68, "name": "상월곡역"},
    {"lat": 37.5567, "lng": 127.1659, "risk": 0.8, "name": "상일동역"},
    {"lat": 37.5909, "lng": 126.9136, "risk": 0.78, "name": "새절역"},
    {"lat": 37.5174, "lng": 126.9284, "risk": 0.54, "name": "샛강역"},
    {"lat": 37.5521, "lng": 126.9355, "risk": 0.4, "name": "서강대역"},
    {"lat": 37.5658, "lng": 126.9666, "risk": 0.87, "name": "서대문역"},
    {"lat": 37.5196, "lng": 126.9884, "risk": 0.43, "name": "서빙고역"},
    {"lat": 37.472, "lng": 126.934, "risk": 2.09, "name": "서울대벤처타운역"},
    {"lat": 37.4813, "lng": 126.9527, "risk": 1.14, "name": "서울대입구역"},
    {"lat": 37.5436, "lng": 127.0447, "risk": 0.55, "name": "서울숲역"},
    {"lat": 37.5541, "lng": 126.9707, "risk": 1.82, "name": "서울역"},
    {"lat": 37.5061, "lng": 126.9227, "risk": 0.37, "name": "서울지방병무청역"},
    {"lat": 37.4918, "lng": 127.0077, "risk": 0.59, "name": "서초역"},
    {"lat": 37.615, "lng": 127.0657, "risk": 0.61, "name": "석계역"},
    {"lat": 37.5025, "lng": 127.0965, "risk": 0.6, "name": "석촌고분역"},
    {"lat": 37.5054, "lng": 127.107, "risk": 0.83, "name": "석촌역"},
    {"lat": 37.5045, "lng": 127.049, "risk": 1.48, "name": "선릉역"},
    {"lat": 37.5382, "lng": 126.8933, "risk": 0.62, "name": "선유도역"},
    {"lat": 37.5109, "lng": 127.0436, "risk": 0.26, "name": "선정릉역"},
    {"lat": 37.5446, "lng": 127.0561, "risk": 0.58, "name": "성수역"},
    {"lat": 37.593, "lng": 127.0171, "risk": 2.89, "name": "성신여대입구역"},
    {"lat": 37.656, "lng": 127.0133, "risk": 0.04, "name": "솔밭공원역"},
    {"lat": 37.6203, "lng": 127.0136, "risk": 0.67, "name": "솔샘역"},
    {"lat": 37.511, "lng": 127.1127, "risk": 0.58, "name": "송파나루역"},
    {"lat": 37.4997, "lng": 127.1122, "risk": 0.66, "name": "송파역"},
    {"lat": 37.6779, "lng": 127.0554, "risk": 0.2, "name": "수락산역"},
    {"lat": 37.5808, "lng": 126.8957, "risk": 0.48, "name": "수색역"},
    {"lat": 37.4855, "lng": 127.1044, "risk": 0.52, "name": "수서역"},
    {"lat": 37.6379, "lng": 127.0255, "risk": 1.76, "name": "수유역"},
    {"lat": 37.5446, "lng": 126.9721, "risk": 0.72, "name": "숙대입구역"},
    {"lat": 37.4963, "lng": 126.9536, "risk": 0.62, "name": "숭실대입구역"},
    {"lat": 37.5653, "lng": 126.9772, "risk": 0.75, "name": "시청역"},
    {"lat": 37.5545, "lng": 127.0205, "risk": 0.22, "name": "신금호역"},
    {"lat": 37.5168, "lng": 126.9184, "risk": 0.58, "name": "신길역"},
    {"lat": 37.6125, "lng": 127.1043, "risk": 0.03, "name": "신내역"},
    {"lat": 37.5048, "lng": 127.0255, "risk": 1.57, "name": "신논현역"},
    {"lat": 37.5698, "lng": 127.0471, "risk": 0.61, "name": "신답역"},
    {"lat": 37.5657, "lng": 127.0195, "risk": 0.37, "name": "신당역"},
    {"lat": 37.4998, "lng": 126.9282, "risk": 0.58, "name": "신대방삼거리역"},
    {"lat": 37.4877, "lng": 126.9135, "risk": 0.66, "name": "신대방역"},
    {"lat": 37.5089, "lng": 126.8913, "risk": 1.48, "name": "신도림역"},
    {"lat": 37.4843, "lng": 126.9297, "risk": 2.94, "name": "신림역"},
    {"lat": 37.5443, "lng": 126.8831, "risk": 0.24, "name": "신목동역"},
    {"lat": 37.5035, "lng": 126.9961, "risk": 0.41, "name": "신반포역"},
    {"lat": 37.5675, "lng": 126.8172, "risk": 0.23, "name": "신방화역"},
    {"lat": 37.5164, "lng": 127.0203, "risk": 0.83, "name": "신사역"},
    {"lat": 37.576, "lng": 127.0245, "risk": 0.81, "name": "신설동역"},
    {"lat": 37.5293, "lng": 126.968, "risk": 0.75, "name": "신용산역"},
    {"lat": 37.6018, "lng": 127.0674, "risk": 0.49, "name": "신이문역"},
    {"lat": 37.5202, "lng": 126.8529, "risk": 0.61, "name": "신정네거리역"},
    {"lat": 37.525, "lng": 126.8561, "risk": 0.52, "name": "신정역"},
    {"lat": 37.5552, "lng": 126.937, "risk": 1.11, "name": "신촌역"},
    {"lat": 37.5001, "lng": 126.9098, "risk": 0.55, "name": "신풍역"},
    {"lat": 37.6485, "lng": 127.0347, "risk": 1.82, "name": "쌍문역"},
    {"lat": 37.5522, "lng": 127.0896, "risk": 0.72, "name": "아차산역"},
    {"lat": 37.5574, "lng": 126.9561, "risk": 0.38, "name": "아현역"},
    {"lat": 37.5765, "lng": 126.9854, "risk": 0.89, "name": "안국역"},
    {"lat": 37.5863, "lng": 127.0292, "risk": 1.32, "name": "안암역"},
    {"lat": 37.5502, "lng": 127.1275, "risk": 0.86, "name": "암사역"},
    {"lat": 37.5572, "lng": 127.1376, "risk": 0.67, "name": "암사역사공원역"},
    {"lat": 37.5275, "lng": 127.0406, "risk": 0.59, "name": "압구정로데오역"},
    {"lat": 37.5265, "lng": 127.0285, "risk": 0.84, "name": "압구정역"},
    {"lat": 37.5534, "lng": 126.9567, "risk": 0.36, "name": "애오개역"},
    {"lat": 37.5545, "lng": 127.0109, "risk": 0.26, "name": "약수역"},
    {"lat": 37.4846, "lng": 127.0342, "risk": 1.73, "name": "양재역"},
    {"lat": 37.5124, "lng": 126.8657, "risk": 0.11, "name": "양천구청역"},
    {"lat": 37.5681, "lng": 126.842, "risk": 0.5, "name": "양천향교역"},
    {"lat": 37.5256, "lng": 126.8864, "risk": 0.48, "name": "양평역"},
    {"lat": 37.548, "lng": 127.0747, "risk": 0.58, "name": "어린이대공원역"},
    {"lat": 37.5073, "lng": 127.034, "risk": 0.69, "name": "언주역"},
    {"lat": 37.5271, "lng": 126.933, "risk": 0.8, "name": "여의나루역"},
    {"lat": 37.5218, "lng": 126.9244, "risk": 1.3, "name": "여의도역"},
    {"lat": 37.5007, "lng": 127.0365, "risk": 1.21, "name": "역삼역"},
    {"lat": 37.6062, "lng": 126.9228, "risk": 1.96, "name": "역촌역"},
    {"lat": 37.6192, "lng": 126.9211, "risk": 1.07, "name": "연신내역"},
    {"lat": 37.547, "lng": 126.8749, "risk": 0.59, "name": "염창역"},
    {"lat": 37.5258, "lng": 126.8967, "risk": 0.86, "name": "영등포구청역"},
    {"lat": 37.5227, "lng": 126.9052, "risk": 0.66, "name": "영등포시장역"},
    {"lat": 37.5157, "lng": 126.9079, "risk": 1.16, "name": "영등포역"},
    {"lat": 37.5021, "lng": 127.128, "risk": 0.69, "name": "오금역"},
    {"lat": 37.4944, "lng": 126.8448, "risk": 0.63, "name": "오류동역"},
    {"lat": 37.5245, "lng": 126.8753, "risk": 0.7, "name": "오목교역"},
    {"lat": 37.5416, "lng": 127.0174, "risk": 0.27, "name": "옥수역"},
    {"lat": 37.492, "lng": 126.8238, "risk": 0.26, "name": "온수역"},
    {"lat": 37.5163, "lng": 127.131, "risk": 0.67, "name": "올림픽공원역"},
    {"lat": 37.5613, "lng": 127.0371, "risk": 1.96, "name": "왕십리역"},
    {"lat": 37.5963, "lng": 127.0637, "risk": 0.15, "name": "외대앞역"},
    {"lat": 37.5621, "lng": 127.0509, "risk": 0.63, "name": "용답역"},
    {"lat": 37.5741, "lng": 127.0383, "risk": 0.41, "name": "용두역"},
    {"lat": 37.5737, "lng": 127.0867, "risk": 0.62, "name": "용마산역"},
    {"lat": 37.5301, "lng": 126.9648, "risk": 0.65, "name": "용산역"},
    {"lat": 37.5488, "lng": 126.8363, "risk": 0.79, "name": "우장산역"},
    {"lat": 37.6333, "lng": 127.0589, "risk": 0.5, "name": "월계역"},
    {"lat": 37.6018, "lng": 127.0415, "risk": 0.58, "name": "월곡역"},
    {"lat": 37.5696, "lng": 126.8991, "risk": 0.1, "name": "월드컵경기장역"},
    {"lat": 37.5663, "lng": 126.991, "risk": 0.52, "name": "을지로3가역"},
    {"lat": 37.5666, "lng": 126.9976, "risk": 0.29, "name": "을지로4가역"},
    {"lat": 37.566, "lng": 126.9822, "risk": 0.95, "name": "을지로입구역"},
    {"lat": 37.55, "lng": 127.0345, "risk": 0.03, "name": "응봉역"},
    {"lat": 37.5985, "lng": 126.9155, "risk": 0.86, "name": "응암역"},
    {"lat": 37.5568, "lng": 126.9464, "risk": 0.73, "name": "이대역"},
    {"lat": 37.4868, "lng": 126.9822, "risk": 0.66, "name": "이수역"},
    {"lat": 37.5224, "lng": 126.9735, "risk": 0.37, "name": "이촌역"},
    {"lat": 37.5345, "lng": 126.9943, "risk": 0.34, "name": "이태원역"},
    {"lat": 37.484, "lng": 127.0841, "risk": 0.74, "name": "일원역"},
    {"lat": 37.5316, "lng": 127.0668, "risk": 0.62, "name": "자양역"},
    {"lat": 37.5207, "lng": 127.1038, "risk": 0.82, "name": "잠실나루역"},
    {"lat": 37.5116, "lng": 127.0863, "risk": 0.93, "name": "잠실새내역"},
    {"lat": 37.5133, "lng": 127.1002, "risk": 2.11, "name": "잠실역"},
    {"lat": 37.5129, "lng": 127.0114, "risk": 0.08, "name": "잠원역"},
    {"lat": 37.5049, "lng": 126.9391, "risk": 0.54, "name": "장승배기역"},
    {"lat": 37.4786, "lng": 127.1262, "risk": 1.52, "name": "장지역"},
    {"lat": 37.5616, "lng": 127.0637, "risk": 0.47, "name": "장한평역"},
    {"lat": 37.6026, "lng": 127.0135, "risk": 1.25, "name": "정릉역"},
    {"lat": 37.5782, "lng": 127.0349, "risk": 0.72, "name": "제기동역"},
    {"lat": 37.5702, "lng": 126.9832, "risk": 0.86, "name": "종각역"},
    {"lat": 37.5704, "lng": 126.9922, "risk": 1.44, "name": "종로3가역"},
    {"lat": 37.571, "lng": 127.0015, "risk": 0.95, "name": "종로5가역"},
    {"lat": 37.5111, "lng": 127.0738, "risk": 0.79, "name": "종합운동장역"},
    {"lat": 37.6451, "lng": 127.0641, "risk": 0.22, "name": "중계역"},
    {"lat": 37.5659, "lng": 127.0843, "risk": 0.16, "name": "중곡역"},
    {"lat": 37.5948, "lng": 127.0757, "risk": 0.21, "name": "중랑역"},
    {"lat": 37.5284, "lng": 127.1484, "risk": 0.57, "name": "중앙보훈병원역"},
    {"lat": 37.6026, "lng": 127.0793, "risk": 0.71, "name": "중화역"},
    {"lat": 37.5581, "lng": 126.8606, "risk": 0.64, "name": "증미역"},
    {"lat": 37.5837, "lng": 126.9095, "risk": 0.43, "name": "증산역"},
    {"lat": 37.6533, "lng": 127.0476, "risk": 1.22, "name": "창동역"},
    {"lat": 37.5794, "lng": 127.0153, "risk": 0.05, "name": "창신역"},
    {"lat": 37.4869, "lng": 126.8386, "risk": 0.7, "name": "천왕역"},
    {"lat": 37.5385, "lng": 127.1239, "risk": 1.05, "name": "천호역"},
    {"lat": 37.5609, "lng": 127.0142, "risk": 0.12, "name": "청구역"},
    {"lat": 37.5195, "lng": 127.0537, "risk": 1.06, "name": "청담역"},
    {"lat": 37.58, "lng": 127.0477, "risk": 1.2, "name": "청량리역"},
    {"lat": 37.4868, "lng": 126.9822, "risk": 0.66, "name": "총신대입구역"},
    {"lat": 37.5614, "lng": 126.9941, "risk": 0.97, "name": "충무로역"},
    {"lat": 37.5598, "lng": 126.9645, "risk": 0.62, "name": "충정로역"},
    {"lat": 37.6185, "lng": 127.0754, "risk": 0.64, "name": "태릉입구역"},
    {"lat": 37.6365, "lng": 127.068, "risk": 0.77, "name": "하계역"},
    {"lat": 37.5143, "lng": 127.0319, "risk": 1.42, "name": "학동역"},
    {"lat": 37.4969, "lng": 127.0712, "risk": 0.47, "name": "학여울역"},
    {"lat": 37.5398, "lng": 127.0018, "risk": 0.47, "name": "한강진역"},
    {"lat": 37.5294, "lng": 127.0092, "risk": 0.18, "name": "한남역"},
    {"lat": 37.5884, "lng": 127.006, "risk": 0.74, "name": "한성대입구역"},
    {"lat": 37.5165, "lng": 127.1164, "risk": 0.48, "name": "한성백제역"},
    {"lat": 37.5557, "lng": 127.0436, "risk": 0.54, "name": "한양대역"},
    {"lat": 37.4963, "lng": 127.0529, "risk": 1.5, "name": "한티역"},
    {"lat": 37.5499, "lng": 126.9145, "risk": 1.28, "name": "합정역"},
    {"lat": 37.5574, "lng": 127.0295, "risk": 0.37, "name": "행당역"},
    {"lat": 37.582, "lng": 127.0019, "risk": 1.0, "name": "혜화역"},
    {"lat": 37.5569, "lng": 126.9238, "risk": 10.0, "name": "홍대입구역"},
    {"lat": 37.5888, "lng": 126.9442, "risk": 0.87, "name": "홍제역"},
    {"lat": 37.6341, "lng": 127.0175, "risk": 0.64, "name": "화계역"},
    {"lat": 37.5417, "lng": 126.8405, "risk": 1.02, "name": "화곡역"},
    {"lat": 37.6198, "lng": 127.0835, "risk": 1.53, "name": "화랑대역"},
    {"lat": 37.5898, "lng": 127.058, "risk": 0.42, "name": "회기역"},
    {"lat": 37.5588, "lng": 126.9784, "risk": 0.43, "name": "회현역"},
    {"lat": 37.5393, "lng": 126.9614, "risk": 0.59, "name": "효창공원앞역"},
    {"lat": 37.5092, "lng": 126.9635, "risk": 10.0, "name": "흑석역"},
]


@app.post("/register", response_model=UserResponse)
async def register(user: UserCreate, db: Session = Depends(get_db)):
    """회원가입"""
    # 중복 사용자 확인
    db_user = db.query(User).filter(User.email == user.email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    # 새 사용자 생성
    hashed_password = get_password_hash(user.password)
    db_user = User(email=user.email, name=user.name, hashed_password=hashed_password)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    return UserResponse(id=db_user.id, email=db_user.email, name=db_user.name)


@app.post("/token")
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)
):
    """로그인"""
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(data={"sub": user.email})
    return {"access_token": access_token, "token_type": "bearer"}


@app.get("/me", response_model=UserResponse)
async def read_users_me(current_user: User = Depends(get_current_user)):
    """현재 사용자 정보"""
    return UserResponse(
        id=current_user.id, email=current_user.email, name=current_user.name
    )


@app.post("/predict-risk", response_model=RiskResponse)
async def predict_sinkhole_risk(
    location: LocationRequest, db: Session = Depends(get_db)
):
    """지정 위치의 싱크홀 위험도 예측 (로그인 불필요)"""

    # 주변 위험지역과의 거리 기반으로 위험도 계산
    min_distance = float("inf")
    nearest_risk = 0.0

    for zone in RISK_ZONES:
        distance = calculate_distance(
            location.latitude, location.longitude, zone["lat"], zone["lng"]
        )
        if distance < min_distance:
            min_distance = distance
            nearest_risk = zone["risk"]

    # 거리에 따른 위험도 조정 (가까울수록 높은 위험도)
    if min_distance < 0.5:  # 500m 이내
        risk_score = max(0.7, nearest_risk)
    elif min_distance < 1.0:  # 1km 이내
        risk_score = max(0.4, nearest_risk * 0.7)
    elif min_distance < 2.0:  # 2km 이내
        risk_score = max(0.2, nearest_risk * 0.5)
    else:
        risk_score = min(0.3, random.uniform(0.1, 0.3))

    # 예측 결과는 DB에 저장하지 않음 (로그인 불필요하므로)

    return RiskResponse(
        latitude=location.latitude,
        longitude=location.longitude,
        risk_score=round(risk_score, 3),
        risk_level=get_risk_level(risk_score),
        message=get_risk_message(risk_score),
    )


@app.get("/risk-zones")
async def get_risk_zones():
    """서울시 위험지역 목록 반환 (로그인 불필요)"""
    return {"zones": RISK_ZONES, "total_count": len(RISK_ZONES)}


@app.post("/safe-route", response_model=RouteResponse)
async def get_safe_route(route_request: RouteRequest):
    """위험지역을 우회하는 안전 경로 생성 (로그인 불필요)"""

    start_lat, start_lng = route_request.start_latitude, route_request.start_longitude
    end_lat, end_lng = route_request.end_latitude, route_request.end_longitude

    # 직선 경로상의 위험지역 확인
    dangerous_zones = []
    for zone in RISK_ZONES:
        if is_point_near_line(
            start_lat, start_lng, end_lat, end_lng, zone["lat"], zone["lng"], 0.5
        ):
            if zone["risk"] > 0.7:
                dangerous_zones.append(zone)

    # 안전 경로 생성 (위험지역 우회)
    if dangerous_zones:
        # 우회 경로 생성 (시뮬레이션)
        waypoints = generate_safe_waypoints(
            start_lat, start_lng, end_lat, end_lng, dangerous_zones
        )
        route_type = "safe_detour"
        message = f"{len(dangerous_zones)}개의 위험지역을 우회하는 경로입니다."
    else:
        # 직선 경로
        waypoints = [
            {"lat": start_lat, "lng": start_lng},
            {"lat": end_lat, "lng": end_lng},
        ]
        route_type = "direct"
        message = "위험지역이 없어 직선 경로를 제공합니다."

    return RouteResponse(
        waypoints=waypoints,
        distance=calculate_distance(start_lat, start_lng, end_lat, end_lng),
        estimated_time=estimate_travel_time(waypoints),
        route_type=route_type,
        avoided_zones=dangerous_zones,
        message=message,
    )


# 유틸리티 함수들


@app.get("/search-location")
async def search_location(query: str):
    """카카오맵 API를 사용한 지명 검색 - 400 오류 해결"""

    if not query or len(query) < 2:
        return {"places": []}

    # API 키 확인
    if not KAKAO_API_KEY or KAKAO_API_KEY == "YOUR_KAKAO_REST_API_KEY":
        return {"places": [], "error": "카카오 API 키가 설정되지 않았습니다."}

    try:
        url = "https://dapi.kakao.com/v2/local/search/keyword.json"
        headers = {
            "Authorization": f"KakaoAK {KAKAO_API_KEY}"
            # Content-Type 제거 (GET 요청에는 불필요)
        }

        # 파라미터 수정 - 문제가 되는 빈 값들 제거
        params = {
            "query": query.strip(),  # 앞뒤 공백 제거
            "size": 5,  # 10 → 5로 변경
            "page": 1,  # 페이지 명시
            "sort": "accuracy",  # 정렬 기준 명시
            # category_group_code 제거 (빈 값이 400 오류 원인)
        }

        # 서울 지역으로 검색 범위 제한 (선택사항)
        # params["rect"] = "126.734086,37.413294,127.269311,37.715133"  # 서울시 경계

        print(f"카카오 API 호출: {url}")
        print(f"파라미터: {params}")

        response = requests.get(url, headers=headers, params=params, timeout=10)

        # 상세 오류 정보 출력
        if response.status_code != 200:
            print(f"카카오 API 응답 코드: {response.status_code}")
            print(f"응답 내용: {response.text}")

            # 400 오류 시 상세 정보 출력
            if response.status_code == 400:
                try:
                    error_data = response.json()
                    print(f"오류 상세: {error_data}")
                except:
                    pass

        response.raise_for_status()

        data = response.json()
        places = data.get("documents", [])

        print(f"검색 결과: {len(places)}개 찾음")

        # 응답 데이터 포맷팅
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
                "place_url": place.get("place_url", ""),
            }
            formatted_places.append(formatted_place)

        return {"places": formatted_places, "total_count": len(formatted_places)}

    except requests.exceptions.HTTPError as e:
        error_msg = f"카카오맵 API HTTP 오류: {e}"
        print(error_msg)

        if e.response.status_code == 400:
            try:
                error_detail = e.response.json()
                print(f"400 오류 상세: {error_detail}")
                return {
                    "places": [],
                    "error": f"잘못된 요청: {error_detail.get('message', '알 수 없는 오류')}",
                }
            except:
                return {"places": [], "error": "잘못된 요청 형식입니다."}
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
        error_msg = f"지명 검색 오류: {e}"
        print(error_msg)
        return {"places": [], "error": "검색 중 오류가 발생했습니다."}


# 대안: 주소 검색 API도 추가
@app.get("/search-address")
async def search_address(query: str):
    """카카오맵 주소 검색 API (키워드 검색의 대안)"""

    if not query or len(query) < 2:
        return {"addresses": []}

    try:
        url = "https://dapi.kakao.com/v2/local/search/address.json"
        headers = {"Authorization": f"KakaoAK {KAKAO_API_KEY}"}
        params = {"query": query.strip(), "size": 5}

        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()

        data = response.json()
        addresses = data.get("documents", [])

        formatted_addresses = []
        for addr in addresses:
            formatted_addr = {
                "place_name": addr.get("address_name", ""),
                "address_name": addr.get("address_name", ""),
                "road_address_name": addr.get("road_address", {}).get(
                    "address_name", ""
                ),
                "x": addr.get("x", ""),  # 경도
                "y": addr.get("y", ""),  # 위도
                "category_name": "주소",
            }
            formatted_addresses.append(formatted_addr)

        return {
            "places": formatted_addresses,  # 프론트엔드 호환성을 위해 "places"로 반환
            "total_count": len(formatted_addresses),
        }

    except Exception as e:
        print(f"주소 검색 오류: {e}")
        return {"places": [], "error": "주소 검색 중 오류가 발생했습니다."}


# 통합 검색 함수 (키워드 + 주소 검색)
@app.get("/search-location-combined")
async def search_location_combined(query: str):
    """키워드 검색과 주소 검색을 함께 시도"""

    # 먼저 키워드 검색 시도
    keyword_result = await search_location(query)

    if keyword_result.get("places"):
        return keyword_result

    # 키워드 검색 실패 시 주소 검색 시도
    print("키워드 검색 실패, 주소 검색 시도")
    address_result = await search_address(query)

    return address_result


def calculate_distance(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """두 좌표 간 거리 계산 (km)"""
    R = 6371  # 지구 반지름 (km)

    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)

    a = math.sin(dlat / 2) * math.sin(dlat / 2) + math.cos(
        math.radians(lat1)
    ) * math.cos(math.radians(lat2)) * math.sin(dlng / 2) * math.sin(dlng / 2)

    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def get_risk_level(risk_score: float) -> str:
    """위험도 점수에 따른 등급 반환"""
    if risk_score >= 0.8:
        return "매우높음"
    elif risk_score >= 0.6:
        return "높음"
    elif risk_score >= 0.4:
        return "보통"
    elif risk_score >= 0.2:
        return "낮음"
    else:
        return "매우낮음"


def get_risk_message(risk_score: float) -> str:
    """위험도에 따른 메시지 반환"""
    if risk_score >= 0.8:
        return "매우 위험한 지역입니다. 우회 경로를 이용하세요."
    elif risk_score >= 0.6:
        return "위험도가 높은 지역입니다. 주의가 필요합니다."
    elif risk_score >= 0.4:
        return "보통 수준의 위험도입니다."
    elif risk_score >= 0.2:
        return "비교적 안전한 지역입니다."
    else:
        return "매우 안전한 지역입니다."


def is_point_near_line(
    x1: float, y1: float, x2: float, y2: float, px: float, py: float, threshold: float
) -> bool:
    """점이 직선 근처에 있는지 확인"""
    # 점과 직선 사이의 거리 계산
    A = y2 - y1
    B = x1 - x2
    C = x2 * y1 - x1 * y2

    distance = abs(A * px + B * py + C) / math.sqrt(A * A + B * B)
    return distance < threshold


def generate_safe_waypoints(
    start_lat: float,
    start_lng: float,
    end_lat: float,
    end_lng: float,
    dangerous_zones: list,
) -> list:
    """위험지역을 우회하는 경유지 생성"""
    waypoints = [{"lat": start_lat, "lng": start_lng}]

    # 간단한 우회 로직 (실제로는 더 복잡한 경로 찾기 알고리즘 필요)
    mid_lat = (start_lat + end_lat) / 2
    mid_lng = (start_lng + end_lng) / 2

    # 위험지역 근처에서 우회점 생성
    for zone in dangerous_zones:
        if calculate_distance(mid_lat, mid_lng, zone["lat"], zone["lng"]) < 1.0:
            # 우회점 추가 (위험지역에서 1km 떨어진 지점)
            offset_lat = 0.01 if zone["lat"] > mid_lat else -0.01
            offset_lng = 0.01 if zone["lng"] > mid_lng else -0.01

            waypoints.append(
                {"lat": zone["lat"] + offset_lat, "lng": zone["lng"] + offset_lng}
            )

    waypoints.append({"lat": end_lat, "lng": end_lng})
    return waypoints


def estimate_travel_time(waypoints: list) -> int:
    """경로의 예상 소요시간 계산 (분)"""
    total_distance = 0
    for i in range(len(waypoints) - 1):
        total_distance += calculate_distance(
            waypoints[i]["lat"],
            waypoints[i]["lng"],
            waypoints[i + 1]["lat"],
            waypoints[i + 1]["lng"],
        )

    # 평균 속도 30km/h로 가정
    return int(total_distance / 30 * 60)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
