import logging
from sentence_transformers import SentenceTransformer
from core.database import get_connection
from core.config import settings

logger = logging.getLogger(__name__)

_model = None


def get_model():
    global _model
    if _model is None:
        _model = SentenceTransformer(settings.EMBED_MODEL)
    return _model


def _fetch_dicts(sql: str, params: tuple) -> list[dict]:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(sql, params)
        rows = cur.fetchall()
        cols = [desc[0] for desc in cur.description]
        return [dict(zip(cols, row)) for row in rows]
    finally:
        conn.close()


def retrieve(query: str, user_id: int, top_k: int = 5) -> list[dict]:
    model = get_model()
    query_vector = model.encode(query).tolist()

    results = _fetch_dicts("""
        SELECT ac.chunk_id,
               ac.content,
               a.article_id,
               a.title,
               a.url,
               a.published_at,
               c.name                            AS category_name,
               ns.name                           AS source_name,
               1 - (ac.embedding <=> %s::vector) AS similarity
        FROM article_chunks ac
                 JOIN articles a ON ac.article_id = a.article_id
                 JOIN categories c ON a.category_id = c.category_id
                 JOIN news_sources ns ON a.source_id = ns.source_id
                 LEFT JOIN user_category_prefs ucp
                           ON a.category_id = ucp.category_id
                               AND ucp.user_id = %s
        WHERE ac.embedding IS NOT NULL
          AND a.is_processed = true
          AND a.is_duplicate = false
        ORDER BY (1 - (ac.embedding <=> %s::vector)) * 0.7
                     + COALESCE(ucp.weight, 5) / 10.0 * 0.2
                     + EXTRACT(EPOCH FROM a.published_at) / EXTRACT(EPOCH FROM NOW()) * 0.1
            DESC
        LIMIT %s
    """, (str(query_vector), user_id, str(query_vector), top_k))

    logger.debug(f"RAG 검색: query={query[:30]}, 결과={len(results)}건")
    return results


def retrieve_by_category(query: str, category_name: str, top_k: int = 5) -> list[dict]:
    model = get_model()
    query_vector = model.encode(query).tolist()

    results = _fetch_dicts("""
        SELECT ac.chunk_id,
               ac.content,
               a.article_id,
               a.title,
               a.url,
               a.published_at,
               c.name                            AS category_name,
               ns.name                           AS source_name,
               1 - (ac.embedding <=> %s::vector) AS similarity
        FROM article_chunks ac
                 JOIN articles a ON ac.article_id = a.article_id
                 JOIN categories c ON a.category_id = c.category_id
                 JOIN news_sources ns ON a.source_id = ns.source_id
        WHERE ac.embedding IS NOT NULL
          AND a.is_processed = true
          AND a.is_duplicate = false
          AND c.name = %s
        ORDER BY ac.embedding <=> %s::vector
        LIMIT %s
    """, (str(query_vector), category_name, str(query_vector), top_k))

    logger.debug(f"카테고리 검색: query={query[:30]}, category={category_name}, 결과={len(results)}건")
    return results