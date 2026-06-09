from datetime import datetime
from core.database import get_connection


def get_latest_articles(page: int = 1, limit: int = 20) -> list[dict]:
    offset = (page - 1) * limit
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT
                a.article_id,
                a.title,
                a.description,
                a.url,
                a.published_at,
                c.name      AS category_name,
                SPLIT_PART(ns.name, '_', 1)     AS source_name
            FROM articles a
            JOIN categories  c  ON a.category_id = c.category_id
            JOIN news_sources ns ON a.source_id   = ns.source_id
            WHERE a.is_duplicate = false
              AND a.is_processed = true
            ORDER BY a.published_at DESC
            LIMIT %s OFFSET %s
        """, (limit, offset))
        rows = cur.fetchall()
        cols = [desc[0] for desc in cur.description]
        return [dict(zip(cols, row)) for row in rows]
    finally:
        conn.close()


def get_new_articles_since(last_fetched_at: datetime, user_id: int) -> list[dict]:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT
                a.article_id,
                a.title,
                a.description,
                a.url,
                a.published_at,
                c.name      AS category_name,
                SPLIT_PART(ns.name, '_', 1)     AS source_name,
                ucp.weight  AS category_weight
            FROM articles a
            JOIN categories       c   ON a.category_id = c.category_id
            JOIN news_sources     ns  ON a.source_id   = ns.source_id
            JOIN user_category_prefs ucp
                ON a.category_id = ucp.category_id
               AND ucp.user_id   = %s
            WHERE a.is_duplicate = false
              AND a.is_processed = true
              AND a.published_at > %s
            ORDER BY a.published_at DESC
        """, (user_id, last_fetched_at))
        rows = cur.fetchall()
        cols = [desc[0] for desc in cur.description]
        return [dict(zip(cols, row)) for row in rows]
    finally:
        conn.close()


def get_recommended_articles(user_id: int, limit: int = 6) -> list[dict]:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT
                a.article_id,
                a.title,
                a.description,
                a.url,
                a.published_at,
                c.name      AS category_name,
                SPLIT_PART(ns.name, '_', 1)     AS source_name,
                ucp.weight  AS category_weight
            FROM articles a
            JOIN categories       c   ON a.category_id = c.category_id
            JOIN news_sources     ns  ON a.source_id   = ns.source_id
            JOIN user_category_prefs ucp
                ON a.category_id = ucp.category_id
               AND ucp.user_id   = %s
            WHERE a.is_duplicate = false
              AND a.is_processed = true
            ORDER BY ucp.weight DESC, a.published_at DESC
            LIMIT %s
        """, (user_id, limit))
        rows = cur.fetchall()
        cols = [desc[0] for desc in cur.description]
        return [dict(zip(cols, row)) for row in rows]
    finally:
        conn.close()


def get_trending_articles(limit: int = 6) -> list[dict]:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT
                a.article_id,
                a.title,
                a.description,
                a.url,
                a.published_at,
                c.name      AS category_name,
                SPLIT_PART(ns.name, '_', 1)     AS source_name,
                COUNT(dup.article_id) + 1 AS press_count
            FROM articles a
            JOIN categories  c  ON a.category_id = c.category_id
            JOIN news_sources ns ON a.source_id   = ns.source_id
            LEFT JOIN articles dup
                ON dup.representative_id = a.article_id
            WHERE a.is_duplicate = false
              AND a.is_processed = true
              AND a.published_at > NOW() - INTERVAL '24 hours'
            GROUP BY
                a.article_id, a.title, a.description,
                a.url, a.published_at, c.name, ns.name
            ORDER BY press_count DESC, a.published_at DESC
            LIMIT %s
        """, (limit,))
        rows = cur.fetchall()
        cols = [desc[0] for desc in cur.description]
        return [dict(zip(cols, row)) for row in rows]
    finally:
        conn.close()