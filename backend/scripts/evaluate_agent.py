import sys
import os
import time

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langsmith import Client
from langsmith.evaluation import evaluate, LangChainStringEvaluator
from langchain_google_genai import ChatGoogleGenerativeAI
from core.config import settings
from rag.agent import answer, get_graph

# LangSmith 클라이언트
client = Client(api_key=settings.LANGCHAIN_API_KEY)

# 평가용 LLM
eval_llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    google_api_key=settings.GEMINI_API_KEY,
    temperature=0,
)

TEST_DATASET = [

    {"question": "최근 금리 관련 뉴스 보여줘",         "expected_route": "rag",      "user_id": 1},
    {"question": "오늘 정치 뉴스는 뭐가 있어?",        "expected_route": "rag",      "user_id": 1},
    {"question": "삼성전자 최신 기사 찾아줘",           "expected_route": "rag",      "user_id": 1},

    {"question": "경제 동향 분석해줘",                 "expected_route": "analysis", "user_id": 1},
    {"question": "정치 뉴스 감성 분석 해줘",            "expected_route": "analysis", "user_id": 1},
    {"question": "최근 사회 이슈 트렌드는 어떻게 돼?",  "expected_route": "analysis", "user_id": 1},


    {"question": "지금 달러 환율 얼마야?",              "expected_route": "web",      "user_id": 1},
    {"question": "오늘 코스피 종가는?",                 "expected_route": "web",      "user_id": 1},
]


def run_agent(inputs: dict) -> dict:
    start = time.time()
    result = answer(
        query=inputs["question"],
        user_id=inputs.get("user_id", 1),
        history=[],
    )
    elapsed = time.time() - start
    return {
        "answer":   result["answer"],
        "sources":  result["sources"],
        "elapsed":  elapsed,
    }


def evaluate_router_accuracy():
    import time
    from rag.agent import router_node, AgentState

    print("\n=== Router 분류 정확도 ===")
    correct = 0
    total = len(TEST_DATASET)

    for i, case in enumerate(TEST_DATASET):
        if i > 0 and i % 4 == 0:
            print("  ⏳ Rate limit 방지를 위해 60초 대기...")
            time.sleep(60)
        else:
            time.sleep(13)  # 분당 5회 = 12초 간격

        state = AgentState(
            question=case["question"],
            user_id=case["user_id"],
            chat_history=[],
            route="rag",
            agent_answer="",
            final_answer="",
            quality_score=0.0,
            retry_count=0,
            sources=[],
        )
        result = router_node(state)
        actual = result["route"]
        expected = case["expected_route"]
        ok = actual == expected
        if ok:
            correct += 1
        print(f"  {'good' if ok else 'fail'} [{expected} → {actual}] {case['question'][:30]}")

    accuracy = correct / total * 100
    print(f"\n  정확도: {correct}/{total} = {accuracy:.1f}%")
    return accuracy


def evaluate_answer_quality():
    print("\n=== 답변 품질 평가 (LangSmith) ===")

    dataset_name = "TheMoon-NewsAgent-Eval"
    try:
        dataset = client.create_dataset(dataset_name, description="뉴스 에이전트 평가 데이터셋")
        for case in TEST_DATASET:
            client.create_example(
                inputs={"question": case["question"], "user_id": case["user_id"]},
                dataset_id=dataset.id,
            )
        print(f"  데이터셋 생성: {dataset_name}")
    except Exception:
        dataset = client.read_dataset(dataset_name=dataset_name)
        print(f"  기존 데이터셋 사용: {dataset_name}")

    evaluators = [
        LangChainStringEvaluator("relevance",   config={"llm": eval_llm}),
        LangChainStringEvaluator("conciseness", config={"llm": eval_llm}),
    ]

    results = evaluate(
        run_agent,
        data=dataset_name,
        evaluators=evaluators,
        experiment_prefix="TheMoon-Agent",
        metadata={"model": "gemini-2.5-flash", "agents": 4},
    )

    print(f"  평가 완료 → LangSmith에서 확인: https://smith.langchain.com")
    return results


def evaluate_response_time():
    print("\n=== 응답 시간 측정 ===")
    times = {"rag": [], "analysis": [], "web": []}

    for case in TEST_DATASET:
        start = time.time()
        answer(query=case["question"], user_id=case["user_id"], history=[])
        elapsed = time.time() - start
        times[case["expected_route"]].append(elapsed)
        print(f"  {case['expected_route']:8s} | {elapsed:.1f}s | {case['question'][:30]}")

    print("\n  평균 응답 시간:")
    for route, t_list in times.items():
        if t_list:
            print(f"  {route:8s}: {sum(t_list)/len(t_list):.1f}s")


if __name__ == "__main__":
    print("=" * 55)
    print("TheMoon 뉴스 에이전트 Harness 평가")
    print("=" * 55)

    # 1. Router 정확도
    accuracy = evaluate_router_accuracy()

    # 2. 응답 시간
    evaluate_response_time()

    # 3. LangSmith 품질 평가
    evaluate_answer_quality()

    print("\n" + "=" * 55)
    print(f"Router 정확도: {accuracy:.1f}%")
    print(f"LangSmith 대시보드: https://smith.langchain.com")
    print("=" * 55)