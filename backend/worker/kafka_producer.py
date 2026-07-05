import json
import logging
import os
import uuid

from kafka import KafkaProducer
from kafka.errors import NoBrokersAvailable

logger = logging.getLogger(__name__)

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
KAFKA_TOPIC     = "chat_requests"

_producer = None


def get_producer() -> KafkaProducer:
    global _producer
    if _producer is None:
        try:
            _producer = KafkaProducer(
                bootstrap_servers=KAFKA_BOOTSTRAP,
                value_serializer=lambda v: json.dumps(v, ensure_ascii=False).encode("utf-8"),
                acks="all",
                retries=3,
                linger_ms=5,
            )
            logger.info(f"Kafka Producer 연결 성공: {KAFKA_BOOTSTRAP}")
        except NoBrokersAvailable as e:
            logger.error(f"Kafka Producer 연결 실패: {e}")
            raise
    return _producer


def publish_chat_request(
    user_id: int,
    session_id: str,
    question: str,
    history: list,
) -> str:
    request_id = str(uuid.uuid4())

    message = {
        "request_id": request_id,
        "user_id":    user_id,
        "session_id": session_id,
        "question":   question,
        "history":    history,
    }

    producer = get_producer()
    producer.send(KAFKA_TOPIC, value=message)
    producer.flush()

    logger.info(f"Kafka 발행: request_id={request_id}, question='{question[:30]}'")
    return request_id