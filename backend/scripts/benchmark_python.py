"""
순수 Python 임베딩 벤치마크 스크립트
Spark와 처리 시간 비교용
"""

import sys
import os
import re
import time

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sentence_transformers import SentenceTransformer
from core.database import get_connection

MODEL_NAME  = "jhgan/ko-sroberta-multitask"
MAX_CHUNK_LEN = 200
OVERLAP       = 30


def chunk_text(text: str) -> list[str]:
    if not text or not text.strip():
        return []
    sentences = re.split(r'(?<=[.!?。])\s+', text.strip())
    chunks, current = [], ""
    for sent in sentences:
        sent = sent.strip()
        if not sent:
            continue
        if len(sent) > MAX_CHUNK_LEN:
            if current:
                chunks.append(current.strip())
                current = ""
            for i in range(0, len(sent), MAX_CHUNK_LEN - OVERLAP):
                piece = sent[i: i + MAX_CHUNK_LEN]
                if piece.strip():
                    chunks.append(piece.strip())
            continue
        if len(current) + len(sent) + 1 > MAX_CHUNK_LEN:
            if current:
                chunks.append(current.strip())
            current = (current[-OVERLAP:] + " " + sent).strip() if OVERLAP and current else sent
        else:
            current = (current + " " + sent).strip() if current else sent
    if current.strip():
        chunks.append(current.strip())
    return chunks


def main():
    total_start = time.time()

    print("=" * 50)
    print("순수 Python 임베딩 벤치마크 시작")
    print("=" * 50)

    # 1. 모델 로드
    t0 = time.time()
    print(f"\n[1/4] 모델 로딩: {MODEL_NAME}")
    model = SentenceTransformer(MODEL_NAME)
    print(f"      완료: {time.time() - t0:.1f}초")

    # 2. 미처리 기사 조회
    t0 = time.time()
    print("\n[2/4] 미처리 기사 조회 중...")
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT article_id, title, description
        FROM articles
        WHERE is_processed = false
          AND is_duplicate = false
          AND description IS NOT NULL
          AND length(description) >= 20
        ORDER BY published_at DESC
        LIMIT 5000
    """)
    articles = cur.fetchall()
    print(f"      대상 기사: {len(articles)}건 ({time.time() - t0:.1f}초)")

    # 3. 청킹
    t0 = time.time()
    print("\n[3/4] 청킹 중...")
    all_chunks = []
    for article_id, title, description in articles:
        full_text = f"{title}. {description}" if description else title
        chunks = chunk_text(full_text)
        for idx, chunk in enumerate(chunks):
            if len(chunk) > 10:
                all_chunks.append((article_id, idx, chunk))
    print(f"      생성된 청크: {len(all_chunks)}개 ({time.time() - t0:.1f}초)")

    # 4. 임베딩 생성 + DB 저장
    t0 = time.time()
    print("\n[4/4] 임베딩 생성 + DB 저장 중...")
    texts = [c[2] for c in all_chunks]
    embeddings = model.encode(
        texts,
        batch_size=32,
        normalize_embeddings=True,
        show_progress_bar=True,
    )

    saved = 0
    for (article_id, chunk_idx, content), embedding in zip(all_chunks, embeddings):
        emb_str = "[" + ",".join(str(v) for v in embedding.tolist()) + "]"
        cur.execute("""
            INSERT INTO article_chunks (article_id, chunk_index, content, embedding)
            VALUES (%s, %s, %s, %s::vector)
            ON CONFLICT DO NOTHING
        """, (article_id, chunk_idx, content, emb_str))
        saved += 1
        if saved % 100 == 0:
            conn.commit()

    conn.commit()
    embed_time = time.time() - t0
    print(f"      완료: {saved}개 저장 ({embed_time:.1f}초)")

    # is_processed 업데이트
    article_ids = [a[0] for a in articles]
    cur.execute(
        "UPDATE articles SET is_processed = true WHERE article_id = ANY(%s)",
        (article_ids,)
    )
    conn.commit()
    conn.close()

    total_time = time.time() - total_start
    print("\n" + "=" * 50)
    print(f"벤치마크 완료")
    print(f"  처리 기사: {len(articles)}건")
    print(f"  생성 청크: {len(all_chunks)}개")
    print(f"  총 소요시간: {total_time:.1f}초 ({total_time/60:.1f}분)")
    print("=" * 50)


if __name__ == "__main__":
    main()