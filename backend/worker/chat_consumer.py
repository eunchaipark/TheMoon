import json
import logging
import os
import sys
import time

sys.path.append("/app")

from kafka import KafkaConsumer
from kafka.errors import NoBrokersAvailable
import redis

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s"
)
logger = logging.getLogger("chat_consumer")

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
KAFKA_TOPIC     = "chat_requests"
REDIS_HOST      = os.getenv("REDIS_HOST", "redis")
REDIS_PORT      = int(os.getenv("REDIS_PORT", "6379"))
RESULT_TTL      = 300  # 결과 5분 보관


def get_redis():
    return redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)


def get_consumer() -> KafkaConsumer:
    retries = 10
    for i in range(retries):
        try:
            consumer = KafkaConsumer(
                KAFKA_TOPIC,
                bootstrap_servers=KAFKA_BOOTSTRAP,
                group_id="chat_consumer_group",
                auto_offset_reset="latest",
                enable_auto_commit=True,
                value_deserializer=lambda m: json.loads(m.decode("utf-8")),
                session_timeout_ms=30000,
                heartbeat_interval_ms=10000,
            )
            logger.info(f"Kafka Consumer 연결 성공: {KAFKA_BOOTSTRAP}")
            return consumer
        except NoBrokersAvailable:
            logger.warning(f"Kafka 연결 대기 중... ({i+1}/{retries})")
            time.sleep(5)
    raise RuntimeError("Kafka 연결 실패")


def process_message(msg: dict, r: redis.Redis) -> None:
    request_id = msg.get("request_id")
    user_id    = msg.get("user_id")
    session_id = msg.get("session_id")
    question   = msg.get("question")
    history    = msg.get("history", [])

    logger.info(f"처리 시작: request_id={request_id}, question='{question[:30]}'")

    result_key = f"chat_result:{request_id}"

    try:
        r.setex(result_key, RESULT_TTL, json.dumps({
            "status": "processing",
            "answer": "",
            "sources": [],
        }))

        from rag.agent import answer as agent_answer
        from repository import chat_repo

        result = agent_answer(question, user_id, history)

        chat_repo.get_or_create_session(user_id, session_id)
        chat_repo.save_message(session_id, "user", question)
        assistant_chat_id = chat_repo.save_message(session_id, "assistant", result["answer"])
        if result.get("sources"):
            chat_repo.save_sources(assistant_chat_id, result["sources"])

        payload = json.dumps({
            "status": "done",
            "answer": result["answer"],
            "sources": result.get("sources", []),
        }, ensure_ascii=False)
        save_result = r.setex(result_key, RESULT_TTL, payload)
        logger.info(f"Redis 저장 결과: {save_result}, key={result_key}")
        verify = r.get(result_key)
        logger.info(f"Redis 검증: {'저장됨' if verify else '저장실패!'}")
        logger.info(f"처리 완료: request_id={request_id}")

    except Exception as e:
        logger.error(f"처리 실패: request_id={request_id}, error={e}")
        r.setex(result_key, RESULT_TTL, json.dumps({
            "status": "error",
            "answer": "답변 생성 중 오류가 발생했습니다. 다시 시도해주세요.",
            "sources": [],
        }))


def main():
    logger.info("=== Chat Consumer Worker 시작 ===")
    r = get_redis()
    consumer = get_consumer()

    logger.info(f"토픽 구독 중: {KAFKA_TOPIC}")

    for message in consumer:
        try:
            msg = message.value
            logger.info(f"메시지 수신: offset={message.offset}, request_id={msg.get('request_id')}")
            process_message(msg, r)
        except Exception as e:
            logger.error(f"메시지 처리 오류: {e}")
            continue


if __name__ == "__main__":
    main()