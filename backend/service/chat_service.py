from repository import chat_repo
from rag import chatbot


def chat(user_id: int, session_id: str, question: str) -> dict:
    chat_repo.get_or_create_session(user_id, session_id)
    history = chat_repo.get_history(session_id, limit=6)
    result = chatbot.answer(question, user_id, history)

    chat_repo.save_message(session_id, "user", question)
    assistant_chat_id = chat_repo.save_message(session_id, "assistant", result['answer'])
    if result['sources']:
        chat_repo.save_sources(assistant_chat_id, result['sources'])

    return result


def get_history(session_id: str) -> list[dict]:
    return chat_repo.get_history(session_id, limit=50)


def get_sessions(user_id: int) -> list[dict]:
    return chat_repo.get_sessions(user_id)
