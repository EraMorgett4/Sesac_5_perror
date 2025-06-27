import pandas as pd
import numpy as np

# CSV 파일 읽기
df = pd.read_csv("output\integrated_risk_dataset_complete_20250627_020041.csv")

# 현재 위험도 범위 확인
print("=== 정규화 전 위험도 범위 ===")
print(f"최소값: {df['final_risk_score'].min()}")
print(f"최대값: {df['final_risk_score'].max()}")
print(f"평균값: {df['final_risk_score'].mean():.2f}")

# Min-Max 정규화 (0-1 범위로 변환)
min_risk = df["final_risk_score"].min()
max_risk = df["final_risk_score"].max()

# RISK_ZONES 형태로 변환 (정규화된 위험도 적용)
RISK_ZONES = []
for _, row in df.iterrows():
    # Min-Max 정규화: (값 - 최소값) / (최대값 - 최소값)
    normalized_risk = (row["final_risk_score"] - min_risk) / (max_risk - min_risk)

    RISK_ZONES.append(
        {
            "lat": row["target_lat"],
            "lng": row["target_lng"],
            "risk": round(normalized_risk, 3),  # 소수점 3자리로 반올림
            "name": row["location_name"],
        }
    )

# 정규화 후 범위 확인
risks = [zone["risk"] for zone in RISK_ZONES]
print("\n=== 정규화 후 위험도 범위 ===")
print(f"최소값: {min(risks)}")
print(f"최대값: {max(risks)}")
print(f"평균값: {np.mean(risks):.3f}")

# 결과 출력
print("\nRISK_ZONES = [")
for i, zone in enumerate(RISK_ZONES):
    comma = "," if i < len(RISK_ZONES) - 1 else ""
    print(
        f'    {{"lat": {zone["lat"]}, "lng": {zone["lng"]}, "risk": {zone["risk"]}, "name": "{zone["name"]}"}}{comma}'
    )
print("]")

# 통계 정보 출력
print(f"\n=== 통계 정보 ===")
print(f"총 지역 수: {len(RISK_ZONES)}")
print(f"위험도 0.8 이상인 지역: {len([r for r in risks if r >= 0.8])}개")
print(f"위험도 0.5-0.8인 지역: {len([r for r in risks if 0.5 <= r < 0.8])}개")
print(f"위험도 0.5 미만인 지역: {len([r for r in risks if r < 0.5])}개")

# 가장 위험한 상위 10개 지역
print(f"\n=== 가장 위험한 상위 10개 지역 ===")
sorted_zones = sorted(RISK_ZONES, key=lambda x: x["risk"], reverse=True)
for i, zone in enumerate(sorted_zones[:10]):
    print(f"{i+1:2d}. {zone['name']:<20} - 위험도: {zone['risk']}")
