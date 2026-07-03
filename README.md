# TheMoon - 실시간 개인화 뉴스 피드 & AI 멀티 에이전트 챗봇

> 정보의 홍수 속에서, 나에게 필요한 뉴스만

<div align="center">
<img src="https://github.com/user-attachments/assets/47f0e1a2-2fde-43df-88df-1c3e76311ffe" width="100%"/>
</div>

---

## 프로젝트 소개

<div align="center">
<img src="https://github.com/user-attachments/assets/4d5286a8-fe0f-4571-be12-f9ef781c8f80" width="100%"/>
</div>

### 한 줄 정의

매일 쏟아지는 수만 건의 뉴스를 AI가 관심사에 맞게 골라주고, 궁금한 건 바로 물어볼 수 있는 나만의 뉴스 큐레이션 플랫폼

### 왜 만들었나?

연합뉴스 단독으로 하루 2천여 건의 기사를 생산하고, 국내 수천 개의 언론사가 같은 사건을 반복 보도합니다. 한국언론진흥재단 2024 언론수용자 조사에 따르면 20~30대의 뉴스 이용률이 매년 하락하고 있으며, 포털을 통한 뉴스 이용률도 처음으로 70%대를 밑돌았습니다.

**진짜 문제**
- 같은 사건을 다룬 중복 기사가 넘쳐나 정작 필요한 뉴스를 찾기 어렵다
- 관심 없는 분야의 뉴스까지 모두 봐야 하는 피로감이 쌓인다
- 뉴스를 읽어도 더 깊이 알고 싶을 때 물어볼 곳이 없다

| 문제 | 해결 |
|------|------|
| 하루 수만 건 기사 범람 | Airflow 자동 수집 + 중복 제거 |
| 관심 없는 기사 노출 | 카테고리 가중치 기반 개인화 피드 |
| 뉴스를 찾는 번거로움 | AI 챗봇으로 질문하면 즉시 분석 |

---

## Challenges & Solutions

<div align="center">
<img src="https://github.com/user-attachments/assets/33e6857d-3e36-4d8e-b46b-5ce08135fe0f" width="100%"/>
</div>

### 문제 정의

하나의 AI에게 8가지 도구를 줬더니, 복잡한 질문에서 도구를 아예 쓰지 않고 스스로 답을 지어냈습니다. 분석 질문 정확도 0%, 전체 정확도 62.5% — 뉴스 서비스에서 치명적인 문제였습니다.

### 문제 해결

질문을 먼저 분류하고, 전담 AI가 3~4개 도구만 보도록 역할을 나눴습니다. 각 AI가 무엇을 했는지 LangSmith로 추적해 어디서 틀렸는지 바로 파악할 수 있게 했습니다.

### 결과

분석 정확도 0% → 87.5%, 전체 정확도 62.5% → 87.5%. 질문 유형마다 가장 잘하는 AI가 답하는 구조를 완성했습니다.

| 지표 | 단일 에이전트 | 멀티 에이전트 |
|------|-------------|-------------|
| 전체 정확도 | 62.5% | 87.5%+ |
| 분석 정확도 | 0% | 87.5%+ |
| 평균 답변 길이 | 226자 | 400자+ |
| 카테고리 간 분석 | 불가 | 가능 |

---

## 시스템 아키텍처

<div align="center">
<img src="https://github.com/user-attachments/assets/3fc6a9ca-18bd-474b-a05b-69eb93cbeb8f" width="100%"/>
</div>

### 기술 스택

| 분류 | 기술 |
|------|------|
| Language | Python, JavaScript, CSS |
| Framework | FastAPI 0.136, React 19.1 |
| Database | PostgreSQL 16 + pgvector |
| AI | LangChain, LangGraph, LangSmith, Gemini 2.5 Flash |
| Embedding | jhgan/ko-sroberta-multitask |
| Middleware | Kafka, Redis Stack |
| Infra | Docker Compose, Apache Spark, Airflow |

```
Client (React 19)
    ↓
FastAPI
  ├── 미들웨어 (Cache / Filter / Rate Limiter)
  └── Kafka Producer (FIFO 큐)

Kafka Consumer Worker
    ↓
LangGraph 멀티 에이전트
  ├── Router → RAG / Analysis / Web / Fallback
  └── Summary → Validate → LangSmith

데이터 파이프라인
  ├── Airflow (30분마다 RSS 수집)
  └── Spark (1시간마다 임베딩 + 중복 감지)
```

---

## 챗봇 파이프라인

<div align="center">
<img src="https://github.com/user-attachments/assets/faf1f367-aec8-4362-8a78-b46111af2c2d" width="100%"/>
</div>

### 왜 이 기술들을 선택했나?

**LangChain + LangGraph**
단일 LLM에 8개 도구를 제공했을 때 분석 질문 정확도 62.5%에 그쳤습니다. LangGraph로 Router가 질문을 먼저 분류하고 전담 에이전트가 3~4개 도구만 보도록 구조를 바꿨습니다.

**LangSmith**
AI 시스템은 어디서 왜 틀린 답변이 나왔는지 알기 어렵습니다. LangSmith로 모든 노드의 실행 과정, 토큰 사용량, 소요 시간을 자동 트레이싱해 데이터 기반으로 품질을 관리합니다.

**Kafka**
챗봇 요청 하나당 LLM을 4~5회 호출하며 처리 시간이 30~50초에 달합니다. 동시 사용자 증가 시 서버 다운 위험을 Kafka FIFO 큐로 해결했습니다.

**Apache Spark**
언론사 수를 늘릴수록 임베딩 처리량이 선형으로 증가합니다. Worker를 추가하면 처리량이 선형으로 늘어나는 수평 확장 구조입니다.

---

## 벤치마크 결과

### Spark 임베딩 (5,000건 / 6,557청크 기준)

| 환경 | 소요 시간 |
|------|----------|
| 순수 Python (단일 프로세스) | 316초 (5.3분) |
| Spark Worker 1개 (파티션 1개) | 769초 (12.8분) |
| Spark Worker 3개 (파티션 1개) | 559초 (9.3분) |
| **Spark Worker 3개 (파티션 6개 + 모델 캐싱)** | **291초 (4.9분)** |

---

## 실행 방법

### 사전 요구사항

- Docker Desktop
- Gemini API Key ([Google AI Studio](https://aistudio.google.com/))
- Tavily API Key ([Tavily](https://tavily.com/))
- LangSmith API Key ([LangSmith](https://smith.langchain.com/))

### 1. 저장소 클론

```bash
git clone https://github.com/eunchaipark/TheMoon.git
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
TAVILY_API_KEY=your_tavily_api_key
LANGCHAIN_API_KEY=your_langsmith_api_key
LANGCHAIN_PROJECT=TheMoon
EMBED_MODEL=jhgan/ko-sroberta-multitask

REDIS_HOST=redis
REDIS_PORT=6379
KAFKA_BOOTSTRAP_SERVERS=kafka:9092
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
| RedisInsight | http://localhost:8001 |

### 5. 초기 데이터 수집

Airflow UI에서 DAG 수동 트리거:
1. `yna_collect`, `mk_collect`, `sbs_collect` 실행 (뉴스 수집)
2. `spark_pipeline` 실행 (임베딩 생성 + 중복 감지)

---

## 트러블슈팅

### Spark 임베딩 성능 문제

**문제**: Worker 3개를 사용해도 Python 단일 프로세스보다 느림
**원인**: JDBC subquery로 읽으면 파티션이 1개로 고정되어 Worker 1개만 동작
**해결**: `column`, `lowerBound`, `upperBound`, `numPartitions` 파라미터로 article_id 범위 분할

### 카테고리 검색 결과 누락

**문제**: 사회 카테고리 뉴스 검색 시 "찾지 못했습니다" 반환 (DB에는 1,020건 존재)
**원인**: 전체 검색 후 카테고리 필터링 방식에서 개인화 가중치가 높은 정치 기사가 상위를 차지
**해결**: `retrieve_by_category()`로 DB WHERE절에서 카테고리 직접 필터링

### Airflow Task 실패 (JWT 인증 오류)

**문제**: `Invalid auth token: Signature verification failed`
**원인**: Airflow 3.x에서 컨테이너마다 JWT 시크릿이 랜덤 생성됨
**해결**: `AIRFLOW__API_AUTH__JWT_SECRET` 환경변수를 모든 컨테이너에 동일하게 설정

---

## 향후 발전 방안

| 항목 | 내용 |
|------|------|
| 멀티모델 아키텍처 | Analysis/Summary에 gemini-2.5-pro 적용 (모델명 한 줄 교체로 즉시 적용 가능) |
| Slot Filling | 정보 부족 시 사용자에게 되묻는 멀티턴 대화 흐름 구현 |
| 키워드 선호도 | 카테고리 외 특정 키워드 가중치 추가 |
| 벡터 인덱스 | 데이터 1만건 이상 시 HNSW 인덱스 활성화로 검색 속도 향상 |
| Kafka 확장 | Consumer Worker 수평 확장으로 처리량 선형 증가 |
| 다국어 지원 | react-i18next 기반 한국어/영어 전환 |

---

## 프로젝트 구조

```
TheMoon/
├── frontend/
│   └── src/
│       ├── pages/Main.jsx
│       ├── components/        # ChatBot, NewsCard, MyPage 등
│       ├── api/               # feed.js, chat.js, user.js
│       └── styles/
│
├── backend/
│   ├── api/routes/            # FastAPI 라우터
│   ├── service/               # 비즈니스 로직
│   ├── repository/            # DB 쿼리
│   ├── rag/                   # agent.py, retrieve.py, chatbot.py
│   ├── worker/                # Kafka Consumer, Producer
│   ├── spark/jobs/            # embedding_job.py, dedup_job.py
│   ├── airflow/dags/          # Airflow DAG 파일
│   └── scripts/               # compare_agents.py, evaluate_agent.py
│
└── db/
    └── init.sql               # DB 스키마 + 초기 데이터
```

---

## 개발자

| 항목 | 내용 |
|------|------|
| 개발 기간 | 2026.05 ~ 2026.07 |
| 개발 인원 | 1인 개발 |
| GitHub | https://github.com/eunchaipark/TheMoon |
