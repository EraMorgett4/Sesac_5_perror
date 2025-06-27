import urllib.request
import json
import sys


class AzureMLPredictor:
    def __init__(self):
        self.url = (
            "http://20.249.185.24:80/api/v1/service/risk200-realtime-endpoint/score"
        )
        self.api_key = "NPv48POoIswLdbyLiuoQUUcpX7xLYfca"
        self.headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

    def predict(self, data):
        """
        Azure ML 엔드포인트로 예측 요청을 보냅니다.

        Args:
            data (dict): 예측에 사용할 입력 데이터

        Returns:
            dict: 예측 결과
        """
        try:
            # 데이터를 JSON으로 인코딩
            body = str.encode(json.dumps(data))

            # 요청 생성
            req = urllib.request.Request(self.url, body, self.headers)

            # 요청 전송
            response = urllib.request.urlopen(req)
            result = response.read()

            # 결과를 JSON으로 파싱
            return json.loads(result.decode("utf-8"))

        except urllib.error.HTTPError as error:
            print(f"HTTP 오류 발생: {error.code}")
            print("헤더 정보:", error.info())
            print("오류 내용:", error.read().decode("utf8", "ignore"))
            return None

        except Exception as e:
            print(f"예상치 못한 오류 발생: {str(e)}")
            return None


# 사용 예시
if __name__ == "__main__":
    # 예측기 인스턴스 생성
    predictor = AzureMLPredictor()

    # 실제 위험도 분석 데이터 (Azure ML 형식에 맞춤)
    sample_data = {
        "Inputs": {
            "input1": [
                {
                    "location_name": "4.19민주묘지역",
                    "target_lat": 37.6495,
                    "target_lng": 127.0137,
                    "analysis_radius_km": 0.2,
                    "nearby_construction_count": 0,
                    "weighted_construction_risk": 0.0,
                    "nearby_sinkhole_count": 1,
                    "weighted_sinkhole_risk": 0.19999999999999998,
                    "avg_daily_visitors": 0.0,
                    "total_daily_visitors": 0,
                    "nearby_subway_stations": 2463,
                    "avg_subway_passengers": 6059.691027202599,
                    "avg_rainfall": 0.0,
                    "weighted_rainfall_risk": 0.0,
                    "rainfall_amplification_factor": 1.0,
                    "ongoing_construction_count": 0,
                    "recent_sinkhole_count": 0,
                    "population_density_score": 0.0,
                    "total_subway_passengers": 14925019,
                    "subway_congestion_risk": 0.12119382054405198,
                    "physical_risk_score": 1.7999999999999998,
                    "social_risk_score": 1.454325846528624,
                    "final_risk_score": 1.679014046285018,
                    "comprehensive_risk_level": "매우낮음",
                    "comprehensive_risk_category": "최저위험",
                    "construction_rainfall_interaction": 0.0,
                    "population_physical_interaction": 0.0,
                    "subway_population_ratio": 14925019.0,
                    "risk_density": 13.361169249349247,
                    "activity_density": 118769527.47952282,
                    "distance_from_center": 0.09035203373472739,
                    "total_infrastructure_risk": 1,
                    "total_mobility_volume": 14925019,
                }
            ]
        },
        "GlobalParameters": {},
    }

    print("Azure ML 엔드포인트 호출 중...")
    result = predictor.predict(sample_data)

    if result:
        print("예측 결과:")
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print("예측 실패")


# 여러 데이터 포인트를 한 번에 예측하는 함수
def batch_predict(predictor, data_list):
    """
    여러 데이터 포인트를 배치로 예측합니다.

    Args:
        predictor: AzureMLPredictor 인스턴스
        data_list: 예측할 데이터들의 리스트

    Returns:
        list: 각 데이터 포인트에 대한 예측 결과 리스트
    """
    results = []

    for i, data in enumerate(data_list):
        print(f"데이터 {i+1} 예측 중...")
        result = predictor.predict(data)
        results.append(result)

    return results


# 새로운 위치의 위험도를 분석하는 함수
def analyze_location_risk(predictor, location_data):
    """
    특정 위치의 위험도를 분석합니다.

    Args:
        predictor: AzureMLPredictor 인스턴스
        location_data: 위치별 위험도 데이터 (dict)

    Returns:
        dict: 예측 결과
    """
    data = {"Inputs": {"input1": [location_data]}, "GlobalParameters": {}}
    return predictor.predict(data)


# 실제 사용 예시 - 다른 위치 데이터
def example_usage():
    predictor = AzureMLPredictor()

    # 새로운 분석 대상 위치 예시
    new_location = {
        "location_name": "강남역",
        "target_lat": 37.4980,
        "target_lng": 127.0276,
        "analysis_radius_km": 0.2,
        "nearby_construction_count": 3,
        "weighted_construction_risk": 0.6,
        "nearby_sinkhole_count": 0,
        "weighted_sinkhole_risk": 0.0,
        "avg_daily_visitors": 50000.0,
        "total_daily_visitors": 50000,
        "nearby_subway_stations": 1,
        "avg_subway_passengers": 180000.0,
        "avg_rainfall": 15.2,
        "weighted_rainfall_risk": 0.3,
        "rainfall_amplification_factor": 1.2,
        "ongoing_construction_count": 2,
        "recent_sinkhole_count": 0,
        "population_density_score": 95.0,
        "total_subway_passengers": 180000,
        "subway_congestion_risk": 0.8,
        "physical_risk_score": 2.5,
        "social_risk_score": 3.2,
        "final_risk_score": 2.85,
        "comprehensive_risk_level": "중간",
        "comprehensive_risk_category": "주의",
        "construction_rainfall_interaction": 0.18,
        "population_physical_interaction": 237.5,
        "subway_population_ratio": 3.6,
        "risk_density": 45.2,
        "activity_density": 2500000.0,
        "distance_from_center": 0.02,
        "total_infrastructure_risk": 3,
        "total_mobility_volume": 230000,
    }

    print("새로운 위치 위험도 분석 중...")
    result = analyze_location_risk(predictor, new_location)

    if result:
        print(f"위치: {new_location['location_name']}")
        print("분석 결과:")
        print(json.dumps(result, indent=2, ensure_ascii=False))

    return result


# 여러 위치를 한 번에 분석하는 함수
def analyze_multiple_locations(predictor, locations_list):
    """
    여러 위치를 한 번에 분석합니다.

    Args:
        predictor: AzureMLPredictor 인스턴스
        locations_list: 위치 데이터 리스트

    Returns:
        dict: 예측 결과
    """
    data = {"Inputs": {"input1": locations_list}, "GlobalParameters": {}}
    return predictor.predict(data)
