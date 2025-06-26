import csv
import os

# CSV 파일 경로 설정 - 프로젝트 구조에 맞게 수정
# data/risk_zones/risk_zones.py → data/csv/sinkhole_processed_data.csv
CSV_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "csv", "sinkhole_processed_data.csv"
)


def load_risk_zones():
    risk_zones = []

    with open(CSV_PATH, newline="", encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            zone = {
                "lat": float(row["center_lat"]),
                "lng": float(row["center_lng"]),
                "risk": float(row["risk_score"]),
                "name": row["closest_district"],
            }
            risk_zones.append(zone)

    return risk_zones


# 직접 실행 시 테스트
if __name__ == "__main__":
    RISK_ZONES = load_risk_zones()
