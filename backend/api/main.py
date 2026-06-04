from fastapi import FastAPI

app = FastAPI(
    title="News RAG Chatbot API",
    description="실시간 개인화 뉴스 피드 및 RAG 챗봇 시스템",
    version="0.1.0"
)

@app.get("/")
def root():
    return {"status": "ok"}

@app.get("/health")
def health():
    return {"status": "healthy"}