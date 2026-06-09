from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
from service import feed_service

router = APIRouter(prefix="/feed", tags=["feed"])


@router.get("/articles")
def get_feed_articles(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    user_id: int = Query(default=None),
):
    """
    개인화 뉴스 목록 조회
    - user_id 있으면 카테고리 가중치 기반 추천
    - user_id 없으면 최신순
    """
    if user_id:
        articles = feed_service.get_recommended_feed(user_id)
    else:
        articles = feed_service.get_latest_feed(page, limit)
    return articles

@router.get("/trending")
def get_trending():
    return feed_service.get_trending_feed()

@router.get("")
def feed_sse(user_id: int = Query(..., description="유저 ID (SSE 연결 필수)")):
    """
    SSE 실시간 뉴스 푸시
    - 연결 시점 이후 새 기사를 30초마다 체크해서 푸시
    - 새 기사 없으면 heartbeat 전송 (연결 유지)
    """
    return StreamingResponse(
        feed_service.sse_feed_generator(user_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )