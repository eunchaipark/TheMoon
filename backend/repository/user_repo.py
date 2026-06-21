from core.database import get_connection


def get_user_by_email(email: str) -> dict | None:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
                    SELECT user_id, email, password_hash, nickname, created_at
                    FROM users
                    WHERE email = %s
                    """, (email,))
        row = cur.fetchone()
        if not row:
            return None
        cols = [desc[0] for desc in cur.description]
        return dict(zip(cols, row))
    finally:
        conn.close()


def create_user(email: str, password_hash: str, nickname: str) -> dict:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
                    INSERT INTO users (email, password_hash, nickname)
                    VALUES (%s, %s, %s) RETURNING user_id, email, nickname, created_at
                    """, (email, password_hash, nickname))
        conn.commit()
        row = cur.fetchone()
        cols = [desc[0] for desc in cur.description]
        return dict(zip(cols, row))
    finally:
        conn.close()


def get_category_prefs(user_id: int) -> list[dict]:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
                    SELECT ucp.pref_id, ucp.category_id, c.name AS category_name, ucp.weight
                    FROM user_category_prefs ucp
                             JOIN categories c ON ucp.category_id = c.category_id
                    WHERE ucp.user_id = %s
                    ORDER BY ucp.category_id
                    """, (user_id,))
        rows = cur.fetchall()
        cols = [desc[0] for desc in cur.description]
        return [dict(zip(cols, row)) for row in rows]
    finally:
        conn.close()


def upsert_category_prefs(user_id: int, prefs: list[dict]) -> None:
    conn = get_connection()
    try:
        cur = conn.cursor()
        for pref in prefs:
            cur.execute("""
                        INSERT INTO user_category_prefs (user_id, category_id, weight)
                        VALUES (%s, %s, %s) ON CONFLICT (user_id, category_id)
                DO
                        UPDATE SET weight = EXCLUDED.weight
                        """, (user_id, pref['category_id'], pref['weight']))
        conn.commit()
    finally:
        conn.close()
