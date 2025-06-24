# 파일 작업 기록로그

### 작업예시

```
### (날짜)
- 작업자 명
    - 커밋prefix : 커밋 메시지
```

### 06/14

- 황선우
  - init: 초기환경 구성

### 06/21

- 황선우
  - Chore: 폴더 구조 및 폴더 이름 수정
- 오병주
  - Chore: 초기 디렉토리 구분 기능ID별 폴더 생성 리액트용 초기 세팅
  - Chore: .gitignore - node_modules 디렉토리 추가
  - Chore: .gitignore - Python 캐시 및 SQLite 데이터베이스 파일 제외 설정 추가
  - Chore: package.json - 프론트엔드 의존성 패키지 설정
  - Chore: requirements.txt - 카카오맵 API 및 경로계산 의존성 추가
  - Chore: manifest.json - PWA 매니페스트 설정
  - Chore: index.html - 앱 메타데이터 및 HTML 구조 설정
  - Chore: database.py - SQLite 데이터베이스 연결 설정
  - Add: main.py - 카카오맵 지명검색 API 엔드포인트 구현
  - Add: main.py - 위험지역 우회 안전경로 계산 알고리즘 구현
  - Add: main.py - 보행자 경로 탐색 API 통합 기능 구현
  - Add: main.py - 싱크홀 위험도 예측 시스템 구현
  - Add: auth.py - JWT 토큰 인증 시스템 구현
  - Add: models.py - 사용자 및 위험도 예측 데이터베이스 모델 정의
  - Add: schemas.py - API 요청/응답 스키마 정의
  - Add: App.js - 퍼블릭 라우팅 시스템 구현
  - Add: index.js - React 앱 초기화 설정
  - Add: Navbar.js - 반응형 네비게이션 헤더 컴포넌트 구현
  - Add: AuthContext.js - JWT 인증 상태 관리 컨텍스트 구현
  - Add: Dashboard.js - 카카오맵 지명검색 기반 위험도 예측 대시보드 구현
  - Add: RiskMap.js - Leaflet 기반 서울시 위험지역 인터랙티브 지도 구현
  - Add: RouteSearch.js - 위험지역 우회 안전경로 검색 시스템 구현
  - Add: Login.js - JWT 기반 사용자 로그인 폼 구현
  - Add: Register.js - 사용자 회원가입 및 유효성 검증 폼 구현
  - Style: App.css - 전역 앱 레이아웃 스타일 설정
  - Style: Navbar.css - 반응형 네비게이션 바 스타일링
  - Style: Auth.css - 로그인/회원가입 폼 스타일링
  - Style: Dashboard.css - 3카드 그리드 대시보드 레이아웃 및 자동완성 UI 스타일링
  - Style: RiskMap.css - 인터랙티브 지도 컨테이너 및 위험도 범례 스타일링
  - Style: RouteSearch.css - 2컬럼 레이아웃 경로검색 UI 스타일링
  - Style: Dashboard - 원형 위험도 점수 표시기 스타일링
  - Style: RiskMap - 위험도별 색상 구분 범례 스타일링
  - Style: RouteSearch - 검색 제안 드롭다운 UI 스타일링

### 06/23

- 오병주
  - Remove: gitkeep 제거
  - Add: 싱크홀 신고정보 가진 rag llm rag에 없는 정보는 일반 llm에 질문
  - Docs: rag 문서 생성
- 전호연
  - Add: OpenAI와 TTS 연동 기능 추가

### 06/24

- 오병주
  - Chore: requirements.txt 업데이트 openai사용에 필요한 라이브러리 추가
  - Style: 신고페이지용 css 추가
  - Add: 신고페이지 화면 추가
  - Add: rag 기능을 사용하는 llm api생성
  - Remove: 필요없어진 gitkeep제거

- 전호연
  - Add: FR-007 Azure Custom Vision으로 이미지 트레이닝 후 개체 감지 테스트