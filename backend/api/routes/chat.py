import json
import asyncio
import logging

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from service import chat_service
from service.user_service import decode_token
from repository import chat_repo

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatRequest(BaseModel):
    question: str
    session_id: str


# Kafka 사용 가능 여부 확인
def is_kafka_available() -> bool:
    try:
        from worker.kafka_producer import get_producer
        get_producer()
        return True
    except Exception:
        return False



# POST /chat - 기존 동기 방식 (폴백용)
@router.post("")
def chat(body: ChatRequest, authorization: str = Header(...)):
    """동기 응답 - Kafka 미연결 시 폴백"""
    try:
        token = authorization.replace("Bearer ", "")
        payload = decode_token(token)
        return chat_service.chat(
            user_id=payload['user_id'],
            session_id=body.session_id,
            question=body.question,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# POST /chat/stream - Kafka + SSE 스트리밍
@router.post("/stream")
async def chat_stream(body: ChatRequest, authorization: str = Header(...)):
    try:
        token = authorization.replace("Bearer ", "")
        payload = decode_token(token)
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))

    user_id = payload['user_id']

    # 대화 히스토리 조회
    history = chat_repo.get_history(body.session_id, limit=3)
    history_data = [{"role": h["role"], "message": h["message"]} for h in history]

    async def generate():
        import redis as redis_lib
        import os

        try:
            r = redis_lib.Redis(
                host=os.getenv("REDIS_HOST", "redis"),
                port=int(os.getenv("REDIS_PORT", "6379")),
                decode_responses=True,
            )
            r.ping()
            print(f"[SSE] Redis 연결 성공")
        except Exception as e:
            print(f"[SSE] Redis 연결 실패: {e}")
            yield f"data: {json.dumps({'chunk': f'Redis 연결 실패: {str(e)}', 'status': 'error'}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
            return

        try:
            kafka_ok = is_kafka_available()
            print(f"[SSE] Kafka 사용 가능: {kafka_ok}")
        except Exception as e:
            print(f"[SSE] Kafka 확인 실패: {e}")
            kafka_ok = False

        # Kafka 사용 가능하면 Kafka로, 아니면 직접 처리
        if kafka_ok:
            from worker.kafka_producer import publish_chat_request

            request_id = publish_chat_request(
                user_id=user_id,
                session_id=body.session_id,
                question=body.question,
                history=history_data,
            )

            # 대기 중 메시지 전송
            yield f"data: {json.dumps({'chunk': '답변을 생성하고 있어요...', 'status': 'processing'}, ensure_ascii=False)}\n\n"

            # Redis 폴링
            result_key = f"chat_result:{request_id}"
            max_wait = 120
            interval = 1
            elapsed = 0
            logger.info(f"SSE 폴링 시작: {result_key}")

            while elapsed < max_wait:
                await asyncio.sleep(interval)
                elapsed += interval

                raw = r.get(result_key)
                if elapsed % 10 == 0:
                    logger.info(f"SSE 폴링 중: elapsed={elapsed}s, key={result_key}, found={raw is not None}")
                if not raw:
                    continue

                result = json.loads(raw)
                status = result.get("status")

                if status == "processing":
                    continue

                elif status == "done":
                    answer  = result.get("answer", "")
                    sources = result.get("sources", [])

                    # 답변을 청크 단위로 전송 (스트리밍 효과)
                    chunk_size = 20
                    for i in range(0, len(answer), chunk_size):
                        chunk = answer[i:i + chunk_size]
                        yield f"data: {json.dumps({'chunk': chunk, 'status': 'streaming'}, ensure_ascii=False)}\n\n"
                        await asyncio.sleep(0.03)

                    # 출처 전송
                    yield f"data: {json.dumps({'sources': sources, 'status': 'done'}, ensure_ascii=False)}\n\n"
                    yield "data: [DONE]\n\n"

                    # 결과 삭제
                    r.delete(result_key)
                    return

                elif status == "error":
                    answer = result.get("answer", "오류가 발생했습니다.")
                    yield f"data: {json.dumps({'chunk': answer, 'status': 'error'}, ensure_ascii=False)}\n\n"
                    yield "data: [DONE]\n\n"
                    r.delete(result_key)
                    return

            # 타임아웃
            yield f"data: {json.dumps({'chunk': '응답 시간이 초과되었습니다. 다시 시도해주세요.', 'status': 'timeout'}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"

        else:
            # Kafka 미연결 시 기존 스트리밍 방식으로 폴백
            logger.warning("Kafka 미연결 - 직접 스트리밍으로 폴백")
            try:
                async for chunk in chat_service.chat_stream(
                    user_id=user_id,
                    session_id=body.session_id,
                    question=body.question,
                ):
                    yield f"data: {json.dumps({'chunk': chunk, 'status': 'streaming'}, ensure_ascii=False)}\n\n"
                yield "data: [DONE]\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'chunk': '오류가 발생했습니다.', 'status': 'error'}, ensure_ascii=False)}\n\n"
                yield "data: [DONE]\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection":    "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@router.get("/history/{session_id}")
def get_history(session_id: str, authorization: str = Header(...)):
    try:
        token = authorization.replace("Bearer ", "")
        decode_token(token)
        return chat_service.get_history(session_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/sessions")
def get_sessions(authorization: str = Header(...)):
    try:
        token = authorization.replace("Bearer ", "")
        payload = decode_token(token)
        return chat_service.get_sessions(payload['user_id'])
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))