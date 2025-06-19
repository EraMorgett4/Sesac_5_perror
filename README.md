# Sesac_5_perror 프로젝트

> 이 저장소는 데이터 기반 프로젝트의 아이디어 발굴부터 분석, 협업까지의 과정을 관리하기 위한 공간입니다. 초기 아이디어 구상 및 팀 협업을 위한 규칙을 아래와 같이 정리합니다.

---

## 프로젝트 개요

githubwiki(https://github.com/EraMorgett4/Sesac_5_perror/wiki)


---

## 🛠 Git & GitHub 협업 규칙

### 📁 디렉토리 구조

```

/project-root
│
├── data/           # 원본 및 전처리된 데이터
├── docs/           # 회의록, 계획서, 발표자료 등 문서
├── outputs/        # 결과 이미지, 모델 파일 등 산출물
├── src/            # 기능별 Python 코드 모듈
├── log.md          # github 로그 관리리
└── README.md       # 프로젝트 개요 및 가이드

```

---

### 📝 커밋 메시지 작성 규칙

```bash
[태그] 작업 요약: 세부 설명 (선택)
```

| 태그           | 의미         | 예시                              |
| ------------ | ---------- | ------------------------------- |
| `[Add]`      | 기능 추가      | `[Add] 군집 분석 함수 추가`             |
| `[Fix]`      | 버그 수정      | `[Fix] 지도 시각화 좌표 오류 수정`         |
| `[Refactor]` | 구조 개선      | `[Refactor] 전처리 함수 분리`          |
| `[Style]`    | 포맷, 변수명 등  | `[Style] 변수명 일관성 수정`            |
| `[Docs]`     | 문서 작성      | `[Docs] 분석 계획서 업데이트`            |
| `[Test]`     | 테스트 추가     | `[Test] KMeans 클러스터링 유닛 테스트 추가` |
| `[Chore]`    | 설정 등 기타 작업 | `[Chore] requirements.txt 업데이트` |
| `[Remove]`   | 불필요한 코드 제거 | `[Remove] 사용하지 않는 import 제거`    |

---

### 🌿 브랜치 네이밍 규칙

```
prefix/이름/작업내용
```

| prefix      | 설명    | 예시                               |
| ----------- | ----- | -------------------------------- |
| `feature/`  | 기능 개발 | `feature/sunwoo/kmeans-analysis` |
| `fix/`      | 버그 수정 | `fix/sunwoo/missing-data`        |
| `docs/`     | 문서 관련 | `docs/sunwoo/readme-update`      |
| `refactor/` | 구조 개선 | `refactor/sunwoo/preprocessing`  |
| `test/`     | 테스트   | `test/sunwoo/model-eval`         |
| `chore/`    | 설정 작업 | `chore/sunwoo/env-setup`         |

> 모든 작업은 `develop` 브랜치에서 분기하여 Pull Request(PR)로 병합합니다.

---

## 🗂 로그 및 문서 관리 규칙

| 문서 종류   | 위치                     | 내용                     |
| ------- | ---------------------- | ---------------------- |
| 기술 문서   | `/docs/`               | 데이터 설명, 분석 기법, 모델 구조 등 |
| 회의록     | `/docs/backlog/` | 목표 분담표      |
| 발표자료    | `/docs/slides/`        | 중간/최종 발표용 슬라이드         |
| 개인 작업일지 | `/log.md`         | 일자별 진행 내역 기록           |

---

## **반드시 지켜주세요**

1. 작업 후 제때제때 커밋하기
2. 최종 PR을 날릴때, 커밋메시지 종합하여 `log.md`파일에 기록하기
