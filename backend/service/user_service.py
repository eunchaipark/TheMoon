import jwt
import bcrypt
from datetime import datetime, timedelta
from repository import user_repo
from core.config import settings

JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = 24


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


def create_token(user_id: int, email: str) -> str:
    payload = {
        "user_id": user_id,
        "email": email,
        "exp": datetime.utcnow() + timedelta(hours=JWT_EXPIRE_HOURS)
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])


def register(email: str, password: str, nickname: str, category_prefs: list[dict]) -> dict:
    existing = user_repo.get_user_by_email(email)
    if existing:
        raise ValueError("이미 사용 중인 이메일이에요")

    password_hash = hash_password(password)
    user = user_repo.create_user(email, password_hash, nickname)

    if category_prefs:
        user_repo.upsert_category_prefs(user['user_id'], category_prefs)

    token = create_token(user['user_id'], user['email'])
    return {
        "user": {
            "user_id": user['user_id'],
            "email": user['email'],
            "nickname": user['nickname'],
        },
        "token": token
    }


def login(email: str, password: str) -> dict:
    user = user_repo.get_user_by_email(email)
    if not user:
        raise ValueError("이메일 또는 비밀번호가 올바르지 않아요")

    if not verify_password(password, user['password_hash']):
        raise ValueError("이메일 또는 비밀번호가 올바르지 않아요")

    token = create_token(user['user_id'], user['email'])
    return {
        "user": {
            "user_id": user['user_id'],
            "email": user['email'],
            "nickname": user['nickname'],
        },
        "token": token
    }


def get_category_prefs(user_id: int) -> list[dict]:
    return user_repo.get_category_prefs(user_id)


def update_category_prefs(user_id: int, prefs: list[dict]) -> None:
    user_repo.upsert_category_prefs(user_id, prefs)