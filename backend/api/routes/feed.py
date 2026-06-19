from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
from typing import Optional
from service import feed_service

router = APIRouter(prefix="/feed", tags=["feed"])


@router.get("/recommended")
def get_recommended(
    user_id: int = Query(...),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=12, ge=1, le=50),
    exclude_ids: Optional[str] = Query(default=None, description="제외할 article_id 목록 (콤마 구분)"),
):
    """
    카테고리 가중치 비율 기반 개인화 추천.
    - page: 더보기
    - exclude_ids: 1,2,3 형태로 전달하면 해당 기사 제외 (새로고침)
    """
    parsed_exclude = []
    if exclude_ids:
        try:
            parsed_exclude = [int(i) for i in exclude_ids.split(",") if i.strip()]
        except ValueError:
            pass
    return feed_service.get_recommended_feed(user_id, limit, page, parsed_exclude)


@router.get("/articles")
def get_feed_articles(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    category_id: Optional[int] = Query(default=None),
):
    """최신 뉴스 목록 (카테고리 필터 가능)."""
    return feed_service.get_latest_feed(page, limit, category_id)


@router.get("/trending")
def get_trending():
    return feed_service.get_trending_feed()


@router.get("/trending/{article_id}/others")
def get_other_press(article_id: int):
    """지금 화제 - 다른 언론사 기사 목록."""
    return feed_service.get_duplicate_articles(article_id)


@router.get("")
def feed_sse(user_id: int = Query(..., description="유저 ID")):
    """SSE 실시간 뉴스 푸시."""
    return StreamingResponse(
        feed_service.sse_feed_generator(user_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )