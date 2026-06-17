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



def process_partition(rows):
    import os
    os.environ["HF_HOME"] = "/tmp/huggingface"
    os.environ["TRANSFORMERS_CACHE"] = "/tmp/huggingface"
    os.makedirs("/tmp/huggingface", exist_ok=True)

    import psycopg2
    from sentence_transformers import SentenceTransformer

    pg_host    = os.getenv("POSTGRES_HOST", "postgres")
    pg_port    = int(os.getenv("POSTGRES_PORT", "5432"))
    pg_db      = os.getenv("POSTGRES_DB", "news_rag")
    pg_user    = os.getenv("POSTGRES_USER", "news_user")
    pg_pass    = os.getenv("POSTGRES_PASSWORD", "news_password")
    model_name = os.getenv("EMBED_MODEL", "jhgan/ko-sroberta-multitask")

    rows_list = list(rows)
    if not rows_list:
        return

    model = SentenceTransformer(model_name)

    all_chunks = []  # (article_id, chunk_index, content)
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

    # 1. 미처리 기사 로드
    articles_df = spark.read.jdbc(
        url=JDBC_URL,
        table="""(
            SELECT article_id, title, description, published_at
            FROM articles
            WHERE is_processed = false
              AND is_duplicate = false
              AND description IS NOT NULL
              AND length(description) >= 20
            ORDER BY published_at DESC
            LIMIT 500
        ) AS unprocessed""",
        properties=JDBC_PROPS,
    )

    count = articles_df.count()
    logger.info(f"처리 대상 기사 수: {count}")

    if count == 0:
        logger.info("처리할 기사 없음. 종료.")
        return {"processed": 0, "chunks": 0}

    # 2. 파티션별 청킹 + 임베딩 + 저장
    articles_df.foreachPartition(process_partition)

    # 3. is_processed=true 업데이트
    import psycopg2
    processed_ids = [row.article_id for row in articles_df.select("article_id").collect()]
    conn = psycopg2.connect(
        host=POSTGRES_HOST, port=int(POSTGRES_PORT),
        dbname=POSTGRES_DB, user=POSTGRES_USER, password=POSTGRES_PASS
    )
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE articles SET is_processed = true WHERE article_id = ANY(%s)",
            (processed_ids,)
        )
        conn.commit()
        logger.info(f"is_processed=true 업데이트: {len(processed_ids)}건")
    finally:
        conn.close()

    logger.info(f"=== Embedding Job 완료: 기사 {count}건 ===")
    return {"processed": count}


if __name__ == "__main__":
    spark = (
        SparkSession.builder
        .appName("NewsEmbeddingJob")
        .config("spark.sql.shuffle.partitions", "4")
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