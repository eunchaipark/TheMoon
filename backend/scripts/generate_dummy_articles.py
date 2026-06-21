"""
벤치마크용 더미 기사 대량 생성 스크립트
"""

import sys
import os
import random

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import get_connection
from datetime import datetime, timedelta

TITLES = [
    "국회 예산안 처리 논의 본격화", "한국은행 기준금리 동결 결정",
    "삼성전자 분기 영업이익 신기록", "수도권 집중호우 피해 복구",
    "대통령실 외교 성과 발표", "코스피 사상 최고치 경신",
    "전국 의료파업 장기화 우려", "반도체 수출 호조세 지속",
    "여야 정기국회 일정 합의", "부동산 시장 안정화 대책 발표",
    "무역수지 흑자 전환 성공", "기업 투자 확대 촉구 회의",
    "사회적 거리두기 완화 검토", "중소기업 지원 정책 강화",
    "교육부 입시제도 개편안 발표", "환율 안정세 유지 전망",
]

DESCRIPTIONS = [
    "정부와 여야가 핵심 쟁점을 두고 막판 협상을 이어가고 있다. 관련 부처는 신속한 처리를 촉구하며 다양한 방안을 검토 중이다.",
    "전문가들은 이번 결정이 경제 전반에 미칠 영향을 면밀히 분석하고 있다. 시장은 당분간 관망세를 유지할 것으로 보인다.",
    "업계에서는 이번 성과가 향후 글로벌 경쟁력 강화에 기여할 것으로 기대하고 있다. 추가 투자 계획도 검토 중인 것으로 알려졌다.",
    "피해 지역 주민들은 신속한 복구 지원을 요청하고 있다. 행정기관은 인력과 장비를 총동원해 복구 작업에 나서고 있다.",
    "이번 발표는 국내외 관계자들의 큰 주목을 받고 있다. 후속 조치에 대한 구체적인 계획도 곧 공개될 예정이다.",
]

def main():
    TARGET = 5000
    conn = get_connection()
    cur = conn.cursor()

    # 현재 기사 수 확인
    cur.execute("SELECT COUNT(*) FROM articles")
    current = cur.fetchone()[0]
    need = max(0, TARGET - current)

    print(f"현재 기사 수: {current}건")
    print(f"추가 생성할 기사 수: {need}건")

    if need == 0:
        print("이미 충분한 기사가 있어요.")
        conn.close()
        return

    # source_id 목록 조회
    cur.execute("SELECT source_id, category_id FROM news_sources")
    sources = cur.fetchall()

    inserted = 0
    base_time = datetime.now() - timedelta(days=30)

    for i in range(need):
        source_id, category_id = random.choice(sources)
        title = random.choice(TITLES) + f" {i+1}호"
        description = random.choice(DESCRIPTIONS)
        url = f"https://dummy-news.com/article/{current + i + 1}"
        published_at = base_time + timedelta(
            seconds=random.randint(0, 30 * 24 * 3600)
        )

        cur.execute("""
            INSERT INTO articles (source_id, category_id, title, description, url, published_at)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (url) DO NOTHING
        """, (source_id, category_id, title, description, url, published_at))

        inserted += 1
        if inserted % 500 == 0:
            conn.commit()
            print(f"  {inserted}건 삽입 완료...")

    conn.commit()
    conn.close()

    print(f"\n완료! {inserted}건 추가됨")
    print(f"총 기사 수: {current + inserted}건")


if __name__ == "__main__":
    main()