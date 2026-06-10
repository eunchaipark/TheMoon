def build_prompt(query: str, chunks: list[dict], history: list[dict]) -> list[dict]:
    context = "\n\n".join([
        f"[{i + 1}] {chunk['title']} ({chunk['source_name']}, {chunk['published_at'].strftime('%Y-%m-%d') if chunk['published_at'] else ''})\n{chunk['content']}"
        for i, chunk in enumerate(chunks)
    ])

    system_prompt = f"""당신은 최신 뉴스를 기반으로 질문에 답변하는 뉴스 어시스턴트입니다.
    아래 뉴스 기사 내용을 참고하여 사용자의 질문에 정확하고 간결하게 답변해주세요.
    뉴스 내용에 없는 정보는 추측하지 말고, 모르는 경우 솔직하게 말해주세요.

    [참고 뉴스]
    {context}"""

    messages = [{"role": "system", "content": system_prompt}]

    # 슬라이딩 윈도우
    for msg in history:
        messages.append({
            "role": msg["role"],
            "content": msg["message"],
        })
    messages.append({"role":"user", "content": query})
    return messages