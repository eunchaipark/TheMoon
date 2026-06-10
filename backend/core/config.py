import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    POSTGRES_HOST: str = os.getenv("POSTGRES_HOST", "localhost")
    POSTGRES_PORT: int = int(os.getenv("POSTGRES_PORT", "5432"))
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "news_rag")
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "news_user")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "news_password")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    EMBED_MODEL: str = os.getenv("EMBED_MODEL", "jhgan/ko-sroberta-multitask")
    JWT_SECRET_KEY: str = os.getenv("AIRFLOW_SECRET_KEY", "supersecretkey1234567890")
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
settings = Settings()