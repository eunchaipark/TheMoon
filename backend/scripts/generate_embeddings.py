# 임시데이터 청크데이터 생성
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sentence_transformers import SentenceTransformer
from core.database import get_connection

MODEL_NAME = "jhgan/ko-sroberta-multitask"

def main():
    print(f"모델 로딩 중: {MODEL_NAME}")
    model = SentenceTransformer(MODEL_NAME)

    conn = get_connection()
    try:
        cur = conn.cursor()

        # 임베딩 없는 청크 조회
        cur.execute("""
            SELECT chunk_id, content
            FROM article_chunks
            WHERE embedding IS NULL
        """)
        chunks = cur.fetchall()
        print(f"임베딩 생성할 청크 수: {len(chunks)}")

        if not chunks:
            print("임베딩할 청크가 없어요.")
            return

        chunk_ids = [row[0] for row in chunks]
        texts = [row[1] for row in chunks]

        print("임베딩 생성 중...")
        embeddings = model.encode(texts, show_progress_bar=True)

        print("DB에 저장 중...")
        for chunk_id, embedding in zip(chunk_ids, embeddings):
            embedding_list = embedding.tolist()
            cur.execute("""
                UPDATE article_chunks
                SET embedding = %s::vector
                WHERE chunk_id = %s
            """, (str(embedding_list), chunk_id))

        conn.commit()
        print(f"완료! {len(chunks)}개 청크 임베딩 저장됨")

    finally:
        conn.close()

if __name__ == "__main__":
    main()