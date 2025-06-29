# azure_ml_service.py
"""
Azure ML 통신 전담 모듈
"""

import aiohttp
import asyncio
import logging
from typing import Dict

logger = logging.getLogger(__name__)


class AzureMLPredictor:
    def __init__(self):
        self.url = (
            "http://20.249.185.24:80/api/v1/service/risk200-realtime-endpoint/score"  # Neural Network
            # "http://20.249.185.24:80/api/v1/service/risk200-decisionforest-endpoit/score"  # Decision Forest
        )
        self.api_key = (
            "NPv48POoIswLdbyLiuoQUUcpX7xLYfca"  # Neural Network
            # "vAiTMXjDzaS8C3AoVRmwUeCLlAOVmKQq"  # Decision Forest
        )
        self.headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

    async def predict_risk(self, location_features: Dict) -> Dict:
        """Azure ML 엔드포인트로 위험도 예측 요청"""
        try:
            print(f"🤖 Azure ML 예측 요청 시작...")
            print(f"📊 입력 피처 개수: {len(location_features)}")

            # Azure ML 입력 형태로 변환
            azure_input = {
                "Inputs": {"input1": [location_features]},
                "GlobalParameters": {},
            }

            print(f"📤 Azure ML로 전송할 데이터:")
            print(f"  - location: {location_features.get('location_name')}")
            print(f"  - 위도: {location_features.get('target_lat')}")
            print(f"  - 경도: {location_features.get('target_lng')}")
            print(f"  - 공사장: {location_features.get('nearby_construction_count')}개")
            print(f"  - 싱크홀: {location_features.get('nearby_sinkhole_count')}개")

            # 비동기 HTTP 요청
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.url, json=azure_input, headers=self.headers, timeout=30
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        print(f"✅ Azure ML 응답 성공!")
                        print(f"📥 응답 데이터 구조: {list(result.keys())}")

                        return {
                            "success": True,
                            "prediction": result,
                            "features": location_features,
                        }
                    else:
                        error_text = await response.text()
                        print(f"❌ Azure ML HTTP 오류: {response.status}")
                        print(f"❌ 오류 내용: {error_text}")
                        return {
                            "success": False,
                            "error": f"HTTP {response.status}: {error_text}",
                        }

        except asyncio.TimeoutError:
            print("❌ Azure ML 요청 시간 초과 (30초)")
            return {"success": False, "error": "Azure ML 요청 시간 초과 (30초)"}
        except Exception as e:
            print(f"❌ Azure ML 통신 오류: {e}")
            return {"success": False, "error": f"Azure ML 통신 오류: {str(e)}"}


# 전역 인스턴스
azure_ml_predictor = AzureMLPredictor()
