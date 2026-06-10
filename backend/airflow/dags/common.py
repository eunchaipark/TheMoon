"""
언론사 RSS 수집 공통 함수
모든 언론사 DAG에서 공유하는 로직
"""
import re
import logging
import feedparser
import psycopg2
from datetime import datetime
from email.utils import parsedate_to_datetime

logger = logging.getLogger(__name__)


def clean_html(text: str) -> str:
    if not text:
        return ""
    return re.sub(r'<[^>]+>', '', text).strip()


def parse_date(date_str: str) -> datetime | None:
    try:
        return parsedate_to_datetime(date_str).replace(tzinfo=None)
    except Exception:
        return None


def validate_article(title: str, description: str, url: str, published_at: datetime) -> bool:
    if not title or not url or not published_at:
        return False
    if not description or len(description.strip()) < 50:
        logger.info(f"요약문 부족으로 폐기: {title[:30]}")
        return False
    return True


def get_connection():
    import os
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "postgres"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        dbname=os.getenv("POSTGRES_DB", "news_rag"),
        user=os.getenv("POSTGRES_USER", "news_user"),
        password=os.getenv("POSTGRES_PASSWORD", "news_password"),
    )


def save_article(source_id: int, category_id: int, title: str,
                 description: str, url: str, published_at: datetime) -> bool:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO articles (source_id, category_id, title, description, url, published_at)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (url) DO NOTHING
            RETURNING article_id
        """, (source_id, category_id, title, description, url, published_at))
        conn.commit()
        result = cur.fetchone()
        return result is not None
    except Exception as e:
        conn.rollback()
        logger.error(f"DB 저장 실패: {e}")
        return False
    finally:
        conn.close()


def collect_rss(source_id: int, category_id: int, rss_url: str) -> dict:
    """연합뉴스, 매일경제 공통 — summary 필드 사용"""
    logger.info(f"RSS 수집 시작: {rss_url}")
    feed = feedparser.parse(rss_url)

    total = len(feed.entries)
    saved = 0
    skipped = 0

    for entry in feed.entries:
        title = clean_html(entry.get('title', ''))
        description = clean_html(entry.get('summary', '') or entry.get('description', ''))
        url = entry.get('link', '')
        published_at = parse_date(entry.get('published', ''))

        if not validate_article(title, description, url, published_at):
            skipped += 1
            continue

        if save_article(source_id, category_id, title, description, url, published_at):
            saved += 1
        else:
            skipped += 1

    result = {"total": total, "saved": saved, "skipped": skipped}
    logger.info(f"RSS 수집 완료: {result}")
    return result


def collect_rss_sbs(source_id: int, category_id: int, rss_url: str) -> dict:
    """SBS 전용 — content 필드 우선 사용"""
    logger.info(f"SBS RSS 수집 시작: {rss_url}")
    feed = feedparser.parse(rss_url)

    total = len(feed.entries)
    saved = 0
    skipped = 0

    for entry in feed.entries:
        title = clean_html(entry.get('title', ''))
        url = entry.get('link', '')
        published_at = parse_date(entry.get('published', ''))

        content_list = entry.get('content', [])
        if content_list:
            description = clean_html(content_list[0].get('value', ''))
        else:
            description = clean_html(entry.get('summary', ''))

        if not validate_article(title, description, url, published_at):
            skipped += 1
            continue

        if save_article(source_id, category_id, title, description, url, published_at):
            saved += 1
        else:
            skipped += 1

    result = {"total": total, "saved": saved, "skipped": skipped}
    logger.info(f"SBS RSS 수집 완료: {result}")
    return result