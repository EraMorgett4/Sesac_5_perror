from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import List, Optional, Dict, Any

class UserCreate(BaseModel):
    email: EmailStr
    name: str
    password: str

class UserResponse(BaseModel):
    id: int
    email: str
    name: str
    
    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str

class LocationRequest(BaseModel):
    latitude: float
    longitude: float
    name: Optional[str] = None

class RiskResponse(BaseModel):
    latitude: float
    longitude: float
    risk_score: float
    risk_level: str
    message: str

class RouteRequest(BaseModel):
    start_latitude: float
    start_longitude: float
    end_latitude: float
    end_longitude: float

class Waypoint(BaseModel):
    lat: float
    lng: float

class DangerousZone(BaseModel):
    lat: float
    lng: float
    risk: float
    name: str

class RouteResponse(BaseModel):
    waypoints: List[Waypoint]
    distance: float
    estimated_time: int  # 분
    route_type: str  # "direct" or "safe_detour"
    avoided_zones: List[DangerousZone]
    message: str


class RouteStep(BaseModel):
    """경로 단계별 안내 정보"""
    instruction: str
    distance: float  # 미터 단위
    duration: float  # 초 단위
    name: str
    mode: str = "walking"

class RouteWaypoint(BaseModel):
    """경로 웨이포인트"""
    lat: float
    lng: float

class RouteRequest(BaseModel):
    """경로 요청"""
    start_latitude: float
    start_longitude: float
    end_latitude: float
    end_longitude: float

class RouteResponse(BaseModel):
    """경로 응답 (도보 경로 정보 포함)"""
    waypoints: List[RouteWaypoint]
    distance: float  # km 단위
    estimated_time: int  # 분 단위
    route_type: str
    avoided_zones: List[Dict[str, Any]] = []
    steps: List[RouteStep] = []
    message: str

class GeocodeResponse(BaseModel):
    """지오코딩 응답"""
    address: str
    latitude: float
    longitude: float
    display_name: str

# 기존 스키마도 유지
class LocationRequest(BaseModel):
    latitude: float
    longitude: float

class RiskResponse(BaseModel):
    latitude: float
    longitude: float
    risk_score: float
    risk_level: str
    message: str

class UserCreate(BaseModel):
    username: str
    email: str
    password: str

class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    created_at: str

    class Config:
        from_attributes = True