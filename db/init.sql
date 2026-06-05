-- ==========================================
-- 1. EXTENSIONS (확장 기능 설정)
-- ==========================================
CREATE
EXTENSION IF NOT EXISTS vector;
CREATE
EXTENSION IF NOT EXISTS "uuid-ossp";


-- ==========================================
-- 2. TABLES CREATION (테이블 생성)
-- ==========================================

-- 카테고리 정보 테이블
CREATE TABLE categories
(
    category_id SERIAL PRIMARY KEY,
    name        VARCHAR(100) UNIQUE NOT NULL
);

-- 뉴스 출처(RSS 피드) 관리 테이블
CREATE TABLE news_sources
(
    source_id   SERIAL PRIMARY KEY,
    category_id INT          NOT NULL,
    name        VARCHAR(200) NOT NULL,
    rss_url     TEXT UNIQUE  NOT NULL,
    is_active   BOOLEAN DEFAULT TRUE,
    FOREIGN KEY (category_id) REFERENCES categories (category_id) ON DELETE RESTRICT
);

-- 수집된 뉴스 기사 메인 테이블
CREATE TABLE articles
(
    article_id        BIGSERIAL PRIMARY KEY,
    source_id         INT         NOT NULL,
    category_id       INT         NOT NULL,
    title             TEXT        NOT NULL,
    description       TEXT        NOT NULL,
    url               TEXT UNIQUE NOT NULL,
    published_at      TIMESTAMP   NOT NULL,
    is_processed      BOOLEAN   DEFAULT FALSE,
    is_duplicate      BOOLEAN   DEFAULT FALSE,
    representative_id BIGINT,
    created_at        TIMESTAMP DEFAULT NOW(),
    FOREIGN KEY (source_id) REFERENCES news_sources (source_id) ON DELETE RESTRICT,
    FOREIGN KEY (category_id) REFERENCES categories (category_id) ON DELETE RESTRICT,
    FOREIGN KEY (representative_id) REFERENCES articles (article_id) ON DELETE SET NULL
);

-- RAG 시스템용 기사 분할(Chunk) 및 임베딩 벡터 테이블
CREATE TABLE article_chunks
(
    chunk_id    BIGSERIAL PRIMARY KEY,
    article_id  BIGINT NOT NULL,
    chunk_index INT    NOT NULL,
    content     TEXT   NOT NULL,
    embedding   VECTOR(768), -- pgvector 768차원
    created_at  TIMESTAMP DEFAULT NOW(),
    FOREIGN KEY (article_id) REFERENCES articles (article_id) ON DELETE CASCADE
);

-- 사용자 계정 테이블
CREATE TABLE users
(
    user_id       BIGSERIAL PRIMARY KEY,
    email         VARCHAR(255) UNIQUE NOT NULL,
    password_hash TEXT                NOT NULL,
    nickname      VARCHAR(100),
    created_at    TIMESTAMP DEFAULT NOW()
);

-- 유저별 카테고리 선호도 관리 테이블 (1~10 가중치 제한)
CREATE TABLE user_category_prefs
(
    pref_id     BIGSERIAL PRIMARY KEY,
    user_id     BIGINT NOT NULL,
    category_id INT    NOT NULL,
    weight      INT    NOT NULL CHECK (weight BETWEEN 1 AND 10),
    created_at  TIMESTAMP DEFAULT NOW(),
    UNIQUE (user_id, category_id),
    FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE,
    FOREIGN KEY (category_id) REFERENCES categories (category_id) ON DELETE CASCADE
);

-- 유저별 키워드 선호도 관리 테이블 (추후 기능 확장 시 활성화) --> 카테고리 뿐만이나리 나중에 키워드로 개인화 확장 가능
-- CREATE TABLE user_keyword_prefs (
--     pref_id BIGSERIAL PRIMARY KEY,
--     user_id BIGINT NOT NULL,
--     keyword VARCHAR(100) NOT NULL,
--     weight INT NOT NULL CHECK (weight BETWEEN 1 AND 10),
--     created_at TIMESTAMP DEFAULT NOW(),
--     FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
-- );

-- 챗봇 세션 관리 테이블
CREATE TABLE chat_sessions
(
    session_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id    BIGINT NOT NULL,
    created_at TIMESTAMP        DEFAULT NOW(),
    updated_at TIMESTAMP        DEFAULT NOW(),
    FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
);

-- 대화 내용 상세 기록 테이블
CREATE TABLE chat_history
(
    chat_id    BIGSERIAL PRIMARY KEY,
    session_id UUID        NOT NULL,
    role       VARCHAR(20) NOT NULL, -- 'user' 또는 'assistant'
    message    TEXT        NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    FOREIGN KEY (session_id) REFERENCES chat_sessions (session_id) ON DELETE CASCADE
);

-- 답변 생성 시 참조된 뉴스 기사(출처) 매핑 테이블
CREATE TABLE chat_sources
(
    id         BIGSERIAL PRIMARY KEY,
    chat_id    BIGINT NOT NULL,
    article_id BIGINT NOT NULL,
    rank       INT    NOT NULL,
    similarity FLOAT  NOT NULL,
    FOREIGN KEY (chat_id) REFERENCES chat_history (chat_id) ON DELETE CASCADE,
    FOREIGN KEY (article_id) REFERENCES articles (article_id) ON DELETE CASCADE
);


-- ==========================================
-- 3. INDEXES (성능 최적화를 위한 인덱스 설정)
-- ==========================================
CREATE INDEX idx_articles_category ON articles (category_id);
CREATE INDEX idx_articles_published ON articles (published_at);
CREATE INDEX idx_articles_is_processed ON articles (is_processed);
CREATE INDEX idx_articles_is_duplicate ON articles (is_duplicate);
CREATE INDEX idx_chunks_article ON article_chunks (article_id);
CREATE INDEX idx_chat_history_session ON chat_history (session_id);

-- 데이터 1000건 이상 쌓인 후 활성화
-- CREATE INDEX idx_chunks_embedding ON article_chunks USING hnsw (embedding vector_cosine_ops);


-- ==========================================
-- 4. DEFAULT DATA (기본 데이터 삽입)
-- ==========================================
INSERT INTO categories (name)
VALUES ('정치'),
       ('경제'),
       ('사회') ON CONFLICT (name) DO NOTHING;

-- category_id: 1=정치, 2=경제, 3=사회
INSERT INTO news_sources (name, rss_url, category_id)
VALUES ('연합뉴스_정치', 'https://www.yna.co.kr/rss/politics.xml', 1),
       ('연합뉴스_경제', 'https://www.yna.co.kr/rss/economy.xml', 2),
       ('매일경제_정치', 'https://www.mk.co.kr/rss/30200030/', 1),
       ('매일경제_경제', 'https://www.mk.co.kr/rss/30100041/', 2),
       ('매일경제_사회', 'https://www.mk.co.kr/rss/50400012/', 3),
       ('한국경제_정치', 'https://www.hankyung.com/feed/politics', 1),
       ('한국경제_경제', 'https://www.hankyung.com/feed/economy', 2),
       ('한국경제_사회', 'https://www.hankyung.com/feed/society', 3),
       ('경향신문_정치', 'https://www.khan.co.kr/rss/rssdata/politic.xml', 1),
       ('경향신문_경제', 'https://www.khan.co.kr/rss/rssdata/economy.xml', 2),
       ('SBS_정치', 'https://news.sbs.co.kr/news/SectionRssFeed.do?sectionId=01', 1),
       ('SBS_경제', 'https://news.sbs.co.kr/news/SectionRssFeed.do?sectionId=02', 2) ON CONFLICT (rss_url) DO NOTHING;



-- ==========================================
-- 5. DUMMY DATA (개발 및 테스트용)
-- ==========================================

-- 테스트 유저
INSERT INTO users (email, password_hash, nickname)
VALUES ('test1@news.com', '$2b$12$dummy_hash_user1', '김테스트'),
       ('test2@news.com', '$2b$12$dummy_hash_user2', '이개발') ON CONFLICT (email) DO NOTHING;

-- 테스트 유저 카테고리 선호도
INSERT INTO user_category_prefs (user_id, category_id, weight)
VALUES (1, 1, 9),
       (1, 2, 6),
       (2, 2, 10),
       (2, 3, 7)
    ON CONFLICT (user_id, category_id) DO NOTHING;

-- 테스트 기사 (is_processed=false, embedding 없음)
INSERT INTO articles (source_id, category_id, title, description, url, published_at)
VALUES (1, 1, '국회 본회의 예산안 처리 논의 본격화',
        '국회가 내년도 예산안 처리를 위한 본회의 일정을 조율 중이다. 여야는 예산안 세부 항목을 두고 막판 협상을 이어가고 있다.',
        'https://www.yna.co.kr/view/AKR20240101001', NOW() - INTERVAL '2 hours'),

       (1, 1, '대통령실 국정 운영 방향 발표',
        '대통령실이 하반기 국정 운영 핵심 과제를 발표했다. 민생 경제 회복과 외교 강화를 최우선 과제로 제시했다.',
        'https://www.yna.co.kr/view/AKR20240101002', NOW() - INTERVAL '4 hours'),

       (2, 2, '한국은행 기준금리 동결 결정',
        '한국은행 금융통화위원회가 기준금리를 현 수준으로 동결했다. 물가 안정세와 경기 침체 우려를 동시에 고려한 결정이다.',
        'https://www.yna.co.kr/view/AKR20240101003', NOW() - INTERVAL '1 hour'),

       (2, 2, '삼성전자 3분기 영업이익 10조 돌파',
        '삼성전자가 3분기 영업이익 10조원을 넘어섰다. 반도체 업황 회복과 스마트폰 판매 호조가 실적을 견인했다.',
        'https://www.yna.co.kr/view/AKR20240101004', NOW() - INTERVAL '3 hours'),

       (5, 3, '수도권 폭우 피해 복구 작업 진행',
        '수도권 일대를 강타한 폭우로 인한 피해 복구 작업이 진행 중이다. 이재민 지원과 도로 복구에 행정력을 집중하고 있다.',
        'https://www.mk.co.kr/news/001', NOW() - INTERVAL '5 hours'),

       (5, 3, '전국 대학병원 응급실 과부하 문제 심화',
        '전국 주요 대학병원 응급실이 환자 급증으로 과부하 상태에 놓였다. 의료진 부족과 병상 부족이 동시에 문제로 지적되고 있다.',
        'https://www.mk.co.kr/news/002', NOW() - INTERVAL '6 hours') ON CONFLICT (url) DO NOTHING;

-- 테스트 청크 (embedding NULL, Spark 처리 전 상태)
INSERT INTO article_chunks (article_id, chunk_index, content)
VALUES (1, 0, '국회가 내년도 예산안 처리를 위한 본회의 일정을 조율 중이다.'),
       (1, 1, '여야는 예산안 세부 항목을 두고 막판 협상을 이어가고 있다.'),
       (2, 0, '대통령실이 하반기 국정 운영 핵심 과제를 발표했다.'),
       (2, 1, '민생 경제 회복과 외교 강화를 최우선 과제로 제시했다.'),
       (3, 0, '한국은행 금융통화위원회가 기준금리를 현 수준으로 동결했다.'),
       (3, 1, '물가 안정세와 경기 침체 우려를 동시에 고려한 결정이다.'),
       (4, 0, '삼성전자가 3분기 영업이익 10조원을 넘어섰다.'),
       (4, 1, '반도체 업황 회복과 스마트폰 판매 호조가 실적을 견인했다.'),
       (5, 0, '수도권 일대를 강타한 폭우로 인한 피해 복구 작업이 진행 중이다.'),
       (6, 0, '전국 주요 대학병원 응급실이 환자 급증으로 과부하 상태에 놓였다.') ON CONFLICT DO NOTHING;

-- 테스트 챗 세션
INSERT INTO chat_sessions (session_id, user_id)
VALUES ('a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11', 1),
       ('b1ffcd00-0d1c-5fg9-cc7e-7cc0ce491b22', 2) ON CONFLICT (session_id) DO NOTHING;

-- 테스트 대화 기록
INSERT INTO chat_history (session_id, role, message)
VALUES ('a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11', 'user', '오늘 정치 뉴스 요약해줘'),
       ('a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11', 'assistant', '오늘 주요 정치 뉴스는 국회 예산안 처리 논의와 대통령실 국정 운영 방향 발표입니다.'),
       ('b1ffcd00-0d1c-5fg9-cc7e-7cc0ce491b22', 'user', '삼성전자 실적 어때?'),
       ('b1ffcd00-0d1c-5fg9-cc7e-7cc0ce491b22', 'assistant',
        '삼성전자가 3분기 영업이익 10조원을 돌파했습니다. 반도체 업황 회복이 주요 원인입니다.') ON CONFLICT DO NOTHING;