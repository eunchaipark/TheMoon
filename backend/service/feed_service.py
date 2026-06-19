import asyncio
import json
from datetime import datetime
from typing import AsyncGenerator
from repository import feed_repo


def format_published_ago(published_at: datetime) -> str:
    now = datetime.now()
    diff = now - published_at.replace(tzinfo=None)
    minutes = int(diff.total_seconds() / 60)

    if minutes < 1:
        return "방금 전"
    elif minutes < 60:
        return f"{minutes}분 전"
    elif minutes < 1440:
        return f"{minutes // 60}시간 전"
    else:
        return f"{minutes // 1440}일 전"


def format_article(article: dict) -> dict:
    return {
        "article_id":    article["article_id"],
        "title":         article["title"],
        "description":   article["description"],
        "url":           article["url"],
        "published_at":  article["published_at"].isoformat() if article["published_at"] else None,
        "published_ago": format_published_ago(article["published_at"]) if article["published_at"] else "",
        "category_name": article["category_name"],
        "source_name":   article["source_name"],
        "press_count":   article.get("press_count"),
        "similarity":    article.get("similarity"),
        "category_weight": article.get("category_weight"),
    }


def get_latest_feed(page: int = 1, limit: int = 20, category_id: int = None) -> list[dict]:
    articles = feed_repo.get_latest_articles_by_category(page, limit, category_id)
    return [format_article(a) for a in articles]


def get_recommended_feed(user_id: int, limit: int = 9, page: int = 1, exclude_ids: list = None) -> list[dict]:
    articles = feed_repo.get_recommended_articles(user_id, limit, page, exclude_ids or [])
    return [format_article(a) for a in articles]


def get_trending_feed(limit: int = 9) -> list[dict]:
    articles = feed_repo.get_trending_articles(limit)
    return [format_article(a) for a in articles]


def get_duplicate_articles(article_id: int) -> list[dict]:
    articles = feed_repo.get_duplicate_articles(article_id)
    return [
        {
            "article_id":   a["article_id"],
            "title":        a["title"],
            "url":          a["url"],
            "source_name":  a["source_name"],
            "published_ago": format_published_ago(a["published_at"]) if a["published_at"] else "",
        }
        for a in articles
    ]


async def sse_feed_generator(user_id: int) -> AsyncGenerator[str, None]:
    last_fetched_at = datetime.now()

    while True:
        await asyncio.sleep(10)

        try:
            new_articles = feed_repo.get_new_articles_since(last_fetched_at, user_id)

            if new_articles:
                last_fetched_at = new_articles[0]["published_at"]
                formatted = [format_article(a) for a in new_articles]
                data = json.dumps(formatted, ensure_ascii=False, default=str)
                yield f"data: {data}\n\n"
            else:
                yield f"data: {json.dumps({'type': 'heartbeat'})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"