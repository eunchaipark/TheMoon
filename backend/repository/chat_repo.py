from core.database import get_connection

def get_or_create_session(user_id: int, session_id: str) -> str:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
                    INSERT INTO chat_sessions (session_id, user_id)
                    VALUES (%s, %s) ON CONFLICT (session_id) DO
                    UPDATE SET updated_at = NOW()
                        RETURNING session_id
                    """, (session_id, user_id))
        conn.commit()
        return cur.fetchone()[0]
    finally:
        conn.close()


def get_history(session_id: str, limit: int = 6) -> list[dict]:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
                    SELECT chat_id, role, message, created_at
                    FROM chat_history
                    WHERE session_id = %s
                    ORDER BY created_at DESC
                        LIMIT %s
                    """, (session_id, limit))
        rows = cur.fetchall()
        cols = [desc[0] for desc in cur.description]
        return list(reversed([dict(zip(cols, row)) for row in rows]))
    finally:
        conn.close()


def save_message(session_id: str, role: str, message: str) -> int:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
                    INSERT INTO chat_history (session_id, role, message)
                    VALUES (%s, %s, %s) RETURNING chat_id
                    """, (session_id, role, message))
        conn.commit()
        return cur.fetchone()[0]
    finally:
        conn.close()


def save_sources(chat_id: int, sources: list[dict]) -> None:
    conn = get_connection()
    try:
        cur = conn.cursor()
        for i, source in enumerate(sources):
            cur.execute("""
                        INSERT INTO chat_sources (chat_id, article_id, rank, similarity)
                        VALUES (%s, %s, %s, %s)
                        """, (chat_id, source['article_id'], i + 1, source['similarity']))
        conn.commit()
    finally:
        conn.close()


def get_sessions(user_id: int) -> list[dict]:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
                    SELECT session_id, created_at, updated_at
                    FROM chat_sessions
                    WHERE user_id = %s
                    ORDER BY updated_at DESC
                    """, (user_id,))
        rows = cur.fetchall()
        cols = [desc[0] for desc in cur.description]
        return [dict(zip(cols, row)) for row in rows]
    finally:
        conn.close()
