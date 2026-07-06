import psycopg2
from core.config import settings


def get_connection():
    return psycopg2.connect(
        host=settings.POSTGRES_HOST,
        port=settings.POSTGRES_PORT,
        dbname=settings.POSTGRES_DB,
        user=settings.POSTGRES_USER,
        password=settings.POSTGRES_PASSWORD,
    )


def rows_to_dicts(cur) -> list[dict]:
    rows = cur.fetchall()
    cols = [desc[0] for desc in cur.description]
    return [dict(zip(cols, row)) for row in rows]