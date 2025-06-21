# main.py
from fastapi import FastAPI, Depends, HTTPException, status
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
from dotenv import load_dotenv


from database import SessionLocal, engine, Base
from models import User, Location, RiskPrediction
from schemas import UserCreate, UserResponse, LocationRequest, RiskResponse, RouteRequest, RouteResponse
from auth import get_password_hash, verify_password, create_access_token, get_current_user


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

# 데이터베이스 의존성
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# 서울시 더미 위험지역 데이터 (실제 좌표 기반)
DUMMY_RISK_ZONES = [
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
]

@app.post("/register", response_model=UserResponse)
async def register(user: UserCreate, db: Session = Depends(get_db)):
    """회원가입"""
    # 중복 사용자 확인
    db_user = db.query(User).filter(User.email == user.email).first()
    if db_user:
        raise HTTPException(
            status_code=400,
            detail="Email already registered"
        )
    
    # 새 사용자 생성
    hashed_password = get_password_hash(user.password)
    db_user = User(
        email=user.email,
        name=user.name,
        hashed_password=hashed_password
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    return UserResponse(id=db_user.id, email=db_user.email, name=db_user.name)

@app.post("/token")
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
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
    return UserResponse(id=current_user.id, email=current_user.email, name=current_user.name)

@app.post("/predict-risk", response_model=RiskResponse)
async def predict_sinkhole_risk(
    location: LocationRequest, 
    db: Session = Depends(get_db)
):
    """지정 위치의 싱크홀 위험도 예측 (로그인 불필요)"""
    
    # 주변 위험지역과의 거리 기반으로 위험도 계산
    min_distance = float('inf')
    nearest_risk = 0.0
    
    for zone in DUMMY_RISK_ZONES:
        distance = calculate_distance(location.latitude, location.longitude, zone["lat"], zone["lng"])
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
        message=get_risk_message(risk_score)
    )

@app.get("/risk-zones")
async def get_risk_zones():
    """서울시 위험지역 목록 반환 (로그인 불필요)"""
    return {
        "zones": DUMMY_RISK_ZONES,
        "total_count": len(DUMMY_RISK_ZONES)
    }

@app.post("/safe-route", response_model=RouteResponse)
async def get_safe_route(route_request: RouteRequest):
    """위험지역을 우회하는 안전 경로 생성 (로그인 불필요)"""
    
    start_lat, start_lng = route_request.start_latitude, route_request.start_longitude
    end_lat, end_lng = route_request.end_latitude, route_request.end_longitude
    
    # 직선 경로상의 위험지역 확인
    dangerous_zones = []
    for zone in DUMMY_RISK_ZONES:
        if is_point_near_line(start_lat, start_lng, end_lat, end_lng, zone["lat"], zone["lng"], 0.5):
            if zone["risk"] > 0.7:
                dangerous_zones.append(zone)
    
    # 안전 경로 생성 (위험지역 우회)
    if dangerous_zones:
        # 우회 경로 생성 (시뮬레이션)
        waypoints = generate_safe_waypoints(start_lat, start_lng, end_lat, end_lng, dangerous_zones)
        route_type = "safe_detour"
        message = f"{len(dangerous_zones)}개의 위험지역을 우회하는 경로입니다."
    else:
        # 직선 경로
        waypoints = [
            {"lat": start_lat, "lng": start_lng},
            {"lat": end_lat, "lng": end_lng}
        ]
        route_type = "direct"
        message = "위험지역이 없어 직선 경로를 제공합니다."
    
    return RouteResponse(
        waypoints=waypoints,
        distance=calculate_distance(start_lat, start_lng, end_lat, end_lng),
        estimated_time=estimate_travel_time(waypoints),
        route_type=route_type,
        avoided_zones=dangerous_zones,
        message=message
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
            "size": 5,               # 10 → 5로 변경
            "page": 1,               # 페이지 명시
            "sort": "accuracy"       # 정렬 기준 명시
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
                "place_url": place.get("place_url", "")
            }
            formatted_places.append(formatted_place)
        
        return {
            "places": formatted_places,
            "total_count": len(formatted_places)
        }
        
    except requests.exceptions.HTTPError as e:
        error_msg = f"카카오맵 API HTTP 오류: {e}"
        print(error_msg)
        
        if e.response.status_code == 400:
            try:
                error_detail = e.response.json()
                print(f"400 오류 상세: {error_detail}")
                return {"places": [], "error": f"잘못된 요청: {error_detail.get('message', '알 수 없는 오류')}"}
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
        headers = {
            "Authorization": f"KakaoAK {KAKAO_API_KEY}"
        }
        params = {
            "query": query.strip(),
            "size": 5
        }
        
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        addresses = data.get("documents", [])
        
        formatted_addresses = []
        for addr in addresses:
            formatted_addr = {
                "place_name": addr.get("address_name", ""),
                "address_name": addr.get("address_name", ""),
                "road_address_name": addr.get("road_address", {}).get("address_name", ""),
                "x": addr.get("x", ""),  # 경도
                "y": addr.get("y", ""),  # 위도
                "category_name": "주소"
            }
            formatted_addresses.append(formatted_addr)
        
        return {
            "places": formatted_addresses,  # 프론트엔드 호환성을 위해 "places"로 반환
            "total_count": len(formatted_addresses)
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
    
    a = (math.sin(dlat/2) * math.sin(dlat/2) + 
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * 
         math.sin(dlng/2) * math.sin(dlng/2))
    
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
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

def is_point_near_line(x1: float, y1: float, x2: float, y2: float, px: float, py: float, threshold: float) -> bool:
    """점이 직선 근처에 있는지 확인"""
    # 점과 직선 사이의 거리 계산
    A = y2 - y1
    B = x1 - x2
    C = x2 * y1 - x1 * y2
    
    distance = abs(A * px + B * py + C) / math.sqrt(A * A + B * B)
    return distance < threshold

def generate_safe_waypoints(start_lat: float, start_lng: float, end_lat: float, end_lng: float, dangerous_zones: list) -> list:
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
            
            waypoints.append({
                "lat": zone["lat"] + offset_lat,
                "lng": zone["lng"] + offset_lng
            })
    
    waypoints.append({"lat": end_lat, "lng": end_lng})
    return waypoints

def estimate_travel_time(waypoints: list) -> int:
    """경로의 예상 소요시간 계산 (분)"""
    total_distance = 0
    for i in range(len(waypoints) - 1):
        total_distance += calculate_distance(
            waypoints[i]["lat"], waypoints[i]["lng"],
            waypoints[i+1]["lat"], waypoints[i+1]["lng"]
        )
    
    # 평균 속도 30km/h로 가정
    return int(total_distance / 30 * 60)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)