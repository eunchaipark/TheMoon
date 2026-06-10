from google import genai
from rag.prompt_builder import build_prompt
from rag.retrieve import retrieve
from core.config import settings

client = genai.Client(api_key=settings.GEMINI_API_KEY)

def answer(query: str, user_id: int, history: list[dict]) -> dict:
    chunks = retrieve(query, user_id, top_k=5)

    if not chunks:
        return {
            "answer": "관련된 최신 뉴스를 찾지 못했어요. 다른 질문을 해보시겠어요?",
            "sources": []
        }

    messages = build_prompt(query, chunks, history)

    full_prompt = "\n\n".join([
        f"[{msg['role'].upper()}]\n{msg['content']}"
        for msg in messages
    ])

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=full_prompt
    )
    answer_text = response.text

    seen = set()
    sources = []
    for chunk in chunks:
        if chunk['article_id'] not in seen:
            seen.add(chunk['article_id'])
            sources.append({
                "article_id":  chunk['article_id'],
                "title":       chunk['title'],
                "url":         chunk['url'],
                "source_name": chunk['source_name'],
                "similarity":  round(float(chunk['similarity']), 3),
            })

    return {
        "answer": answer_text,
        "sources": sources
    }