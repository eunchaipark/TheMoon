from core.database import get_connection


def get_or_create_session(user_id: int, session_id: str) -> str:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
                    INSERT INTO chat_sessions (session_id, user_id)
                    VALUES (%s, %s) ON CONFLICT (session_id) DO
                    UPDATE SET updated_at = NOW() RETURNING session
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


