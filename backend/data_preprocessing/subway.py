import pandas as pd


def filter_seoul_subway_data(input_file, output_file):
    """
    서울시 지하철 데이터를 필터링하고 필요한 컬럼만 추출하는 함수

    Parameters:
    input_file (str): 입력 CSV 파일 경로
    output_file (str): 출력 CSV 파일 경로
    """

    # 1. 데이터 읽기
    df = pd.read_csv(input_file, encoding="utf-8")
    print(f"원본 데이터: {len(df)}행")

    # 2. 서울시 자치구 목록 정의
    seoul_districts = [
        "종로구",
        "중구",
        "용산구",
        "성동구",
        "광진구",
        "동대문구",
        "중랑구",
        "성북구",
        "강북구",
        "도봉구",
        "노원구",
        "은평구",
        "서대문구",
        "마포구",
        "양천구",
        "강서구",
        "구로구",
        "금천구",
        "영등포구",
        "동작구",
        "관악구",
        "서초구",
        "강남구",
        "송파구",
        "강동구",
    ]

    # 3. 서울시 자치구 데이터만 필터링
    seoul_df = df[df["자치구"].isin(seoul_districts)].copy()
    print(f"서울시 필터링 후: {len(seoul_df)}행")

    # 4. 필요한 컬럼만 선택 (위도, 경도, 역명)
    result_df = seoul_df[["위도", "경도", "역명"]].copy()

    # 5. 중복 제거 (같은 역이 여러 날짜에 있을 수 있음)
    result_df = result_df.drop_duplicates().reset_index(drop=True)
    print(f"중복 제거 후: {len(result_df)}행")

    # 6. 역명 정리 (필요시)
    # 역명에서 "역" 제거 여부 선택 가능
    # result_df['역명'] = result_df['역명'].str.replace('역', '', regex=False)

    # 7. 결과 저장
    result_df.to_csv(output_file, index=False, encoding="utf-8-sig")
    print(f"결과 저장: {output_file}")

    # 8. 결과 미리보기
    print("\n=== 결과 미리보기 ===")
    print(result_df.head(10))

    # 9. 기본 통계
    print(f"\n=== 기본 통계 ===")
    print(f"총 지하철역 수: {len(result_df)}")
    print(f"위도 범위: {result_df['위도'].min():.4f} ~ {result_df['위도'].max():.4f}")
    print(f"경도 범위: {result_df['경도'].min():.4f} ~ {result_df['경도'].max():.4f}")

    return result_df


# 사용 예시
if __name__ == "__main__":
    # 파일 경로 설정
    input_file = "data/지하철유동인구수.csv"  # 입력 파일명
    output_file = "seoul_subway_stations.csv"  # 출력 파일명

    # 데이터 처리 실행
    try:
        filtered_data = filter_seoul_subway_data(input_file, output_file)
        print("처리 완료!")

    except FileNotFoundError:
        print(f"파일을 찾을 수 없습니다: {input_file}")
        print("파일 경로를 확인해주세요.")
    except Exception as e:
        print(f"오류 발생: {e}")


# 추가 기능: 자치구별 역 수 확인
def analyze_district_stations(df):
    """자치구별 지하철역 분포 분석"""

    # 원본 데이터에서 서울시만 필터링
    seoul_districts = [
        "종로구",
        "중구",
        "용산구",
        "성동구",
        "광진구",
        "동대문구",
        "중랑구",
        "성북구",
        "강북구",
        "도봉구",
        "노원구",
        "은평구",
        "서대문구",
        "마포구",
        "양천구",
        "강서구",
        "구로구",
        "금천구",
        "영등포구",
        "동작구",
        "관악구",
        "서초구",
        "강남구",
        "송파구",
        "강동구",
    ]

    seoul_df = df[df["자치구"].isin(seoul_districts)]
    district_count = (
        seoul_df.groupby("자치구")["역명"].nunique().sort_values(ascending=False)
    )

    print("\n=== 자치구별 지하철역 수 ===")
    for district, count in district_count.items():
        print(f"{district}: {count}개")

    return district_count


# 좌표 유효성 검증 함수
def validate_coordinates(df):
    """좌표 데이터 유효성 검증"""

    # 서울시 대략적 좌표 범위
    seoul_lat_min, seoul_lat_max = 37.4, 37.7
    seoul_lng_min, seoul_lng_max = 126.7, 127.2

    # 범위 벗어난 데이터 확인
    invalid_data = df[
        (df["위도"] < seoul_lat_min)
        | (df["위도"] > seoul_lat_max)
        | (df["경도"] < seoul_lng_min)
        | (df["경도"] > seoul_lng_max)
    ]

    if len(invalid_data) > 0:
        print(f"\n⚠️  좌표 범위를 벗어난 데이터 {len(invalid_data)}개 발견:")
        print(invalid_data)
    else:
        print("\n✅ 모든 좌표가 서울시 범위 내에 있습니다.")

    return invalid_data
