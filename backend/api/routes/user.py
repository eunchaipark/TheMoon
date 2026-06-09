from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel

from service import user_service

router = APIRouter(prefix="/users", tags=["users"])

class RegisterRequest(BaseModel):
    email: str
    password: str
    nickname: str
    category_prefs:list[dict] = []

class PrefItem(BaseModel):
    category_id: int
    weight: int

class LoginRequest(BaseModel):
    email: str
    password: str

@router.post("/register")
def register(body: RegisterRequest):
    try:
        return user_service.register(
            body.email,
            body.password,
            body.nickname,
            body.category_prefs
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/login")
def login(body: LoginRequest):
    try:
        return user_service.login(
            body.email,
            body.password
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/prefs/categories")
def get_prefs(authorization: str = Header(...)):
    try:
        token = authorization.replace("Bearer ", "")
        payload = user_service.decode_token(token)
        return user_service.get_category_prefs(payload['user_id'])
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))


@router.post("/prefs/categories")
def update_prefs(prefs: list[PrefItem], authorization: str = Header(...)):
    try:
        token = authorization.replace("Bearer ", "")
        payload = user_service.decode_token(token)
        user_service.update_category_prefs(payload['user_id'], [p.dict() for p in prefs])
        return {"success": True}
    except Exception as e:
        print(f"update_prefs error: {e}")
        raise HTTPException(status_code=401, detail=str(e))