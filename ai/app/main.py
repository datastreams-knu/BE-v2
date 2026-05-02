# ai/app/main.py
from fastapi import FastAPI

app = FastAPI(
    title="KNU Chatbot AI Server",
    version="0.1.0",
)

@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/ready")
async def ready() -> dict[str, str]:
    # TODO: Redis·Pinecone 연결 확인 추가
    return {"status": "ready"}