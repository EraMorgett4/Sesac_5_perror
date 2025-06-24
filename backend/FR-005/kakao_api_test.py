import os
import requests
from dotenv import load_dotenv

load_dotenv()

# API 키 확인
api_key = os.getenv("KAKAO_REST_API_KEY")
print(f"API 키: {api_key[:10] if api_key else 'None'}...")

# 테스트 호출
url = "https://dapi.kakao.com/v2/local/search/address.json"
headers = {"Authorization": f"KakaoAK {api_key}"}
params = {"query": "서울시 강남구"}

response = requests.get(url, headers=headers, params=params)

print(f"응답 코드: {response.status_code}")
print(f"응답 내용: {response.text[:200]}")

if response.status_code == 403:
    print("\n❌ 403 오류 - 확인사항:")
    print("1. 카카오 콘솔 → 제품설정 → 카카오맵 → Local API 활성화")
    print("2. REST API 키 (JavaScript 키 아님)")
    print("3. API 키 앞뒤 공백 제거")
