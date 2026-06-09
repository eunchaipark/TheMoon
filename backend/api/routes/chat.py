from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from service import chat_service
from service.user_service import decode_token

router = APIRouter(prefix="/chat", tags=["chat"])

class ChatRequest(BaseModel):
    question: str
    session_id: str



@router.post("")
def chat(body: ChatRequest, authorization: str = Header(...)):
    try:
        token = authorization.replace("Bearer ", "")
        payload = decode_token(token)
        return chat_service.chat(
            user_id=payload['user_id'],
            session_id=body.session_id,
            question=body.question
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))