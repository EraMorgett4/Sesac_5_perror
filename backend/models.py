# models.py
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship  # ← 이렇게 수정
from database import Base
from datetime import datetime

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    hashed_password = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    
    # 관계
    predictions = relationship("RiskPrediction", back_populates="user")

class Location(Base):
    __tablename__ = "locations"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    address = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

class RiskPrediction(Base):
    __tablename__ = "risk_predictions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    risk_score = Column(Float, nullable=False)
    prediction_date = Column(DateTime, default=datetime.utcnow)
    
    # 관계
    user = relationship("User", back_populates="predictions")