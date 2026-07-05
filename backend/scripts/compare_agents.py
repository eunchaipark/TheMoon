import sys
import os
import time

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rag.single_agent import answer_single
from rag.agent import answer as answer_multi


TEST_CASES = [
    {"question": "오늘 정치 뉴스 보여줘",        "expected_tool": "news_search_politics", "expected_route": "rag",      "user_id": 1},
    {"question": "삼성전자 최신 기사 찾아줘",      "expected_tool": "news_search_all",      "expected_route": "rag",      "user_id": 1},
    {"question": "경제 동향 분석해줘",            "expected_tool": "news_search_economy",  "expected_route": "analysis", "user_id": 1},
    {"question": "최근 사회 이슈 트렌드는?",       "expected_tool": "news_search_society",  "expected_route": "analysis", "user_id": 1},
    {"question": "정치 뉴스 감성 분석해줘",        "expected_tool": "sentiment_analysis",   "expected_route": "analysis", "user_id": 1},
    {"question": "지금 화제되는 뉴스 뭐야?",       "expected_tool": "trending_news",        "expected_route": "rag",      "user_id": 1},
    {"question": "지금 달러 환율 얼마야?",         "expected_tool": "tavily_search_results_json", "expected_route": "web", "user_id": 1},
    {"question": "오늘 날씨 어때?",                "expected_tool": "tavily_search_results_json", "expected_route": "web", "user_id": 1},
]


def run_single_agent_test():
    print("\n" + "=" * 60)
    print("단일 에이전트 (Baseline) 테스트")
    print("=" * 60)

    results = []
    correct_tool = 0

    for i, case in enumerate(TEST_CASES):
        if i > 0:
            time.sleep(20)

        print(f"\n[{i+1}/8] {case['question']}")
        try:
            result = answer_single(case["question"], case["user_id"])
            tools_used = result["tools_used"]
            elapsed = result["elapsed"]
            answer_len = len(result["answer"])

            tool_ok = case["expected_tool"] in tools_used
            if tool_ok:
                correct_tool += 1

            print(f"  사용된 툴: {tools_used}")
            print(f"  정답 툴: {case['expected_tool']} → {'good' if tool_ok else 'fail'}")
            print(f"  응답 시간: {elapsed:.1f}s")
            print(f"  답변 길이: {answer_len}자")

            results.append({
                "question": case["question"],
                "tools_used": tools_used,
                "tool_correct": tool_ok,
                "elapsed": elapsed,
                "answer_len": answer_len,
                "num_tools_used": len(tools_used),
            })
        except Exception as e:
            print(f"  오류: {e}")
            results.append({
                "question": case["question"],
                "tools_used": [],
                "tool_correct": False,
                "elapsed": 0,
                "answer_len": 0,
                "num_tools_used": 0,
            })

    accuracy = correct_tool / len(TEST_CASES) * 100
    avg_time = sum(r["elapsed"] for r in results) / len(results)
    avg_len  = sum(r["answer_len"] for r in results) / len(results)
    avg_tools = sum(r["num_tools_used"] for r in results) / len(results)

    print(f"\n--- 단일 에이전트 요약 ---")
    print(f"툴 선택 정확도: {correct_tool}/{len(TEST_CASES)} = {accuracy:.1f}%")
    print(f"평균 응답 시간: {avg_time:.1f}s")
    print(f"평균 답변 길이: {avg_len:.0f}자")
    print(f"평균 사용 툴 개수: {avg_tools:.1f}개")

    return {
        "accuracy": accuracy,
        "avg_time": avg_time,
        "avg_len": avg_len,
        "avg_tools": avg_tools,
        "results": results,
    }


def run_multi_agent_test():
    print("\n" + "=" * 60)
    print("멀티 에이전트 (LangGraph) 테스트")
    print("=" * 60)

    from rag.agent import router_node, AgentState

    results = []
    correct_route = 0

    for i, case in enumerate(TEST_CASES):
        if i > 0:
            time.sleep(13)

        print(f"\n[{i+1}/8] {case['question']}")
        try:
            start = time.time()
            result = answer_multi(case["question"], case["user_id"], [])
            elapsed = time.time() - start
            answer_len = len(result["answer"])

            # Router 분류 별도 확인
            state = AgentState(
                question=case["question"], user_id=case["user_id"], chat_history=[],
                route="rag", slot_filled=True, slot_question=None, missing_info=None,
                agent_answer="", final_answer="", quality_score=0.0, retry_count=0, sources=[],
            )
            route_result = router_node(state)
            actual_route = route_result["route"]
            route_ok = actual_route == case["expected_route"]
            if route_ok:
                correct_route += 1

            print(f"  Router 분류: {actual_route} (정답: {case['expected_route']}) → {'good' if route_ok else 'fail'}")
            print(f"  응답 시간: {elapsed:.1f}s")
            print(f"  답변 길이: {answer_len}자")

            results.append({
                "question": case["question"],
                "route": actual_route,
                "route_correct": route_ok,
                "elapsed": elapsed,
                "answer_len": answer_len,
            })
        except Exception as e:
            print(f"  fail 오류: {e}")
            results.append({
                "question": case["question"], "route": "error",
                "route_correct": False, "elapsed": 0, "answer_len": 0,
            })

    accuracy = correct_route / len(TEST_CASES) * 100
    avg_time = sum(r["elapsed"] for r in results) / len(results)
    avg_len  = sum(r["answer_len"] for r in results) / len(results)

    print(f"\n--- 멀티 에이전트 요약 ---")
    print(f"Router 분류 정확도: {correct_route}/{len(TEST_CASES)} = {accuracy:.1f}%")
    print(f"평균 응답 시간: {avg_time:.1f}s")
    print(f"평균 답변 길이: {avg_len:.0f}자")

    return {
        "accuracy": accuracy,
        "avg_time": avg_time,
        "avg_len": avg_len,
        "results": results,
    }


def print_comparison(single_result: dict, multi_result: dict):
    print("\n" + "=" * 60)
    print("최종 비교 결과")
    print("=" * 60)
    print(f"{'지표':<20}{'단일 에이전트':<18}{'멀티 에이전트':<18}")
    print("-" * 56)
    print(f"{'선택/분류 정확도':<20}{single_result['accuracy']:.1f}%{'':<13}{multi_result['accuracy']:.1f}%")
    print(f"{'평균 응답 시간':<20}{single_result['avg_time']:.1f}s{'':<14}{multi_result['avg_time']:.1f}s")
    print(f"{'평균 답변 길이':<20}{single_result['avg_len']:.0f}자{'':<13}{multi_result['avg_len']:.0f}자")
    print(f"{'평균 사용 툴 개수':<20}{single_result['avg_tools']:.1f}개{'':<14}{'1개 (전담 에이전트)':<10}")
    print("=" * 60)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", choices=["single", "multi", "both"], default="both")
    args = parser.parse_args()

    single_result = None
    multi_result = None

    if args.only in ("single", "both"):
        single_result = run_single_agent_test()

    if args.only in ("multi", "both"):
        if args.only == "both":
            print("\n 다음 테스트 전 60초 대기 (rate limit 방지)...")
            time.sleep(60)
        multi_result = run_multi_agent_test()

    if single_result and multi_result:
        print_comparison(single_result, multi_result)