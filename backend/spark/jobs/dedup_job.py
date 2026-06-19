import os
import sys
import logging
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import (
    StructType, StructField,
    LongType, IntegerType, FloatType, ArrayType, StringType, BooleanType
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s"
)
logger = logging.getLogger("dedup_job")


POSTGRES_HOST = os.getenv("POSTGRES_HOST", "postgres")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_DB   = os.getenv("POSTGRES_DB",   "news_rag")
POSTGRES_USER = os.getenv("POSTGRES_USER", "news_user")
POSTGRES_PASS = os.getenv("POSTGRES_PASSWORD", "news_password")
JDBC_URL      = f"jdbc:postgresql://{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
JDBC_PROPS    = {"user": POSTGRES_USER, "password": POSTGRES_PASS, "driver": "org.postgresql.Driver"}

SIMILARITY_THRESHOLD = float(os.getenv("DEDUP_THRESHOLD", "0.75"))
TIME_WINDOW_HOURS    = int(os.getenv("DEDUP_WINDOW_HOURS", "24"))


def detect_duplicates_in_category(rows: list) -> list:
    """
    단일 카테고리 내 기사들의 중복을 감지.
    같은 source_id끼리는 비교 제외 (동일 언론사 내 중복 방지).

    Args:
        rows: [(article_id, published_at, embedding_list, source_id), ...]

    Returns:
        [(duplicate_article_id, representative_article_id), ...]
    """
    import numpy as np

    if len(rows) < 2:
        return []

    # published_at 기준 오름차순 정렬 (오래된 것이 representative)
    rows_sorted = sorted(rows, key=lambda r: r[1])

    ids        = [r[0] for r in rows_sorted]
    source_ids = [r[3] for r in rows_sorted]
    embeddings = np.array([r[2] for r in rows_sorted], dtype=np.float32)

    # 이미 정규화된 임베딩이므로 내적 = 코사인 유사도
    sim_matrix = embeddings @ embeddings.T

    duplicates = []
    is_duplicate = [False] * len(ids)

    for i in range(len(ids)):
        if is_duplicate[i]:
            continue
        for j in range(i + 1, len(ids)):
            if is_duplicate[j]:
                continue
            # 같은 언론사(source_id)끼리는 중복 비교 제외
            if source_ids[i] == source_ids[j]:
                continue
            if sim_matrix[i, j] >= SIMILARITY_THRESHOLD:
                # j가 i의 중복 (i가 더 오래된 대표)
                duplicates.append((ids[j], ids[i]))
                is_duplicate[j] = True

    return duplicates


def apply_dedup_results(duplicates: list):
    if not duplicates:
        logger.info("감지된 중복 없음.")
        return

    import psycopg2
    conn = psycopg2.connect(
        host=POSTGRES_HOST, port=int(POSTGRES_PORT),
        dbname=POSTGRES_DB, user=POSTGRES_USER, password=POSTGRES_PASS
    )
    try:
        cur = conn.cursor()
        for dup_id, rep_id in duplicates:
            cur.execute("""
                UPDATE articles
                SET is_duplicate = true,
                    representative_id = %s
                WHERE article_id = %s
                  AND is_duplicate = false
            """, (rep_id, dup_id))
        conn.commit()
        logger.info(f"중복 처리 완료: {len(duplicates)}건")
    finally:
        conn.close()


def run(spark: SparkSession):
    logger.info("=== Dedup Job 시작 ===")


    articles_df = spark.read.jdbc(
        url=JDBC_URL,
        table=f"""(
            SELECT
                a.article_id,
                a.category_id,
                a.source_id,
                a.published_at,
                ac.embedding::text AS embedding_text
            FROM articles a
            JOIN article_chunks ac
              ON a.article_id = ac.article_id
             AND ac.chunk_index = 0
            WHERE a.is_processed = true
              AND a.is_duplicate = false
              AND a.published_at > NOW() - INTERVAL '{TIME_WINDOW_HOURS} hours'
              AND ac.embedding IS NOT NULL
        ) AS recent_articles""",
        properties=JDBC_PROPS,
    )

    count = articles_df.count()
    logger.info(f"비교 대상 기사 수: {count}")

    if count < 2:
        logger.info("비교 대상 기사 부족. 종료.")
        return {"duplicates_found": 0}


    def parse_embedding(emb_text: str):
        if not emb_text:
            return None
        try:
            cleaned = emb_text.strip().lstrip("[").rstrip("]")
            return [float(x) for x in cleaned.split(",")]
        except Exception:
            return None

    parse_emb_udf = F.udf(parse_embedding, ArrayType(FloatType()))

    articles_df = articles_df.withColumn(
        "embedding", parse_emb_udf(F.col("embedding_text"))
    ).filter(F.col("embedding").isNotNull())


    category_ids = [row.category_id for row in articles_df.select("category_id").distinct().collect()]
    logger.info(f"처리할 카테고리: {category_ids}")

    all_duplicates = []

    for cat_id in category_ids:
        cat_rows = (
            articles_df
            .filter(F.col("category_id") == cat_id)
            .select("article_id", "published_at", "embedding", "source_id")
            .collect()
        )

        rows_data = [
            (row.article_id, row.published_at, row.embedding, row.source_id)
            for row in cat_rows
        ]

        dups = detect_duplicates_in_category(rows_data)
        logger.info(f"카테고리 {cat_id}: 기사 {len(rows_data)}건 중 중복 {len(dups)}건")
        all_duplicates.extend(dups)

    apply_dedup_results(all_duplicates)

    logger.info(f"=== Dedup Job 완료: 총 중복 {len(all_duplicates)}건 처리 ===")
    return {"duplicates_found": len(all_duplicates)}


if __name__ == "__main__":
    spark = (
        SparkSession.builder
        .appName("NewsDedupJob")
        .config("spark.jars.packages", "org.postgresql:postgresql:42.7.3")
        .config("spark.sql.shuffle.partitions", "4")
        .config("spark.executor.memory", "1g")
        .config("spark.driver.memory", "1g")
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