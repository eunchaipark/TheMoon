-- ==========================================
-- 1. EXTENSIONS (확장 기능 설정)
-- ==========================================
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";


-- ==========================================
-- 2. TABLES CREATION (테이블 생성)
-- ==========================================

-- 카테고리 정보 테이블
CREATE TABLE categories (
    category_id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL
);

-- 뉴스 출처(RSS 피드) 관리 테이블
CREATE TABLE news_sources (
    source_id SERIAL PRIMARY KEY,
    category_id INT NOT NULL,
    name VARCHAR(200) NOT NULL,
    rss_url TEXT UNIQUE NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    FOREIGN KEY (category_id) REFERENCES categories(category_id) ON DELETE RESTRICT
);

-- 수집된 뉴스 기사 메인 테이블
CREATE TABLE articles (
    article_id BIGSERIAL PRIMARY KEY,
    source_id INT NOT NULL,
    category_id INT NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    url TEXT UNIQUE NOT NULL,
    published_at TIMESTAMP NOT NULL,
    is_processed BOOLEAN DEFAULT FALSE,
    is_duplicate BOOLEAN DEFAULT FALSE,
    representative_id BIGINT,
    created_at TIMESTAMP DEFAULT NOW(),
    FOREIGN KEY (source_id) REFERENCES news_sources(source_id) ON DELETE RESTRICT,
    FOREIGN KEY (category_id) REFERENCES categories(category_id) ON DELETE RESTRICT,
    FOREIGN KEY (representative_id) REFERENCES articles(article_id) ON DELETE SET NULL
);

-- RAG 시스템용 기사 분할(Chunk) 및 임베딩 벡터 테이블
CREATE TABLE article_chunks (
    chunk_id BIGSERIAL PRIMARY KEY,
    article_id BIGINT NOT NULL,
    chunk_index INT NOT NULL,
    content TEXT NOT NULL,
    embedding VECTOR(768),                      -- pgvector 768차원
    created_at TIMESTAMP DEFAULT NOW(),
    FOREIGN KEY (article_id) REFERENCES articles(article_id) ON DELETE CASCADE
);

-- 사용자 계정 테이블
CREATE TABLE users (
    user_id BIGSERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    nickname VARCHAR(100),
    created_at TIMESTAMP DEFAULT NOW()
);

-- 유저별 카테고리 선호도 관리 테이블 (1~10 가중치 제한)
CREATE TABLE user_category_prefs (
    pref_id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    category_id INT NOT NULL,
    weight INT NOT NULL CHECK (weight BETWEEN 1 AND 10),
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE (user_id, category_id),
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (category_id) REFERENCES categories(category_id) ON DELETE CASCADE
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
CREATE TABLE chat_sessions (
    session_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id BIGINT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- 대화 내용 상세 기록 테이블
CREATE TABLE chat_history (
    chat_id BIGSERIAL PRIMARY KEY,
    session_id UUID NOT NULL,
    role VARCHAR(20) NOT NULL,                  -- 'user' 또는 'assistant'
    message TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    FOREIGN KEY (session_id) REFERENCES chat_sessions(session_id) ON DELETE CASCADE
);

-- 답변 생성 시 참조된 뉴스 기사(출처) 매핑 테이블
CREATE TABLE chat_sources (
    id BIGSERIAL PRIMARY KEY,
    chat_id BIGINT NOT NULL,
    article_id BIGINT NOT NULL,
    rank INT NOT NULL,
    similarity FLOAT NOT NULL,
    FOREIGN KEY (chat_id) REFERENCES chat_history(chat_id) ON DELETE CASCADE,
    FOREIGN KEY (article_id) REFERENCES articles(article_id) ON DELETE CASCADE
);


-- ==========================================
-- 3. INDEXES (성능 최적화를 위한 인덱스 설정)
-- ==========================================
CREATE INDEX idx_articles_category ON articles(category_id);
CREATE INDEX idx_articles_published ON articles(published_at);
CREATE INDEX idx_articles_is_processed ON articles(is_processed);
CREATE INDEX idx_articles_is_duplicate ON articles(is_duplicate);
CREATE INDEX idx_chunks_article ON article_chunks(article_id);
CREATE INDEX idx_chat_history_session ON chat_history(session_id);

-- 데이터 1000건 이상 쌓인 후 활성화
-- CREATE INDEX idx_chunks_embedding ON article_chunks USING hnsw (embedding vector_cosine_ops);


-- ==========================================
-- 4. DEFAULT DATA (기본 데이터 삽입)
-- ==========================================
INSERT INTO categories (name) VALUES
    ('정치'),
    ('경제'),
    ('사회')
ON CONFLICT (name) DO NOTHING;

-- category_id: 1=정치, 2=경제, 3=사회
INSERT INTO news_sources (name, rss_url, category_id) VALUES
    ('연합뉴스_정치',  'https://www.yna.co.kr/rss/politics.xml',                          1),
    ('연합뉴스_경제',  'https://www.yna.co.kr/rss/economy.xml',                           2),
    ('매일경제_정치',  'https://www.mk.co.kr/rss/30200030/',                              1),
    ('매일경제_경제',  'https://www.mk.co.kr/rss/30100041/',                              2),
    ('매일경제_사회',  'https://www.mk.co.kr/rss/50400012/',                              3),
    ('한국경제_정치',  'https://www.hankyung.com/feed/politics',                          1),
    ('한국경제_경제',  'https://www.hankyung.com/feed/economy',                           2),
    ('한국경제_사회',  'https://www.hankyung.com/feed/society',                           3),
    ('경향신문_정치',  'https://www.khan.co.kr/rss/rssdata/politic.xml',                  1),
    ('경향신문_경제',  'https://www.khan.co.kr/rss/rssdata/economy.xml',                  2),
    ('SBS_정치',       'https://news.sbs.co.kr/news/SectionRssFeed.do?sectionId=01',      1),
    ('SBS_경제',       'https://news.sbs.co.kr/news/SectionRssFeed.do?sectionId=02',      2)
ON CONFLICT (rss_url) DO NOTHING;