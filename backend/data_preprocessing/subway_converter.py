# subway_converter.py - integrate.py용 간소화 버전
import pandas as pd


def convert_subway_to_analysis_locations(csv_file, limit=None, silent=True):
    """
    지하철역 CSV를 analysis_locations 딕셔너리 형태로 변환 (간소화 버전)

    Parameters:
    csv_file (str): 지하철역 CSV 파일 경로
    limit (int): 출력할 역 개수 제한 (None이면 전체)
    silent (bool): True면 출력 메시지 최소화

    Returns:
    list: analysis_locations 형태의 결과
    """

    if not silent:
        print("🚇 지하철역 데이터 로드 중...")

    try:
        # CSV 파일 읽기 (인코딩 자동 처리)
        try:
            df = pd.read_csv(csv_file, encoding="utf-8")
        except UnicodeDecodeError:
            df = pd.read_csv(csv_file, encoding="cp949")

        # 필수 컬럼 확인
        required_columns = ["위도", "경도", "역명"]
        if not all(col in df.columns for col in required_columns):
            if not silent:
                print("❌ 필수 컬럼 없음, 빈 리스트 반환")
            return []

        # 서울시 좌표 범위 필터링
        seoul_bounds = {
            "lat_min": 37.4,
            "lat_max": 37.7,
            "lng_min": 126.7,
            "lng_max": 127.2,
        }

        df_seoul = df[
            (df["위도"] >= seoul_bounds["lat_min"])
            & (df["위도"] <= seoul_bounds["lat_max"])
            & (df["경도"] >= seoul_bounds["lng_min"])
            & (df["경도"] <= seoul_bounds["lng_max"])
        ].copy()

        # 중복 제거 및 정렬
        df_clean = df_seoul.drop_duplicates(subset=["역명"]).reset_index(drop=True)
        df_clean = df_clean.sort_values("역명").reset_index(drop=True)

        # 개수 제한
        if limit and limit < len(df_clean):
            df_clean = df_clean.head(limit)

        # analysis_locations 형태로 변환
        analysis_locations = []
        for _, row in df_clean.iterrows():
            analysis_locations.append(
                {
                    "name": row["역명"],
                    "lat": float(row["위도"]),
                    "lng": float(row["경도"]),
                }
            )

        if not silent:
            print("✅ {}개 지하철역 로드 완료".format(len(analysis_locations)))

        return analysis_locations

    except Exception as e:
        if not silent:
            print("❌ 지하철역 로드 실패: {}".format(e))
        return []


def get_default_analysis_locations():
    """기본 분석 위치 반환"""
    return [
        {"name": "서울시청", "lat": 37.5665, "lng": 126.9780},
        {"name": "강남구청", "lat": 37.5173, "lng": 127.0473},
        {"name": "서대문구청", "lat": 37.5985, "lng": 126.9316},
        {"name": "송파구청", "lat": 37.5145, "lng": 127.1066},
        {"name": "마포구청", "lat": 37.5663, "lng": 126.9019},
        {"name": "홍대입구역", "lat": 37.5572, "lng": 126.9245},
        {"name": "강남역", "lat": 37.4979, "lng": 127.0276},
        {"name": "종로3가역", "lat": 37.5704, "lng": 126.9922},
        {"name": "잠실역", "lat": 37.5133, "lng": 127.1000},
        {"name": "신촌역", "lat": 37.5559, "lng": 126.9369},
        {"name": "을지로입구역", "lat": 37.5663, "lng": 126.9819},
        {"name": "동대문역", "lat": 37.5714, "lng": 127.0094},
    ]


def get_priority_subway_stations():
    """우선순위 높은 지하철역 반환"""
    return [
        {"name": "강남역", "lat": 37.4979, "lng": 127.0276},
        {"name": "홍대입구역", "lat": 37.5572, "lng": 126.9245},
        {"name": "신촌역", "lat": 37.5559, "lng": 126.9369},
        {"name": "종로3가역", "lat": 37.5704, "lng": 126.9922},
        {"name": "을지로입구역", "lat": 37.5663, "lng": 126.9819},
        {"name": "동대문역", "lat": 37.5714, "lng": 127.0094},
        {"name": "잠실역", "lat": 37.5133, "lng": 127.1000},
        {"name": "고속터미널역", "lat": 37.5045, "lng": 127.0044},
        {"name": "교대역", "lat": 37.4932, "lng": 127.0140},
        {"name": "사당역", "lat": 37.4766, "lng": 126.9816},
        {"name": "명동역", "lat": 37.5636, "lng": 126.9835},
        {"name": "이태원역", "lat": 37.5344, "lng": 126.9942},
        {"name": "건대입구역", "lat": 37.5403, "lng": 127.0698},
        {"name": "신림역", "lat": 37.4843, "lng": 126.9299},
        {"name": "서울역", "lat": 37.5547, "lng": 126.9707},
        {"name": "영등포구청역", "lat": 37.5259, "lng": 126.8956},
        {"name": "왕십리역", "lat": 37.5610, "lng": 127.0378},
        {"name": "노원역", "lat": 37.6542, "lng": 127.0616},
        {"name": "신도림역", "lat": 37.5089, "lng": 126.8912},
        {"name": "구로역", "lat": 37.5033, "lng": 126.8817},
    ]


def load_analysis_locations(
    mode="subway", subway_csv="seoul_subway_stations.csv", limit=100, silent=True
):
    """
    분석 위치 로드 (integrate.py에서 사용)

    Parameters:
    mode (str): 'default', 'subway', 'priority', 'mixed'
    subway_csv (str): 지하철역 CSV 파일 경로
    limit (int): 지하철역 개수 제한
    silent (bool): 출력 메시지 최소화

    Returns:
    list: analysis_locations
    """

    if mode == "default":
        return get_default_analysis_locations()

    elif mode == "priority":
        return get_priority_subway_stations()

    elif mode == "subway":
        subway_locations = convert_subway_to_analysis_locations(
            subway_csv, limit=limit, silent=silent
        )
        if len(subway_locations) > 0:
            return subway_locations
        else:
            if not silent:
                print("⚠️ 지하철역 로드 실패, 기본 위치 사용")
            return get_default_analysis_locations()

    elif mode == "mixed":
        # 우선순위 역 + 추가 지하철역
        priority_locations = get_priority_subway_stations()

        additional_subway = convert_subway_to_analysis_locations(
            subway_csv, limit=limit // 2, silent=silent
        )

        # 중복 제거
        existing_names = {loc["name"] for loc in priority_locations}
        for subway_loc in additional_subway:
            if subway_loc["name"] not in existing_names:
                priority_locations.append(subway_loc)
                existing_names.add(subway_loc["name"])

                if len(priority_locations) >= limit:
                    break

        return priority_locations[:limit] if limit else priority_locations

    else:
        if not silent:
            print("❌ 알 수 없는 모드: {}, 기본 위치 사용".format(mode))
        return get_default_analysis_locations()


# integrate.py에서 바로 사용할 수 있는 함수
def get_analysis_locations_for_integrate(
    use_subway=True,
    subway_csv="seoul_subway_stations.csv",
    station_count=200,
    fallback_mode="priority",
):
    """
    integrate.py에서 직접 호출하는 간편 함수

    Parameters:
    use_subway (bool): True면 지하철역 사용, False면 기본 위치
    subway_csv (str): 지하철역 CSV 파일 경로
    station_count (int): 지하철역 개수
    fallback_mode (str): 실패시 대체 모드 ('priority' 또는 'default')

    Returns:
    list: analysis_locations
    """

    if not use_subway:
        return get_default_analysis_locations()

    # 지하철역 시도
    subway_locations = convert_subway_to_analysis_locations(
        subway_csv, limit=station_count, silent=True
    )

    if len(subway_locations) > 0:
        return subway_locations

    # 실패시 대체
    if fallback_mode == "priority":
        return get_priority_subway_stations()
    else:
        return get_default_analysis_locations()
