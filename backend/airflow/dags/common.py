import re
import logging
import feedparser
import psycopg2
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

logger = logging.getLogger(__name__)


def clean_html(text: str) -> str:
    if not text:
        return ""
    return re.sub(r'<[^>]+>', '', text).strip()


def parse_date(date_str: str) -> datetime | None:
    # DB published_at은 timezone 없는 컬럼이고 Postgres NOW()는 UTC 기준이라,
    # RSS의 오프셋(주로 KST +09:00)을 버리지 않고 UTC로 변환 후 저장해야
    # "최근 N시간" 류 비교 쿼리가 실제 경과 시간과 어긋나지 않음
    try:
        dt = parsedate_to_datetime(date_str)
        if dt.tzinfo is not None:
            dt = dt.astimezone(timezone.utc)
        return dt.replace(tzinfo=None)
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


def _collect_entries(source_id: int, category_id: int, entries, extract_description) -> dict:
    total = len(entries)
    saved = 0
    skipped = 0

    for entry in entries:
        title = clean_html(entry.get('title', ''))
        description = extract_description(entry)
        url = entry.get('link', '')
        published_at = parse_date(entry.get('published', ''))

        if not validate_article(title, description, url, published_at):
            skipped += 1
            continue

        if save_article(source_id, category_id, title, description, url, published_at):
            saved += 1
        else:
            skipped += 1

    return {"total": total, "saved": saved, "skipped": skipped}


def _check_feed_fetched(feed, rss_url: str) -> None:
    # bozo=1이어도 entries가 있으면 경미한 XML 이슈일 수 있어 통과시키고,
    # entries가 아예 없을 때만 진짜 수집 실패로 보고 예외를 던져 Airflow 재시도가 동작하게 함
    if feed.bozo and not feed.entries:
        raise RuntimeError(f"RSS 수집 실패: {rss_url} - {feed.bozo_exception}")


def collect_rss(source_id: int, category_id: int, rss_url: str) -> dict:
    # 연합뉴스, 매일경제 공통 — summary 필드 사용
    logger.info(f"RSS 수집 시작: {rss_url}")
    feed = feedparser.parse(rss_url)
    _check_feed_fetched(feed, rss_url)

    result = _collect_entries(
        source_id, category_id, feed.entries,
        lambda entry: clean_html(entry.get('summary', '') or entry.get('description', '')),
    )
    logger.info(f"RSS 수집 완료: {result}")
    return result


def collect_rss_sbs(source_id: int, category_id: int, rss_url: str) -> dict:
    # SBS 전용 — content 필드 우선 사용
    logger.info(f"SBS RSS 수집 시작: {rss_url}")
    feed = feedparser.parse(rss_url)
    _check_feed_fetched(feed, rss_url)

    def extract_description(entry):
        content_list = entry.get('content', [])
        if content_list:
            return clean_html(content_list[0].get('value', ''))
        return clean_html(entry.get('summary', ''))

    result = _collect_entries(source_id, category_id, feed.entries, extract_description)
    logger.info(f"SBS RSS 수집 완료: {result}")
    return result