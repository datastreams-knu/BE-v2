# ai/app/main.py
"""AI 서버 진입점."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.middleware.correlation import CorrelationIDMiddleware

configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """AI 서버 라이프사이클.

    Phase 6 이후 이 함수에서:
    - Redis Pub/Sub 클라이언트 생성
    - Pinecone 클라이언트 초기화
    - 임베딩 모델 로드
    - 메타데이터 캐시 초기 적재
    등을 처리할 예정.
    """
    logger.info(
        "ai_server_starting",
        environment=settings.ENVIRONMENT.value,
    )

    yield

    logger.info("ai_server_shutting_down")


app = FastAPI(
    title="KNU Chatbot AI Server",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if not settings.is_production else None,
    redoc_url="/redoc" if not settings.is_production else None,
)

app.add_middleware(CorrelationIDMiddleware)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/ready")
async def ready() -> dict[str, str]:
    """Phase 6에서 Pinecone·Redis 점검 추가 예정."""
    return {"status": "ready"}

@app.