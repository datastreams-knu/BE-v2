# be/app/main.py
from fastapi import FastAPI

app = FastAPI(
    title="KNU Chatbot Backend",
    version="0.1.0",
)

@app.get("/health")
async def health() -> dict[str, str]:
    """Liveness probe — 프로세스가 응답 가능한가"""
    return {"status": "ok"}


@app.get("/health/ready")
async def ready() -> dict[str, str]:
    """Readiness probe — 외부 의존성까지 점검 (Phase 3에서 보강)"""
    # TODO: Phase 3에서 DB·Redis 연결 확인 추가
    return {"status": "ready"}