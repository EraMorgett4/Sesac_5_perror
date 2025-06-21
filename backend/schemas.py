from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import List, Optional

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
