from typing import AsyncGenerator
from repository import chat_repo
from rag import chatbot


def _prepare_turn(user_id: int, session_id: str, question: str) -> list[dict]:
    chat_repo.get_or_create_session(user_id, session_id)
    history = chat_repo.get_history(session_id, limit=3)
    chat_repo.save_message(session_id, "user", question)
    return history


def chat(user_id: int, session_id: str, question: str) -> dict:
    history = _prepare_turn(user_id, session_id, question)

    result = chatbot.answer(question, user_id, history)

    assistant_chat_id = chat_repo.save_message(session_id, "assistant", result['answer'])
    if result['sources']:
        chat_repo.save_sources(assistant_chat_id, result['sources'])

    return result


async def chat_stream(user_id: int, session_id: str, question: str) -> AsyncGenerator[str, None]:
    history = _prepare_turn(user_id, session_id, question)

    full_answer = ""
    async for chunk in chatbot.answer_stream(question, user_id, history):
        full_answer += chunk
        yield chunk

    chat_repo.save_message(session_id, "assistant", full_answer)


def get_history(session_id: str) -> list[dict]:
    return chat_repo.get_history(session_id, limit=50)


def get_sessions(user_id: int) -> list[dict]:
    return chat_repo.get_sessions(user_id)