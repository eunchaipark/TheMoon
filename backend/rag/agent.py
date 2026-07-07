import logging
import os
import re
from typing import TypedDict, Literal, Optional
from typing import AsyncGenerator

import langchain
from langchain.tools import StructuredTool
from pydantic import BaseModel, Field
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.rate_limiters import InMemoryRateLimiter
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_ollama import ChatOllama
from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_community.cache import RedisCache
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langgraph.graph import StateGraph, END
import redis

from rag.retrieve import retrieve as vector_retrieve
from core.config import settings

logger = logging.getLogger(__name__)

os.environ.setdefault("LANGCHAIN_TRACING_V2", "true")
os.environ.setdefault("LANGCHAIN_PROJECT", settings.LANGCHAIN_PROJECT)
if settings.LANGCHAIN_API_KEY:
    os.environ.setdefault("LANGCHAIN_API_KEY", settings.LANGCHAIN_API_KEY)

_redis_client = None

def get_redis_client():
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.Redis(
            host=os.getenv("REDIS_HOST", "redis"),
            port=int(os.getenv("REDIS_PORT", "6379")),
            decode_responses=False,
        )
    return _redis_client

def setup_llm_cache():
    try:
        r = get_redis_client()
        r.ping()
        langchain.llm_cache = RedisCache(r, ttl=86400)
        logger.info("Redis 캐시 연결 성공 (정확 일치 캐시)")
    except Exception as e:
        logger.warning(f"Redis 연결 실패, 캐시 비활성화: {e}")

setup_llm_cache()



# Warm-up: 워커 시작 시 모델 사전 로딩
def warmup():
    try:
        from rag.retrieve import get_model
        model = get_model()
        model.encode(["warm-up"], normalize_embeddings=True)
        logger.info("Warm-up 완료: 임베딩 모델 사전 로딩")
    except Exception as e:
        logger.warning(f"Warm-up 실패 (무시): {e}")

warmup()


# 미들웨어 2: Rate Limiter
rate_limiter = InMemoryRateLimiter(
    requests_per_second=0.08,
    check_every_n_seconds=0.1,
    max_bucket_size=5,
)



# 미들웨어 3: Safety Filter
BLOCKED_PATTERNS = [
    "주식 매수 추천", "투자 조언", "종목 추천",
    "개인정보", "비밀번호", "해킹",
]

def safety_filter(query: str) -> str | None:
    for pattern in BLOCKED_PATTERNS:
        if pattern in query:
            return f"'{pattern}' 관련 요청은 처리할 수 없습니다. 뉴스 정보 제공만 가능합니다."
    return None


# 미들웨어 4: 중복 질문 감지
def duplicate_check(user_id: int, query: str) -> str | None:
    try:
        r = get_redis_client()
        key = f"last_query:{user_id}"
        last = r.get(key)
        if last and last.decode("utf-8") == query:
            logger.info(f"중복 질문 감지: user={user_id}")
            return "동일한 질문을 너무 빠르게 반복하고 있어요. 잠시 후 다시 시도해주세요."
        r.set(key, query.encode("utf-8"), ex=3)
    except Exception as e:
        logger.warning(f"중복 감지 실패 (무시): {e}")
    return None



# 미들웨어 5: 응답 품질 로깅
def log_quality(user_id: int, query: str, answer: str, score: float, route: str) -> None:
    try:
        if score < 0.4:
            r = get_redis_client()
            import json, time
            log_entry = json.dumps({
                "user_id":  user_id,
                "query":    query,
                "answer":   answer[:200],
                "score":    score,
                "route":    route,
                "ts":       int(time.time()),
            }, ensure_ascii=False)
            r.lpush("quality_logs:low", log_entry)
            r.ltrim("quality_logs:low", 0, 99)
            logger.warning(f"낮은 품질 답변 로깅: score={score:.1f}, route={route}, query='{query[:30]}'")
    except Exception as e:
        logger.warning(f"품질 로깅 실패 (무시): {e}")


def make_llm(temperature: float = 0.3):
    return ChatOllama(
        model=settings.OLLAMA_MODEL,
        base_url=settings.OLLAMA_BASE_URL,
        temperature=temperature,
    )

def make_web_llm(temperature: float = 0.3):
    return ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        google_api_key=settings.GEMINI_API_KEY,
        temperature=temperature,
        rate_limiter=rate_limiter,
    )

router_llm   = make_llm(temperature=0)
slot_llm     = make_llm(temperature=0)
rag_llm      = make_llm(temperature=0.3)
analysis_llm = make_llm(temperature=0.3)
web_llm      = make_web_llm(temperature=0.3)
summary_llm  = make_llm(temperature=0.2)


class AgentState(TypedDict):
    question: str
    user_id: int
    chat_history: list[BaseMessage]
    route: Literal["rag", "analysis", "web", "fallback"]
    slot_filled: bool
    slot_question: Optional[str]
    missing_info: Optional[str]
    agent_answer: str
    final_answer: str
    quality_score: float
    retry_count: int
    sources: list[dict]


CATEGORY_MAP = {
    "all":      {"ko": None,   "label": "전체"},
    "politics": {"ko": "정치", "label": "정치"},
    "economy":  {"ko": "경제", "label": "경제"},
    "society":  {"ko": "사회", "label": "사회"},
}

class SearchQueryInput(BaseModel):
    query: str = Field(description="검색할 키워드 또는 질문 문장")

def make_rag_search_tool(user_id: int, category_key: str = "all"):
    cat    = CATEGORY_MAP.get(category_key, CATEGORY_MAP["all"])
    ko_name = cat["ko"]
    label   = cat["label"]

    def _search(query: str) -> str:
        chunks = vector_retrieve(query, user_id, top_k=5)
        if ko_name:
            chunks = [c for c in chunks if c.get('category_name') == ko_name]
        if not chunks:
            return f"{label} 관련 뉴스를 찾지 못했습니다."
        results = []
        seen = set()
        for chunk in chunks:
            if chunk['article_id'] not in seen:
                seen.add(chunk['article_id'])
                pub = chunk['published_at'].strftime('%Y-%m-%d') if chunk.get('published_at') else ''
                results.append(
                    f"[{chunk['source_name']} / {pub}] {chunk['title']}\n"
                    f"내용: {chunk['content']}\n"
                    f"URL: {chunk['url']}"
                )
        return "\n\n".join(results)

    return StructuredTool.from_function(
        func=_search,
        name=f"news_rag_search_{category_key}",
        description=f"뉴스 DB에서 {label} 카테고리 기사를 벡터 검색합니다.",
        args_schema=SearchQueryInput,
    )


def _format_chunks(chunks: list[dict]) -> str:
    if not chunks:
        return "관련 뉴스를 찾지 못했습니다."
    lines = []
    seen = set()
    for chunk in chunks:
        if chunk['article_id'] not in seen:
            seen.add(chunk['article_id'])
            pub = chunk['published_at'].strftime('%Y-%m-%d') if chunk.get('published_at') else ''
            lines.append(
                f"[{chunk['source_name']} / {pub}] {chunk['title']}\n"
                f"내용: {chunk['content']}\n"
                f"URL: {chunk['url']}"
            )
    return "\n\n".join(lines)


CATEGORY_KEYWORDS = {"정치": "politics", "경제": "economy", "사회": "society"}

def _infer_category(question: str) -> str | None:
    for ko in CATEGORY_KEYWORDS:
        if ko in question:
            return ko
    return None


ROUTER_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """사용자 질문을 다음 4가지 중 하나로 분류하세요.

- rag: 뉴스 DB에서 기사를 검색하는 단순 조회 질문
  예) "금리 뉴스 보여줘", "오늘 정치 뉴스는?", "삼성전자 기사 찾아줘"

- analysis: 뉴스를 분석하거나 인사이트/감성/트렌드를 요청하는 질문
  예) "경제 동향 분석해줘", "정치 이슈 감성 분석", "최근 사회 트렌드는?"

- web: DB에 없는 실시간 정보나 최신 속보가 필요한 질문
  예) "오늘 날씨", "지금 환율", "방금 나온 속보"

- fallback: 뉴스와 무관하거나 의도가 불명확한 질문
  예) "안녕", "뭐 먹을까", "심심해", "ㅋㅋ"

반드시 rag, analysis, web, fallback 중 하나만 답하세요."""),
    ("human", "{question}")
])



# Slot Filling 프롬프트
# raw JSON만 반환하도록 명시 → 파싱 실패 방지

SLOT_FILLING_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """사용자의 뉴스 질문에서 필요한 정보가 충분한지 판단하세요.

분류 기준:
- "뉴스 요약해줘", "분석해줘", "보여줘" 처럼 대상이 없으면 → 부족
- "정치 뉴스 요약해줘", "삼성전자 분석해줘" 처럼 대상이 명확하면 → 충분

반드시 아래 형식의 raw JSON만 반환하세요.
마크다운 코드블록(```), 설명, 줄바꿈 없이 JSON만 출력하세요.

충분한 경우: {{"sufficient": true}}
부족한 경우: {{"sufficient": false, "ask": "사용자에게 물어볼 질문"}}

예시:
- "뉴스 요약해줘" → {{"sufficient": false, "ask": "어떤 카테고리 뉴스를 요약해드릴까요? (정치/경제/사회)"}}
- "분석해줘" → {{"sufficient": false, "ask": "어떤 분야를 분석해드릴까요? (정치/경제/사회)"}}
- "삼성전자 최근 뉴스 요약해줘" → {{"sufficient": true}}
- "경제 동향 분석해줘" → {{"sufficient": true}}"""),
    ("human", "질문: {question}\n분류: {route}")
])

AGENT_PROMPT = ChatPromptTemplate.from_messages([
    ("system", "{system_message}"),
    MessagesPlaceholder(variable_name="chat_history"),
    ("human", "{input}"),
    MessagesPlaceholder(variable_name="agent_scratchpad"),
])

RAG_ANSWER_PROMPT = ChatPromptTemplate.from_messages([
    ("system", "당신은 뉴스 검색 전문 에이전트입니다. 아래 뉴스 기사를 참고하여 질문에 정확하게 답하세요. "
               "기사에 없는 내용은 추측하지 말고 모른다고 답하세요.\n\n[참고 뉴스]\n{context}"),
    ("human", "{question}"),
])

ANALYSIS_ANSWER_PROMPT = ChatPromptTemplate.from_messages([
    ("system", "당신은 뉴스 분석 전문 에이전트입니다. 아래 뉴스 기사를 참고하여 질문에 대한 감성/트렌드/인사이트를 분석해 답하세요.\n\n[참고 뉴스]\n{context}"),
    ("human", "{question}"),
])



def router_node(state: AgentState) -> AgentState:
    chain = ROUTER_PROMPT | router_llm
    result = chain.invoke({"question": state["question"]})
    route_text = result.content.strip().lower()

    if "fallback" in route_text:
        route = "fallback"
    elif "analysis" in route_text:
        route = "analysis"
    elif "web" in route_text:
        route = "web"
    else:
        route = "rag"

    logger.info(f"Router: '{state['question'][:30]}' → {route}")
    return {**state, "route": route}


def slot_filling_node(state: AgentState) -> AgentState:
    import json

    chain = SLOT_FILLING_PROMPT | slot_llm
    result = chain.invoke({
        "question": state["question"],
        "route": state["route"],
    })

    try:
        text = result.content.strip()

        if "```" in text:
            text = re.sub(r"```(?:json)?", "", text).strip()

        match = re.search(r'\{.*?\}', text, re.DOTALL)
        if match:
            text = match.group(0)

        parsed = json.loads(text)

        if parsed.get("sufficient", True):
            logger.info("Slot Filling: 정보 충분 → 에이전트 진행")
            return {**state, "slot_filled": True, "slot_question": None}
        else:
            ask = parsed.get("ask", "좀 더 구체적으로 말씀해주시겠어요?")
            logger.info(f"Slot Filling: 정보 부족 → '{ask}'")
            return {**state, "slot_filled": False, "slot_question": ask}
    except Exception as e:
        logger.warning(f"Slot Filling 파싱 실패: {e}, 기본값으로 진행")
        return {**state, "slot_filled": True, "slot_question": None}


def fallback_node(state: AgentState) -> AgentState:
    question = state["question"]

    greetings = ["안녕", "hi", "hello", "ㅎㅇ"]
    if any(g in question.lower() for g in greetings):
        answer = "안녕하세요! 저는 뉴스 챗봇이에요. 정치, 경제, 사회 뉴스에 대해 무엇이든 질문해보세요! 😊"
    else:
        answer = (
            "죄송해요, 질문의 의도를 파악하기 어려웠어요.\n\n"
            "저는 뉴스 관련 질문에 답변드릴 수 있어요:\n"
            "- 📰 **뉴스 검색**: '오늘 정치 뉴스 보여줘'\n"
            "- 📊 **트렌드 분석**: '경제 동향 분석해줘'\n"
            "- 🔍 **실시간 정보**: '지금 환율 알려줘'\n\n"
            "다시 질문해주시겠어요?"
        )

    logger.info(f"Fallback 처리: '{question[:30]}'")
    return {**state, "agent_answer": answer, "final_answer": answer, "quality_score": 1.0}


def _run_agent(llm, tools, system_message, state, max_time=30, max_iter=3):
    prompt = AGENT_PROMPT.partial(system_message=system_message)
    agent = create_tool_calling_agent(llm, tools, prompt)
    executor = AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=False,
        max_iterations=max_iter,
        max_execution_time=max_time,
        handle_parsing_errors=True,
    )
    return executor.invoke({
        "input": state["question"],
        "chat_history": state["chat_history"],
    })


def rag_agent_node(state: AgentState) -> AgentState:
    user_id = state["user_id"]
    question = state["question"]
    chunks = vector_retrieve(question, user_id, top_k=5)
    chain = RAG_ANSWER_PROMPT | rag_llm
    result = chain.invoke({"question": question, "context": _format_chunks(chunks)})
    sources = _extract_sources(chunks[:3])
    return {**state, "agent_answer": result.content, "sources": sources}


def analysis_agent_node(state: AgentState) -> AgentState:
    user_id = state["user_id"]
    question = state["question"]
    ko_category = _infer_category(question)
    if ko_category:
        chunks = vector_retrieve(f"{ko_category} 최신 동향", user_id, top_k=10)
        chunks = [c for c in chunks if c.get('category_name') == ko_category]
    else:
        chunks = vector_retrieve(question, user_id, top_k=10)
    chain = ANALYSIS_ANSWER_PROMPT | analysis_llm
    result = chain.invoke({"question": question, "context": _format_chunks(chunks[:5])})
    sources = _extract_sources(chunks[:3])
    return {**state, "agent_answer": result.content, "sources": sources}


def web_agent_node(state: AgentState) -> AgentState:
    user_id = state["user_id"]
    tools = [
        TavilySearchResults(max_results=2),
        make_rag_search_tool(user_id, category_key="all"),
    ]
    result = _run_agent(
        web_llm, tools,
        "당신은 실시간 정보 검색 전문 에이전트입니다. 웹 검색으로 최신 정보를 찾고 출처를 명확히 밝히세요.",
        state,
    )
    return {**state, "agent_answer": result.get("output", ""), "sources": []}


def summary_node(state: AgentState) -> AgentState:
    if not state["agent_answer"]:
        return {**state, "final_answer": "답변을 생성하지 못했습니다."}

    if state["route"] in ("web", "fallback"):
        logger.info(f"{state['route']} 라우트: Summary 스킵")
        return {**state, "final_answer": state["agent_answer"]}

    prompt = ChatPromptTemplate.from_messages([
        ("system", "다음 에이전트 답변을 핵심 정보 우선, 중복 제거, 읽기 쉽게 한국어로 정리하세요. 200자 이내로 간결하게."),
        ("human", "에이전트 답변:\n{answer}\n\n원래 질문: {question}")
    ])
    chain = prompt | summary_llm
    result = chain.invoke({"answer": state["agent_answer"], "question": state["question"]})
    return {**state, "final_answer": result.content}


# retry_count 증가 → 무한 재시도 방지
def validate_node(state: AgentState) -> AgentState:
    answer = state.get("final_answer", "")
    score = 0.0
    if len(answer) > 50:  score += 0.4
    if len(answer) > 200: score += 0.2
    if state.get("sources"): score += 0.2
    if "없습니다" not in answer or len(answer) > 100: score += 0.2

    retry_count = state.get("retry_count", 0)
    if score < 0.4:
        retry_count += 1

    logger.info(f"품질 점수: {score:.1f}, retry_count: {retry_count}")
    return {**state, "quality_score": score, "retry_count": retry_count}



def route_by_type(state: AgentState) -> str:
    return state.get("route", "rag")

def check_slot(state: AgentState) -> str:
    if not state.get("slot_filled", True):
        return "need_slot"
    route = state.get("route", "rag")
    return route


# 원래 route로 재시도 → 분석 질문이 rag로 잘못 재시도되던 문제 해결
def check_quality(state: AgentState) -> str:
    if state.get("quality_score", 0) < 0.4 and state.get("retry_count", 0) < 1:
        route = state.get("route", "rag")
        logger.info(f"품질 미달 → {route}로 재시도")
        return route
    return "done"


def slot_response_node(state: AgentState) -> AgentState:
    ask = state.get("slot_question", "좀 더 구체적으로 말씀해주시겠어요?")
    return {**state, "final_answer": ask, "quality_score": 1.0}



def _extract_sources(chunks: list) -> list:
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
    return sources

def convert_history(history: list[dict]) -> list[BaseMessage]:
    messages = []
    for msg in history:
        if msg['role'] == 'user':
            messages.append(HumanMessage(content=msg['message']))
        elif msg['role'] == 'assistant':
            messages.append(AIMessage(content=msg['message']))
    return messages


def _build_initial_state(query: str, user_id: int, history: list[dict]) -> AgentState:
    return AgentState(
        question=query,
        user_id=user_id,
        chat_history=convert_history(history),
        route="rag",
        slot_filled=True,
        slot_question=None,
        missing_info=None,
        agent_answer="",
        final_answer="",
        quality_score=0.0,
        retry_count=0,
        sources=[],
    )


def build_graph():
    graph = StateGraph(AgentState)

    graph.add_node("router",        router_node)
    graph.add_node("slot_filling",  slot_filling_node)
    graph.add_node("slot_response", slot_response_node)
    graph.add_node("fallback",      fallback_node)
    graph.add_node("rag",           rag_agent_node)
    graph.add_node("analysis",      analysis_agent_node)
    graph.add_node("web",           web_agent_node)
    graph.add_node("summary",       summary_node)
    graph.add_node("validate",      validate_node)

    graph.set_entry_point("router")

    graph.add_conditional_edges("router", route_by_type, {
        "rag":      "slot_filling",
        "analysis": "slot_filling",
        "web":      "slot_filling",
        "fallback": "fallback",
    })

    graph.add_conditional_edges("slot_filling", check_slot, {
        "need_slot": "slot_response",
        "rag":       "rag",
        "analysis":  "analysis",
        "web":       "web",
    })

    graph.add_edge("slot_response", "validate")
    graph.add_edge("fallback",      "validate")

    graph.add_edge("rag",      "summary")
    graph.add_edge("analysis", "summary")
    graph.add_edge("web",      "summary")

    graph.add_edge("summary", "validate")

    graph.add_conditional_edges("validate", check_quality, {
        "done":     END,
        "rag":      "rag",
        "analysis": "analysis",
        "web":      "web",
    })

    return graph.compile()


_graph = None

def get_graph():
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph


def answer(query: str, user_id: int, history: list[dict]) -> dict:
    blocked = safety_filter(query)
    if blocked:
        return {"answer": blocked, "sources": []}

    duplicated = duplicate_check(user_id, query)
    if duplicated:
        return {"answer": duplicated, "sources": []}

    graph = get_graph()
    initial_state = _build_initial_state(query, user_id, history)
    try:
        result = graph.invoke(initial_state)
        final = result.get("final_answer") or result.get("agent_answer", "답변을 생성하지 못했습니다.")
        score = result.get("quality_score", 0.0)
        route = result.get("route", "rag")

        log_quality(user_id, query, final, score, route)

        return {"answer": final, "sources": result.get("sources", [])}
    except Exception as e:
        logger.error(f"그래프 실행 실패: {e}")
        return {"answer": "답변 생성 중 오류가 발생했습니다.", "sources": []}


async def answer_stream(query: str, user_id: int, history: list[dict]) -> AsyncGenerator[str, None]:
    blocked = safety_filter(query)
    if blocked:
        yield blocked
        return

    graph = get_graph()
    initial_state = _build_initial_state(query, user_id, history)
    try:
        async for event in graph.astream_events(initial_state, version="v1"):
            kind = event.get("event")
            if kind == "on_chat_model_stream":
                chunk = event.get("data", {}).get("chunk")
                if chunk and hasattr(chunk, "content") and chunk.content:
                    yield chunk.content
    except Exception as e:
        logger.error(f"스트리밍 실패: {e}")
        yield "답변 생성 중 오류가 발생했습니다."