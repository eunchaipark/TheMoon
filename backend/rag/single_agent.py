import logging
import time
from langchain.tools import Tool
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_community.tools.tavily_search import TavilySearchResults
from langchain.agents import AgentExecutor, create_tool_calling_agent

from rag.retrieve import retrieve as vector_retrieve, retrieve_by_category
from repository import feed_repo
from core.config import settings

logger = logging.getLogger(__name__)

llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    google_api_key=settings.GEMINI_API_KEY,
    temperature=0.3,
)


def build_all_tools(user_id: int):
    def search_all(query: str) -> str:
        chunks = vector_retrieve(query, user_id, top_k=5)
        if not chunks:
            return "관련 뉴스를 찾지 못했습니다."
        return "\n\n".join([f"[{c['source_name']}] {c['title']}\n{c['content']}" for c in chunks[:5]])

    def make_category_search(category_name: str):
        def _search(query: str) -> str:
            chunks = retrieve_by_category(query, category_name, top_k=5)
            if not chunks:
                return f"{category_name} 관련 뉴스를 찾지 못했습니다."
            return "\n\n".join([f"[{c['source_name']}] {c['title']}\n{c['content']}" for c in chunks])
        return _search

    search_politics = make_category_search("정치")
    search_economy = make_category_search("경제")
    search_society = make_category_search("사회")

    def sentiment(category: str) -> str:
        chunks = vector_retrieve(f"{category} 최신 동향", user_id, top_k=10)
        cat_chunks = [c for c in chunks if c.get('category_name') == category]
        if not cat_chunks:
            return f"{category} 카테고리 뉴스를 찾지 못했습니다."
        titles = [c['title'] for c in cat_chunks[:5]]
        return f"{category} 감성 분석 대상:\n" + "\n".join(f"- {t}" for t in titles)

    def trending(query: str = "") -> str:
        articles = feed_repo.get_trending_articles(limit=5)
        if not articles:
            return "현재 화제 기사가 없습니다."
        return "\n\n".join([f"[{a['category_name']}] {a['title']}" for a in articles])

    def related(query: str) -> str:
        chunks = vector_retrieve(query, user_id, top_k=3)
        if not chunks:
            return "관련 뉴스를 찾지 못했습니다."
        return "\n".join([f"- [{c['source_name']}] {c['title']}" for c in chunks])

    return [
        Tool(name="news_search_all",      func=search_all,      description="전체 카테고리 뉴스 DB 검색"),
        Tool(name="news_search_politics", func=search_politics, description="정치 카테고리 뉴스 DB 검색"),
        Tool(name="news_search_economy",  func=search_economy,  description="경제 카테고리 뉴스 DB 검색"),
        Tool(name="news_search_society",  func=search_society,  description="사회 카테고리 뉴스 DB 검색"),
        Tool(name="sentiment_analysis",   func=sentiment,       description="카테고리별 뉴스 감성 분석"),
        Tool(name="trending_news",        func=trending,        description="현재 화제 기사 조회"),
        Tool(name="related_news",         func=related,         description="관련 뉴스 추가 검색"),
        TavilySearchResults(max_results=2, description="실시간 웹 검색, DB에 없는 최신 정보 조회"),
    ]


SYSTEM_PROMPT = """당신은 뉴스 어시스턴트입니다. 아래 8개 도구 중 질문에 가장 적합한 것을 선택해서 답변하세요.

- news_search_all: 전체 카테고리 뉴스 검색
- news_search_politics: 정치 뉴스 검색
- news_search_economy: 경제 뉴스 검색
- news_search_society: 사회 뉴스 검색
- sentiment_analysis: 카테고리별 감성 분석
- trending_news: 현재 화제 기사
- related_news: 관련 뉴스 추가 검색
- tavily_search_results_json: 실시간 웹 검색

질문에 맞는 도구를 정확히 선택하고, 검색 결과를 바탕으로 정확하게 답변하세요."""

PROMPT = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_PROMPT),
    MessagesPlaceholder(variable_name="chat_history"),
    ("human", "{input}"),
    MessagesPlaceholder(variable_name="agent_scratchpad"),
])


def answer_single(query: str, user_id: int, history: list = None) -> dict:
    """단일 에이전트 답변 생성 (비교 실험용)"""
    tools = build_all_tools(user_id)
    agent = create_tool_calling_agent(llm, tools, PROMPT)
    executor = AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=False,
        max_iterations=4,
        max_execution_time=60,
        handle_parsing_errors=True,
        return_intermediate_steps=True,
    )

    start = time.time()
    result = executor.invoke({"input": query, "chat_history": history or []})
    elapsed = time.time() - start

    tools_used = []
    for step in result.get("intermediate_steps", []):
        action = step[0]
        tools_used.append(action.tool)

    return {
        "answer": result.get("output", ""),
        "tools_used": tools_used,
        "elapsed": elapsed,
    }