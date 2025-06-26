"""
서울시 200m 단위 그리드 위치 생성기
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import os


def create_seoul_200m_grid():
    """서울시를 200m 단위로 그리드 분할하여 위치 리스트 생성"""

    print("🗺️ 서울시 200m 그리드 생성 시작...")

    # 서울시 경계 좌표 (보다 정확한 범위)
    seoul_bounds = {
        "lat_min": 37.428,  # 서울 최남단 (서초구 남부)
        "lat_max": 37.701,  # 서울 최북단 (도봉구 북부)
        "lng_min": 126.764,  # 서울 최서단 (강서구 서부)
        "lng_max": 127.184,  # 서울 최동단 (강동구 동부)
    }

    # 200m를 위도/경도로 변환 (한국 기준 근사치)
    # 위도 1도 ≈ 111km, 경도 1도 ≈ 88km (서울 위도 기준)
    lat_step = 0.2 / 111.0  # 200m를 위도로 변환 ≈ 0.0018도
    lng_step = 0.2 / 88.0  # 200m를 경도로 변환 ≈ 0.0023도

    print(f"📏 그리드 간격: 위도 {lat_step:.4f}도, 경도 {lng_step:.4f}도")

    analysis_locations = []
    grid_count = 0

    # 위도를 기준으로 남쪽부터 북쪽으로 스캔
    current_lat = seoul_bounds["lat_min"]

    while current_lat <= seoul_bounds["lat_max"]:
        # 경도를 기준으로 서쪽부터 동쪽으로 스캔
        current_lng = seoul_bounds["lng_min"]

        while current_lng <= seoul_bounds["lng_max"]:
            grid_count += 1

            # 그리드 포인트 생성
            location = {
                "name": f"G_{grid_count:04d}",
                "lat": round(current_lat, 4),
                "lng": round(current_lng, 4),
            }

            analysis_locations.append(location)

            # 다음 경도로 이동
            current_lng += lng_step

        # 다음 위도로 이동
        current_lat += lat_step

    print(f"✅ 총 {len(analysis_locations)}개 그리드 포인트 생성")
    print(f"📊 그리드 범위:")
    print(f"   위도: {seoul_bounds['lat_min']:.3f} ~ {seoul_bounds['lat_max']:.3f}")
    print(f"   경도: {seoul_bounds['lng_min']:.3f} ~ {seoul_bounds['lng_max']:.3f}")

    return analysis_locations


def validate_grid_coverage(analysis_locations):
    """생성된 그리드의 커버리지 검증"""
    print("\n🔍 그리드 커버리지 검증...")

    if not analysis_locations:
        print("❌ 생성된 그리드가 없습니다.")
        return

    # 위도/경도 범위 추출
    lats = [loc["lat"] for loc in analysis_locations]
    lngs = [loc["lng"] for loc in analysis_locations]

    print(f"📍 실제 생성 범위:")
    print(f"   위도: {min(lats):.4f} ~ {max(lats):.4f}")
    print(f"   경도: {min(lngs):.4f} ~ {max(lngs):.4f}")

    # 그리드 밀도 계산
    lat_range = max(lats) - min(lats)
    lng_range = max(lngs) - min(lngs)
    area_km2 = lat_range * 111 * lng_range * 88  # 대략적인 면적
    density = len(analysis_locations) / area_km2

    print(f"📏 커버 면적: 약 {area_km2:.1f} km²")
    print(f"🎯 그리드 밀도: {density:.1f} 포인트/km²")

    # 예상 서울시 면적과 비교
    seoul_area = 605.21  # 서울시 실제 면적 (km²)
    expected_points = seoul_area * 25  # 200m 그리드 시 1km²당 25개 포인트
    print(f"🏙️ 서울시 면적: {seoul_area} km²")
    print(f"📈 예상 포인트 수: 약 {expected_points:.0f}개")
    print(f"📊 실제 생성률: {len(analysis_locations)/expected_points*100:.1f}%")


def save_grid_to_csv(analysis_locations, filename="seoul_200m_grid.csv"):
    """그리드 데이터를 CSV 파일로 저장"""
    print(f"\n💾 그리드 데이터를 {filename}에 저장 중...")

    # DataFrame 생성
    df = pd.DataFrame(analysis_locations)

    # 추가 정보 컬럼 생성
    df["grid_id"] = df["name"]
    df["grid_size_m"] = 200
    df["created_date"] = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")

    # CSV 저장
    os.makedirs("output", exist_ok=True)
    output_path = f"output/{filename}"
    df.to_csv(output_path, index=False, encoding="utf-8")

    print(f"✅ 파일 저장 완료: {output_path}")
    print(f"📁 파일 크기: {len(df)} 행 × {len(df.columns)} 열")

    # 샘플 데이터 표시
    print(f"\n📋 샘플 데이터 (상위 10개):")
    print(df[["name", "lat", "lng"]].head(10).to_string(index=False))

    return output_path


def visualize_grid(analysis_locations, sample_size=1000):
    """그리드 분포 시각화 (샘플링)"""
    print(f"\n📊 그리드 분포 시각화 (샘플 {sample_size}개)...")

    # 너무 많으면 샘플링
    if len(analysis_locations) > sample_size:
        import random

        sample_locations = random.sample(analysis_locations, sample_size)
        print(f"   전체 {len(analysis_locations)}개 중 {sample_size}개 샘플링")
    else:
        sample_locations = analysis_locations

    # 좌표 추출
    lats = [loc["lat"] for loc in sample_locations]
    lngs = [loc["lng"] for loc in sample_locations]

    # 시각화
    plt.figure(figsize=(12, 10))
    plt.scatter(lngs, lats, s=1, alpha=0.6, c="blue")
    plt.xlabel("경도 (Longitude)")
    plt.ylabel("위도 (Latitude)")
    plt.title(
        f"서울시 200m 그리드 분포\n(총 {len(analysis_locations)}개 포인트 중 {len(sample_locations)}개 표시)"
    )
    plt.grid(True, alpha=0.3)

    # 서울시 경계 표시
    seoul_bounds = {
        "lat_min": 37.428,
        "lat_max": 37.701,
        "lng_min": 126.764,
        "lng_max": 127.184,
    }
    plt.axhline(
        y=seoul_bounds["lat_min"],
        color="red",
        linestyle="--",
        alpha=0.5,
        label="서울시 경계",
    )
    plt.axhline(y=seoul_bounds["lat_max"], color="red", linestyle="--", alpha=0.5)
    plt.axvline(x=seoul_bounds["lng_min"], color="red", linestyle="--", alpha=0.5)
    plt.axvline(x=seoul_bounds["lng_max"], color="red", linestyle="--", alpha=0.5)

    plt.legend()
    plt.tight_layout()

    # 저장
    os.makedirs("output", exist_ok=True)
    plt.savefig("output/seoul_grid_visualization.png", dpi=300, bbox_inches="tight")
    print("✅ 시각화 저장: output/seoul_grid_visualization.png")
    plt.show()


def create_analysis_locations_code(analysis_locations, max_display=20):
    """analysis_locations 변수 형태의 코드 생성"""
    print(f"\n🔧 analysis_locations 코드 생성...")

    code_lines = ["analysis_locations = ["]

    # 표시할 개수 제한
    # display_count = min(len(analysis_locations), max_display)

    # for i, location in enumerate(analysis_locations[:display_count]):
    for i, location in enumerate(analysis_locations):
        line = f'    {{"name": "{location["name"]}", "lat": {location["lat"]}, "lng": {location["lng"]}}},'
        code_lines.append(line)

    if len(analysis_locations) > max_display:
        code_lines.append(f"    # ... 총 {len(analysis_locations)}개 위치")
        code_lines.append(f"    # (표시된 것: {max_display}개)")

    code_lines.append("]")

    code_string = "\n".join(code_lines)

    # 파일로 저장
    os.makedirs("output", exist_ok=True)
    with open("output/analysis_locations_code.py", "w", encoding="utf-8") as f:
        f.write("# 서울시 200m 그리드 analysis_locations\n")
        f.write("# 자동 생성된 코드\n\n")
        f.write(code_string)
        f.write(f"\n\nprint(f'총 {{len(analysis_locations)}}개 그리드 위치 로드 완료')")

    print(f"✅ 코드 파일 저장: output/analysis_locations_code.py")
    print(f"\n📝 사용 방법:")
    print(f"   1. output/analysis_locations_code.py 파일 내용을 복사")
    print(f"   2. 기존 코드의 analysis_locations 부분에 붙여넣기")

    return code_string


def filter_grid_by_districts(analysis_locations, target_districts=None):
    """특정 구만 선택하여 그리드 필터링 (선택사항)"""
    if target_districts is None:
        target_districts = ["강남구", "서초구", "송파구", "강동구"]  # 강남권 예시

    print(f"\n🎯 특정 구 필터링: {target_districts}")
    print("   (이 기능은 구 경계 데이터가 있을 때 사용 가능)")

    # 실제 구 경계 필터링은 복잡하므로 여기서는 스킵
    # 필요시 구 경계 좌표 데이터를 활용하여 구현 가능

    return analysis_locations


def main():
    """메인 실행 함수"""
    print("🚀 서울시 200m 그리드 생성기 시작\n")

    # 1. 그리드 생성
    analysis_locations = create_seoul_200m_grid()

    # 2. 검증
    validate_grid_coverage(analysis_locations)

    # 3. CSV 저장
    csv_path = save_grid_to_csv(analysis_locations)

    # 4. 시각화
    try:
        visualize_grid(analysis_locations)
    except Exception as e:
        print(f"⚠️ 시각화 실패: {e}")

    # 5. 코드 생성
    code_string = create_analysis_locations_code(analysis_locations)

    # 6. 요약 정보
    print(f"\n🎉 그리드 생성 완료!")
    print(f"   📍 총 포인트 수: {len(analysis_locations)}개")
    print(f"   📏 그리드 간격: 200m")
    print(f"   💾 저장 위치: output/ 폴더")
    print(f"   🔧 사용 준비: analysis_locations 변수 형태로 생성됨")

    # 7. 샘플 코드 출력
    print(f"\n📋 샘플 analysis_locations (처음 5개):")
    for i, location in enumerate(analysis_locations[:5]):
        print(f"   {location}")

    print(f"\n💡 다음 단계:")
    print(f"   1. output/analysis_locations_code.py 파일 확인")
    print(f"   2. 기존 코드에서 analysis_locations 부분 교체")
    print(f"   3. radius = 0.1 (100m)로 설정 권장 (그리드가 촘촘하므로)")

    return analysis_locations


if __name__ == "__main__":
    # 실행
    grid_locations = main()

    # 추가: 기존 코드에 바로 사용할 수 있는 변수 생성
    analysis_locations = grid_locations
    print(f"\n✅ analysis_locations 변수 준비 완료: {len(analysis_locations)}개 위치")
