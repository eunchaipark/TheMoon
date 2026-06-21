import os
import sys
import re
import logging
from pyspark.sql import SparkSession
from pyspark.sql import functions as F

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s"
)
logger = logging.getLogger("embedding_job")


POSTGRES_HOST = os.getenv("POSTGRES_HOST", "postgres")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_DB   = os.getenv("POSTGRES_DB",   "news_rag")
POSTGRES_USER = os.getenv("POSTGRES_USER", "news_user")
POSTGRES_PASS = os.getenv("POSTGRES_PASSWORD", "news_password")
JDBC_URL      = f"jdbc:postgresql://{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
JDBC_PROPS    = {"user": POSTGRES_USER, "password": POSTGRES_PASS, "driver": "org.postgresql.Driver"}

EMBED_MODEL   = os.getenv("EMBED_MODEL", "jhgan/ko-sroberta-multitask")
BATCH_SIZE    = int(os.getenv("EMBED_BATCH_SIZE", "32"))
MAX_CHUNK_LEN = int(os.getenv("MAX_CHUNK_LEN", "200"))
OVERLAP       = int(os.getenv("CHUNK_OVERLAP", "30"))
NUM_PARTITIONS = int(os.getenv("SPARK_NUM_PARTITIONS", "6"))  # Worker 3 × Core 2



def chunk_text(text: str, max_len: int = MAX_CHUNK_LEN, overlap: int = OVERLAP):
    if not text or not text.strip():
        return []

    sentences = re.split(r'(?<=[.!?。])\s+', text.strip())
    chunks = []
    current = ""

    for sent in sentences:
        sent = sent.strip()
        if not sent:
            continue

        if len(sent) > max_len:
            if current:
                chunks.append(current.strip())
                current = ""
            for i in range(0, len(sent), max_len - overlap):
                piece = sent[i: i + max_len]
                if piece.strip():
                    chunks.append(piece.strip())
            continue

        if len(current) + len(sent) + 1 > max_len:
            if current:
                chunks.append(current.strip())
            current = (current[-overlap:] + " " + sent).strip() if overlap and current else sent
        else:
            current = (current + " " + sent).strip() if current else sent

    if current.strip():
        chunks.append(current.strip())

    return chunks



_worker_model = None
_worker_model_name = None

def get_worker_model(model_name: str):
    global _worker_model, _worker_model_name
    import os
    os.environ["HF_HOME"] = "/tmp/huggingface"
    os.environ["TRANSFORMERS_CACHE"] = "/tmp/huggingface"
    os.makedirs("/tmp/huggingface", exist_ok=True)

    if _worker_model is None or _worker_model_name != model_name:
        from sentence_transformers import SentenceTransformer
        _worker_model = SentenceTransformer(model_name)
        _worker_model_name = model_name
    return _worker_model



def process_partition(rows):
    import os
    import psycopg2

    pg_host    = os.getenv("POSTGRES_HOST", "postgres")
    pg_port    = int(os.getenv("POSTGRES_PORT", "5432"))
    pg_db      = os.getenv("POSTGRES_DB", "news_rag")
    pg_user    = os.getenv("POSTGRES_USER", "news_user")
    pg_pass    = os.getenv("POSTGRES_PASSWORD", "news_password")
    model_name = os.getenv("EMBED_MODEL", "jhgan/ko-sroberta-multitask")

    rows_list = list(rows)
    if not rows_list:
        return

    # 모델 로드 (Worker 프로세스 내 전역 캐시 활용)
    model = get_worker_model(model_name)

    # 청킹
    all_chunks = []
    for row in rows_list:
        full_text = f"{row.title}. {row.description}" if row.description else row.title
        chunks = chunk_text(full_text)
        for idx, chunk in enumerate(chunks):
            if len(chunk) > 10:
                all_chunks.append((row.article_id, idx, chunk))

    if not all_chunks:
        return


    texts = [c[2] for c in all_chunks]
    embeddings = model.encode(
        texts,
        batch_size=int(os.getenv("EMBED_BATCH_SIZE", "32")),
        normalize_embeddings=True,
        show_progress_bar=False,
    )

    # DB 저장
    conn = psycopg2.connect(
        host=pg_host, port=pg_port,
        dbname=pg_db, user=pg_user, password=pg_pass
    )
    try:
        cur = conn.cursor()
        batch = []
        for (article_id, chunk_idx, content), embedding in zip(all_chunks, embeddings):
            emb_str = "[" + ",".join(str(v) for v in embedding.tolist()) + "]"
            batch.append((article_id, chunk_idx, content, emb_str))

            if len(batch) >= 100:
                cur.executemany("""
                    INSERT INTO article_chunks (article_id, chunk_index, content, embedding)
                    VALUES (%s, %s, %s, %s::vector)
                    ON CONFLICT DO NOTHING
                """, batch)
                conn.commit()
                batch = []

        if batch:
            cur.executemany("""
                INSERT INTO article_chunks (article_id, chunk_index, content, embedding)
                VALUES (%s, %s, %s, %s::vector)
                ON CONFLICT DO NOTHING
            """, batch)
            conn.commit()

    finally:
        conn.close()


def run(spark: SparkSession):
    logger.info("=== Embedding Job 시작 ===")

    import psycopg2

    # 1. 파티션 범위 조회 (article_id min/max)
    conn = psycopg2.connect(
        host=POSTGRES_HOST, port=int(POSTGRES_PORT),
        dbname=POSTGRES_DB, user=POSTGRES_USER, password=POSTGRES_PASS
    )
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT MIN(article_id), MAX(article_id), COUNT(*)
            FROM articles
            WHERE is_processed = false
              AND is_duplicate = false
              AND description IS NOT NULL
              AND length(description) >= 20
        """)
        min_id, max_id, count = cur.fetchone()
    finally:
        conn.close()

    logger.info(f"처리 대상 기사 수: {count} (article_id: {min_id} ~ {max_id})")

    if not count or count == 0:
        logger.info("처리할 기사 없음. 종료.")
        return {"processed": 0, "chunks": 0}

    # 2. article_id 범위로 파티션 분할해서 읽기 (진짜 병렬 처리 핵심)
    articles_df = spark.read.jdbc(
        url=JDBC_URL,
        table="""(
            SELECT article_id, title, description, published_at
            FROM articles
            WHERE is_processed = false
              AND is_duplicate = false
              AND description IS NOT NULL
              AND length(description) >= 20
        ) AS unprocessed""",
        column="article_id",
        lowerBound=int(min_id),
        upperBound=int(max_id) + 1,
        numPartitions=NUM_PARTITIONS,
        properties=JDBC_PROPS,
    )

    actual_partitions = articles_df.rdd.getNumPartitions()
    logger.info(f"파티션 수: {actual_partitions} (Worker {NUM_PARTITIONS//2}개 × Core 2개)")

    # 3. Worker별 병렬 처리
    articles_df.foreachPartition(process_partition)

    # 4. is_processed=true 업데이트
    conn = psycopg2.connect(
        host=POSTGRES_HOST, port=int(POSTGRES_PORT),
        dbname=POSTGRES_DB, user=POSTGRES_USER, password=POSTGRES_PASS
    )
    try:
        cur = conn.cursor()
        cur.execute("""
            UPDATE articles SET is_processed = true
            WHERE is_processed = false
              AND is_duplicate = false
              AND description IS NOT NULL
              AND length(description) >= 20
        """)
        conn.commit()
        logger.info(f"is_processed=true 업데이트 완료")
    finally:
        conn.close()

    logger.info(f"=== Embedding Job 완료: 기사 {count}건 ===")
    return {"processed": count}


if __name__ == "__main__":
    spark = (
        SparkSession.builder
        .appName("NewsEmbeddingJob")
        .config("spark.sql.shuffle.partitions", str(NUM_PARTITIONS))
        .config("spark.executor.memory", "2g")
        .config("spark.driver.memory", "1g")
        .config("spark.python.worker.reuse", "true")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("WARN")

    try:
        result = run(spark)
        logger.info(f"결과: {result}")
        sys.exit(0)
    except Exception as e:
        logger.exception(f"Job 실패: {e}")
        sys.exit(1)
    finally:
        spark.stop()