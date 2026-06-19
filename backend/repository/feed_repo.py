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
                c.name                      AS category_name,
                SPLIT_PART(ns.name, '_', 1) AS source_name
            FROM articles a
            JOIN categories   c  ON a.category_id = c.category_id
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


def get_latest_articles_by_category(page: int = 1, limit: int = 20, category_id: int = None) -> list[dict]:
    offset = (page - 1) * limit
    conn = get_connection()
    try:
        cur = conn.cursor()
        if category_id:
            cur.execute("""
                SELECT
                    a.article_id,
                    a.title,
                    a.description,
                    a.url,
                    a.published_at,
                    c.name                      AS category_name,
                    SPLIT_PART(ns.name, '_', 1) AS source_name
                FROM articles a
                JOIN categories   c  ON a.category_id = c.category_id
                JOIN news_sources ns ON a.source_id   = ns.source_id
                WHERE a.is_duplicate = false
                  AND a.is_processed = true
                  AND a.category_id = %s
                ORDER BY a.published_at DESC
                LIMIT %s OFFSET %s
            """, (category_id, limit, offset))
        else:
            cur.execute("""
                SELECT
                    a.article_id,
                    a.title,
                    a.description,
                    a.url,
                    a.published_at,
                    c.name                      AS category_name,
                    SPLIT_PART(ns.name, '_', 1) AS source_name
                FROM articles a
                JOIN categories   c  ON a.category_id = c.category_id
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
                c.name                      AS category_name,
                SPLIT_PART(ns.name, '_', 1) AS source_name,
                ucp.weight                  AS category_weight
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


def get_recommended_articles(user_id: int, limit: int = 9, page: int = 1, exclude_ids: list = None) -> list[dict]:
    """
    카테고리 가중치 비율에 따라 기사를 배분해서 추천.
    - 가중치 합계 대비 각 카테고리 비율로 limit 배분
    - 동일 카테고리 내에서는 최신순
    - exclude_ids: 이미 본 기사 제외 (새로고침용)
    - page: 더보기용 페이지네이션
    """
    conn = get_connection()
    try:
        cur = conn.cursor()

        # 유저 카테고리 가중치 조회
        cur.execute("""
            SELECT category_id, weight
            FROM user_category_prefs
            WHERE user_id = %s
            ORDER BY weight DESC
        """, (user_id,))
        prefs = cur.fetchall()

        if not prefs:
            # 선호도 없으면 최신순
            return get_latest_articles(page, limit)

        total_weight = sum(w for _, w in prefs)
        offset = (page - 1) * limit
        exclude_ids = exclude_ids or []

        # 카테고리별 할당 기사 수 계산
        allocations = []
        remaining = limit
        for i, (cat_id, weight) in enumerate(prefs):
            if i == len(prefs) - 1:
                count = remaining  # 나머지 전부
            else:
                count = max(1, round(limit * weight / total_weight))
                remaining -= count
                remaining = max(0, remaining)
            allocations.append((cat_id, count))

        articles = []
        for cat_id, count in allocations:
            if count <= 0:
                continue

            if exclude_ids:
                cur.execute("""
                    SELECT
                        a.article_id,
                        a.title,
                        a.description,
                        a.url,
                        a.published_at,
                        c.name                      AS category_name,
                        SPLIT_PART(ns.name, '_', 1) AS source_name,
                        ucp.weight                  AS category_weight
                    FROM articles a
                    JOIN categories       c   ON a.category_id = c.category_id
                    JOIN news_sources     ns  ON a.source_id   = ns.source_id
                    JOIN user_category_prefs ucp
                        ON a.category_id = ucp.category_id
                       AND ucp.user_id   = %s
                    WHERE a.is_duplicate = false
                      AND a.is_processed = true
                      AND a.category_id  = %s
                      AND a.article_id   NOT IN %s
                    ORDER BY a.published_at DESC
                    LIMIT %s OFFSET %s
                """, (user_id, cat_id, tuple(exclude_ids), count, offset))
            else:
                cur.execute("""
                    SELECT
                        a.article_id,
                        a.title,
                        a.description,
                        a.url,
                        a.published_at,
                        c.name                      AS category_name,
                        SPLIT_PART(ns.name, '_', 1) AS source_name,
                        ucp.weight                  AS category_weight
                    FROM articles a
                    JOIN categories       c   ON a.category_id = c.category_id
                    JOIN news_sources     ns  ON a.source_id   = ns.source_id
                    JOIN user_category_prefs ucp
                        ON a.category_id = ucp.category_id
                       AND ucp.user_id   = %s
                    WHERE a.is_duplicate = false
                      AND a.is_processed = true
                      AND a.category_id  = %s
                    ORDER BY a.published_at DESC
                    LIMIT %s OFFSET %s
                """, (user_id, cat_id, count, offset))

            rows = cur.fetchall()
            cols = [desc[0] for desc in cur.description]
            articles.extend([dict(zip(cols, row)) for row in rows])

        # 카테고리별로 섞되 가중치 높은 순 유지하면서 인터리빙
        result = []
        buckets = {}
        for a in articles:
            cat = a['category_name']
            buckets.setdefault(cat, []).append(a)

        # 라운드로빈 방식으로 인터리빙
        while any(buckets.values()):
            for cat_id, _ in prefs:
                cur.execute("SELECT name FROM categories WHERE category_id = %s", (cat_id,))
                row = cur.fetchone()
                if not row:
                    continue
                cat_name = row[0]
                if buckets.get(cat_name):
                    result.append(buckets[cat_name].pop(0))

        return result

    finally:
        conn.close()


def get_duplicate_articles(representative_id: int) -> list[dict]:
    """지금 화제 - 같은 대표 기사를 가진 중복 기사 조회.
    언론사(SPLIT_PART source name)별로 하나씩만 반환."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT DISTINCT ON (SPLIT_PART(ns.name, '_', 1))
                a.article_id,
                a.title,
                a.url,
                a.published_at,
                SPLIT_PART(ns.name, '_', 1) AS source_name
            FROM articles a
            JOIN news_sources ns ON a.source_id = ns.source_id
            WHERE a.representative_id = %s
            ORDER BY SPLIT_PART(ns.name, '_', 1), a.published_at DESC
        """, (representative_id,))
        rows = cur.fetchall()
        cols = [desc[0] for desc in cur.description]
        return [dict(zip(cols, row)) for row in rows]
    finally:
        conn.close()


def get_trending_articles(limit: int = 9) -> list[dict]:
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
                c.name                      AS category_name,
                SPLIT_PART(ns.name, '_', 1) AS source_name,
                COUNT(dup.article_id) + 1   AS press_count
            FROM articles a
            JOIN categories   c  ON a.category_id = c.category_id
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