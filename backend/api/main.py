from fastapi import FastAPI
from api.routes import feed, user
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="News RAG Chatbot API",
    description="실시간 개인화 뉴스 피드 및 RAG 챗봇 시스템",
    version="0.1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(feed.router)
app.include_router(user.router)


@app.get("/")
def root():
    return {"status": "ok"}

@app.get("/health")
def health():
    return {"status": "healthy"}




