# 🌙 TheMoon - 실시간 개인화 뉴스 피드 & RAG 챗봇

> 여러 언론사의 뉴스를 실시간으로 수집하고, 사용자 관심사에 맞게 개인화된 피드를 제공하며, RAG 기반 챗봇으로 뉴스에 대해 대화할 수 있는 서비스

---

## 📌 프로젝트 소개

### 만든 이유
매일 쏟아지는 뉴스를 여러 사이트를 돌아다니며 확인하는 것은 비효율적입니다. 같은 사건을 다루는 기사가 언론사마다 중복으로 노출되고, 관심 없는 분야의 기사까지 모두 봐야 하는 문제가 있습니다.

**TheMoon**은 이 문제를 해결하기 위해:
- 여러 언론사 RSS를 자동으로 수집하고 중복 기사를 제거
- 사용자의 카테고리 관심도에 따라 개인화된 피드 제공
- 뉴스 내용을 벡터화하여 RAG 챗봇으로 질문에 답변

### 주요 특징
- **완전 자동화**: Airflow가 30분마다 RSS를 수집하고, Spark가 1시간마다 임베딩 파이프라인 실행
- **실시간성**: SSE(Server-Sent Events)로 새 기사를 클라이언트에 푸시
- **개인화**: 카테고리별 가중치(1~10)를 기반으로 추천 비율 동적 조정
- **RAG 챗봇**: pgvector 코사인 유사도 검색 + Gemini 2.5 Flash 답변 생성

---

## ✨ 주요 기능

### 1. 실시간 뉴스 피드 (SSE)
- Airflow DAG가 연합뉴스, 매일경제, SBS, 한국경제, 경향신문 등 12개 RSS 피드를 30분마다 수집
- 새 기사 발생 시 SSE로 클라이언트에 실시간 푸시
- 무한 스크롤 + 카테고리(정치/경제/사회) 필터

### 2. 개인화 추천
- 회원가입 시 카테고리별 관심도(1~10) 설정
- 가중치 비율에 따라 카테고리별 기사 수 동적 배분
  - 예: 경제 9, 정치 6, 사회 3 → 경제 50%, 정치 33%, 사회 17%
- 더보기 / 새로고침 (이미 본 기사 제외)
- 마이페이지에서 관심도 변경 시 즉시 반영

### 3. Apache Spark 임베딩 파이프라인
- `is_processed=false` 기사를 article_id 범위로 파티션 분할하여 병렬 처리
- Worker 프로세스 내 모델 전역 캐싱으로 반복 로드 제거
- 한국어 임베딩 모델 `jhgan/ko-sroberta-multitask` (768차원)

**벤치마크 결과 (5,000건 / 6,557청크 기준)**

| 환경 | 소요 시간 |
|------|----------|
| 순수 Python (단일 프로세스) | 316초 (5.3분) |
| Spark Worker 1개 (파티션 1개) | 769초 (12.8분) |
| Spark Worker 3개 (파티션 1개) | 559초 (9.3분) |
| **Spark Worker 3개 (파티션 6개 + 모델 캐싱)** | **291초 (4.9분)** |

> 파티션을 article_id 범위로 분할하고 Worker 프로세스 내 모델을 캐싱한 결과, 순수 Python 대비 **약 8% 성능 향상**을 달성했습니다. Worker를 추가할수록 선형적으로 처리량이 증가하는 수평 확장 구조입니다.

### 4. RAG 챗봇 (Retrieval-Augmented Generation)
- 사용자 질문을 동일 임베딩 모델로 벡터화
- pgvector 코사인 유사도 검색 + 개인화 스코어링
  ```
  최종 점수 = 유사도 × 0.7 + 카테고리 가중치 × 0.2 + 최신성 × 0.1
  ```
- 검색된 청크를 컨텍스트로 Gemini 2.5 Flash에 전달하여 답변 생성
- 슬라이딩 윈도우 방식 대화 히스토리 (최근 6턴)
- 출처 링크 표시, 날짜별 대화 내역 조회

### 5. 중복 기사 감지
- Spark로 24시간 이내 기사의 대표 청크 임베딩 추출
- 카테고리 내 + 다른 언론사 간 코사인 유사도 비교 (임계값 0.75)
- 중복 감지 시 `is_duplicate=true`, `representative_id` 설정
- "지금 화제" 섹션에서 여러 언론사 보도 기사 통합 표시

### 6. Airflow 자동화 파이프라인
```
RSS 수집 DAGs (30분마다)          Spark 파이프라인 DAG (1시간마다)
├── yna_collect (연합뉴스)    →   ├── check_unprocessed_count
├── mk_collect  (매일경제)    →   ├── embedding_job (청킹 + 임베딩)
└── sbs_collect (SBS)        →   └── dedup_job (중복 감지)
```

---

## 🏗️ 시스템 아키텍처

```
┌─────────────────────────────────────────────────────────────┐
│                        Frontend (React)                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │ 개인화피드│  │ 지금화제 │  │ 최신뉴스 │  │ RAG챗봇  │   │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘   │
└───────┼─────────────┼──────────────┼──────────────┼─────────┘
        │             │              │              │
        ▼             ▼              ▼              ▼
┌─────────────────────────────────────────────────────────────┐
│                    FastAPI Backend                           │
│  /feed/recommended  /feed/trending  /feed/articles  /chat   │
└───────────────────────────┬─────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                   ▼
┌──────────────┐   ┌──────────────┐   ┌──────────────────┐
│  PostgreSQL  │   │   pgvector   │   │  Gemini 2.5 Flash │
│  (뉴스 DB)   │   │ (벡터 검색)  │   │  (답변 생성)      │
└──────────────┘   └──────────────┘   └──────────────────┘
        ▲
        │
┌───────┴──────────────────────────────────────────────────┐
│                  데이터 파이프라인                         │
│                                                           │
│  Airflow (RSS 수집) ──▶ articles 테이블                   │
│                              │                            │
│  Spark (임베딩 생성) ◀───────┘                            │
│       │                                                   │
│       └──▶ article_chunks (벡터) + is_processed=true      │
│                                                           │
│  Spark (중복 감지) ──▶ is_duplicate=true + representative │
└──────────────────────────────────────────────────────────┘
```

---

## 🤔 왜 이 기술들을 선택했나?

### Apache Spark — 왜 단순 스크립트 대신?

뉴스 임베딩 파이프라인은 단순히 "지금 작동하면 된다"가 아니라 **미래 확장성**을 고려해야 합니다.

**문제 상황:**
- 현재 12개 RSS 피드에서 30분마다 기사 수집
- 언론사를 50개로 늘리면 하루 수천~수만 건의 기사 처리 필요
- 임베딩 생성은 CPU/메모리 집약적 작업 → 단일 프로세스로는 병목 발생

**Spark를 선택한 이유:**
```
단순 Python 스크립트        Apache Spark
─────────────────           ─────────────────
단일 프로세스               분산 병렬 처리
스케일업만 가능             스케일아웃 가능 (Worker 추가)
실패 시 전체 재처리         파티션 단위 재처리
모니터링 어려움             Web UI + 상세 실행 로그
```

**핵심 설계 결정 — article_id 기반 파티션 분할:**
```python
# ❌ 잘못된 방식: subquery → 파티션 1개 → Worker 1개만 동작
articles_df = spark.read.jdbc(url, table="(SELECT ... LIMIT 5000) AS t", ...)

# ✅ 올바른 방식: article_id 범위 분할 → 진짜 병렬 처리
articles_df = spark.read.jdbc(
    url, table="...",
    column="article_id",
    lowerBound=min_id, upperBound=max_id,
    numPartitions=6,   # Worker 3개 × Core 2개
    ...
)
```

**실측 결과:** Worker 3개, 파티션 6개, 모델 캐싱 적용 시 **Python 단일 프로세스 대비 8% 빠름**, Worker 추가 시 선형적으로 성능 향상

---

### Apache Airflow — 왜 단순 Cron 대신?

뉴스 수집은 단순한 반복 작업처럼 보이지만 실제로는 복잡한 의존성이 있습니다.

**Cron의 한계:**
```bash
# Cron으로 하면 이렇게 됨
*/30 * * * * python collect_rss.py   # 수집
0 * * * *    python embedding.py     # 임베딩 (수집 완료 여부 모름)
0 * * * *    python dedup.py         # 중복 감지 (임베딩 완료 여부 모름)
```
- 이전 단계 실패 여부를 다음 단계가 알 수 없음
- 실패 시 재시도 로직 직접 구현 필요
- 어떤 DAG Run이 성공/실패했는지 추적 불가

**Airflow를 선택한 이유:**
```
RSS 수집 DAG (30분)          Spark 파이프라인 DAG (1시간)
┌─────────────┐              ┌──────────────────────┐
│ collect_    │              │ check_unprocessed    │
│ politics    │──────────▶  │         ↓            │
│ collect_    │    성공 시만  │ run_embedding_job    │
│ economy     │   다음 실행  │         ↓            │
└─────────────┘              │ run_dedup_job        │
                             │         ↓            │
                             │ notify_result        │
                             └──────────────────────┘
```
- DAG 단위 의존성 관리
- 자동 재시도 (retries=1, retry_delay=10분)
- Web UI에서 실행 이력, 로그, 성공/실패 한눈에 확인
- 미처리 기사가 없으면 Spark 기동 자체를 스킵 (불필요한 리소스 낭비 방지)

---

### jhgan/ko-sroberta-multitask — 왜 이 임베딩 모델?

RAG 시스템의 핵심은 **검색 품질**입니다. 임베딩 모델 선택이 검색 정확도를 결정합니다.

**후보 모델 비교:**

| 모델 | 언어 | 차원 | 한국어 성능 | 속도 |
|------|------|------|------------|------|
| text-embedding-ada-002 (OpenAI) | 다국어 | 1536 | 보통 | API 지연 |
| multilingual-e5-large | 다국어 | 1024 | 양호 | 느림 |
| **jhgan/ko-sroberta-multitask** | **한국어 특화** | **768** | **우수** | **빠름** |
| KoSimCSE-roberta | 한국어 특화 | 768 | 우수 | 빠름 |

**jhgan/ko-sroberta-multitask를 선택한 이유:**
1. **한국어 뉴스 특화**: 한국어 문장 유사도 태스크로 파인튜닝됨
2. **적절한 차원(768)**: OpenAI 1536차원 대비 저장 공간 절반, 검색 속도 향상
3. **로컬 실행**: API 호출 없이 컨테이너 내부에서 실행 → 비용 없음, 레이턴시 없음
4. **FastAPI와 Spark 동일 모델 사용**: 임베딩 공간 일관성 보장 (다른 모델 쓰면 검색 품질 급락)

> **중요**: 인덱싱(Spark)과 검색(FastAPI) 시 **반드시 동일한 모델**을 써야 합니다. 모델이 다르면 벡터 공간이 달라져 유사도 계산이 무의미해집니다.

---

## 🛠️ 기술 스택

### Backend
| 기술 | 선택 이유 |
|------|----------|
| **FastAPI** | 비동기 지원, SSE 스트리밍, 자동 API 문서화 |
| **PostgreSQL + pgvector** | 관계형 DB와 벡터 검색을 단일 DB로 통합, 추가 벡터 DB 불필요 |
| **Apache Spark** | 수평 확장 가능한 분산 임베딩 파이프라인 구성 |
| **Apache Airflow** | DAG 기반 파이프라인 스케줄링 및 모니터링 |
| **Gemini 2.5 Flash** | 빠른 응답속도, 한국어 성능 우수 |
| **jhgan/ko-sroberta-multitask** | 한국어 특화 문장 임베딩 모델 (768차원) |

### Frontend
| 기술 | 선택 이유 |
|------|----------|
| **React** | 컴포넌트 재사용, 상태 관리 용이 |
| **SSE (EventSource)** | 단방향 서버 푸시에 WebSocket보다 가벼움 |
| **Axios** | 인터셉터로 JWT 토큰 자동 주입 |

### Infrastructure
| 기술 | 선택 이유 |
|------|----------|
| **Docker Compose** | 전체 스택 단일 명령으로 실행 |
| **SQLite (Airflow)** | 단일 노드 환경에서 간편한 Airflow 메타 DB |

---

## 🗄️ DB 스키마

```sql
articles          -- 수집된 뉴스 기사 (is_processed, is_duplicate)
article_chunks    -- 청킹된 텍스트 + 768차원 임베딩 벡터
categories        -- 정치/경제/사회
news_sources      -- RSS 피드 URL 관리
users             -- 회원 정보
user_category_prefs -- 카테고리별 관심도 (1~10)
chat_sessions     -- 챗봇 세션
chat_history      -- 대화 내용
chat_sources      -- 답변 생성에 사용된 기사 출처
```

---

## 🚀 실행 방법

### 사전 요구사항
- Docker Desktop
- Gemini API Key ([Google AI Studio](https://aistudio.google.com/))

### 1. 저장소 클론
```bash
git clone https://github.com/your-username/TheMoon.git
cd TheMoon
```

### 2. 환경변수 설정
```bash
cp .env.example .env
```

`.env` 파일 수정:
```env
POSTGRES_DB=news_rag
POSTGRES_USER=news_user
POSTGRES_PASSWORD=your_password

AIRFLOW_SECRET_KEY=your-secret-key-32-chars-minimum
AIRFLOW_USER=admin
AIRFLOW_PASSWORD=your_airflow_password
AIRFLOW_EMAIL=admin@example.com

GEMINI_API_KEY=your_gemini_api_key
EMBED_MODEL=jhgan/ko-sroberta-multitask

VITE_API_URL=http://localhost:8000
```

### 3. 실행
```bash
docker compose up -d
```

### 4. 서비스 접속
| 서비스 | URL |
|--------|-----|
| 프론트엔드 | http://localhost:5173 |
| FastAPI Docs | http://localhost:8000/docs |
| Airflow UI | http://localhost:8080 |
| Spark UI | http://localhost:8081 |

### 5. 초기 데이터 수집
Airflow UI에서 DAG를 수동 트리거:
1. `yna_collect`, `mk_collect`, `sbs_collect` 실행 (뉴스 수집)
2. `spark_pipeline` 실행 (임베딩 생성 + 중복 감지)

---

## ⚙️ 데이터 파이프라인 상세

### RSS 수집 → 임베딩 → 서비스 흐름
```
1. Airflow RSS DAG (30분마다)
   └── feedparser로 RSS 파싱
   └── articles 테이블 저장 (is_processed=false)

2. Airflow Spark DAG (1시간마다)
   ├── check_unprocessed_count: 미처리 기사 확인
   ├── embedding_job:
   │   ├── article_id 범위로 6개 파티션 분할
   │   ├── 파티션별 Worker에서 병렬 청킹 + 임베딩
   │   └── article_chunks 저장, is_processed=true
   └── dedup_job:
       ├── 24시간 이내 기사 임베딩 로드
       ├── 카테고리 내 다른 언론사 간 유사도 비교
       └── 임계값(0.75) 초과 시 is_duplicate=true

3. FastAPI 피드 API
   └── is_processed=true AND is_duplicate=false 기사만 노출
```

### 청킹 전략
- 문장 단위 분리 (`.!?。` 기준)
- 최대 청크 길이: 200자
- 청크 간 오버랩: 30자 (문맥 연속성 보장)

---

## 🔍 RAG 시스템 상세

### 검색 스코어링 공식
```
최종 점수 = 코사인 유사도 × 0.7
           + 카테고리 가중치(1~10) / 10 × 0.2
           + 기사 최신성(발행시각/현재시각) × 0.1
```
- **유사도 70%**: 질문과 내용 관련성 최우선
- **개인화 20%**: 사용자 관심 카테고리 기사 우선 노출
- **최신성 10%**: 동일 유사도면 최신 기사 우선

### 프롬프트 전략
- System 프롬프트에 검색된 뉴스 청크 컨텍스트 삽입
- 슬라이딩 윈도우로 최근 6턴 대화 히스토리 유지
- 뉴스 내용 외 추측 금지 지시

---

## 🐛 트러블슈팅

### Spark 임베딩 성능 문제
**문제**: Worker 3개를 사용해도 Python 단일 프로세스보다 느림  
**원인**: JDBC subquery로 읽으면 파티션이 1개로 고정되어 Worker 1개만 동작  
**해결**: `column`, `lowerBound`, `upperBound`, `numPartitions` 파라미터로 article_id 범위 분할

### Airflow Task 실패 (JWT 인증 오류)
**문제**: `Invalid auth token: Signature verification failed`  
**원인**: Airflow 3.x에서 컨테이너마다 JWT 시크릿이 랜덤 생성됨  
**해결**: `AIRFLOW__API_AUTH__JWT_SECRET` 환경변수를 모든 컨테이너에 동일하게 설정

### HuggingFace 모델 캐시 권한 오류
**문제**: `PermissionError: /home/spark`  
**원인**: Spark Worker가 `spark` 유저로 실행되는데 홈 디렉토리 없음  
**해결**: `HF_HOME=/tmp/huggingface` 환경변수를 Worker 프로세스 시작 시 설정

### Airflow Task State Mismatch
**문제**: Task가 queued 상태에서 failed로 변경됨  
**원인**: Airflow 3.x + SQLite 조합에서 동시 쓰기 충돌  
**해결**: Airflow 메타 DB를 SQLite → PostgreSQL로 교체

---

## 🔮 향후 발전 방안

| 항목 | 내용 |
|------|------|
| **키워드 선호도** | 카테고리 외 특정 키워드 가중치 추가 |
| **뉴스 요약** | Gemini로 기사 3줄 요약 자동 생성 |
| **감성 분석** | 긍정/부정/중립 감성 태깅 및 필터 |
| **벡터 인덱스** | 데이터 1만건 이상 시 HNSW 인덱스 활성화로 검색 속도 향상 |
| **다국어 지원** | react-i18next 기반 한국어/영어 전환 |
| **모바일 앱** | React Native로 iOS/Android 앱 개발 |
| **알림 기능** | 관심 키워드 기사 발생 시 푸시 알림 |
| **Spark 확장** | 클라우드 환경에서 Worker 수평 확장으로 처리량 선형 증가 |

---

## 📁 프로젝트 구조

```
TheMoon/
├── frontend/                  # React 프론트엔드
│   └── src/
│       ├── pages/Main.jsx     # 메인 피드
│       ├── components/        # ChatBot, NewsCard, MyPage 등
│       ├── api/               # feed.js, chat.js, user.js
│       └── styles/            # CSS 모듈
│
├── backend/
│   ├── api/                   # FastAPI 라우터
│   ├── service/               # 비즈니스 로직
│   ├── repository/            # DB 쿼리
│   ├── rag/                   # 청킹, 임베딩, 챗봇
│   ├── spark/jobs/            # Spark Job (embedding, dedup)
│   ├── airflow/dags/          # Airflow DAG 파일
│   └── scripts/               # 유틸리티 스크립트
│
└── db/
    └── init.sql               # DB 스키마 + 초기 데이터
```

---

## 👤 개발자

| 항목 | 내용 |
|------|------|
| 개발 기간 | 2026년 |
| 개발 인원 | 1인 개발 |
| 기술 문의 | GitHub Issues |