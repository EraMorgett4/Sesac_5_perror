from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional
import uvicorn

app = FastAPI(
    title="위치 정보 API", description="Geolocation을 활용한 위치 정보 처리 API"
)


# Pydantic 모델: 위치 데이터 검증
class LocationData(BaseModel):
    latitude: float
    longitude: float
    accuracy: Optional[float] = None
    timestamp: Optional[str] = None


# 정적 파일 서빙 (HTML, CSS, JS)
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def serve_index():
    """메인 페이지 제공"""
    return FileResponse("static/index.html")


@app.post("/api/location")
async def receive_location(location: LocationData):
    """
    클라이언트로부터 위치 정보를 받아 처리

    Args:
        location: 위도, 경도 및 추가 정보가 포함된 위치 데이터

    Returns:
        처리 결과 및 받은 위치 정보
    """
    try:
        # 위치 데이터 검증
        if not (-90 <= location.latitude <= 90):
            raise HTTPException(
                status_code=400, detail="위도는 -90 ~ 90 범위여야 합니다"
            )

        if not (-180 <= location.longitude <= 180):
            raise HTTPException(
                status_code=400, detail="경도는 -180 ~ 180 범위여야 합니다"
            )

        # 위치 정보 처리 로직 (예: DB 저장, 외부 API 호출 등)
        result = {
            "status": "success",
            "message": "위치 정보가 성공적으로 수신되었습니다",
            "received_data": {
                "latitude": location.latitude,
                "longitude": location.longitude,
                "accuracy": location.accuracy,
                "timestamp": location.timestamp,
            },
            "location_info": f"위도: {location.latitude:.6f}, 경도: {location.longitude:.6f}",
        }

        # 실제 운영환경에서는 여기서 데이터베이스 저장, 로깅 등 수행
        print(f"[위치 수신] 위도: {location.latitude}, 경도: {location.longitude}")

        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"서버 오류: {str(e)}")


@app.get("/api/health")
async def health_check():
    """API 상태 확인"""
    return {"status": "healthy", "message": "API가 정상 작동 중입니다"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
