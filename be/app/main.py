# be/app/main.py
"""FastAPI 애플리케이션 진입점."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.core.exceptions import UserNotFoundError
from app.core.exceptions import register_exception_handlers

from app.db.session import create_engine, dispose_db, init_db
from app.db.redis_client import create_redis
from app.middleware.correlation import CorrelationIDMiddleware

from app.api.v1 import api_router

import httpx

configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    logger.info(
        "app_starting",
        environment=settings.ENVIRONMENT.value,
        log_level=settings.LOG_LEVEL,
    )

    # DB 초기화
    engine = create_engine()
    init_db(engine)
    logger.info("db_initialized")

    # HTTP 클라이언트
    http_client = httpx.AsyncClient(timeout=10.0)
    app.state.http_client = http_client
    logger.info("http_client_initialized")

    # Redis
    redis = create_redis()
    await redis.ping()
    app.state.redis = redis
    logger.info("redis_initialized")


    try:
        yield
    finally:
        # 역순 정리
        await redis.aclose()
        logger.info("redis_disposed")

        await http_client.aclose()
        logger.info("http_client_disposed")

        await dispose_db()
        logger.info("db_disposed")
        logger.info("app_shutting_down")


app = FastAPI(
    title="KNU Chatbot Backend",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if not settings.is_production else None,
    redoc_url="/redoc" if not settings.is_production else None,
)

app.add_middleware(CorrelationIDMiddleware)

# 글로벌 예외 핸들러 등록
register_exception_handlers(app)

# api 라우터 등록
app.include_router(api_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}

from typing import Annotated
from fastapi import Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db


@app.get("/health/ready")
async def ready(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> JSONResponse:
    """Readiness probe — DB 연결까지 점검."""
    checks: dict[str, str] = {}
    is_ready = True

    # DB 점검
    try:
        await db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"error: {type(e).__name__}"
        is_ready = False
        logger.warning("readiness_db_check_failed", error=str(e))

    if is_ready:
        return JSONResponse({"status": "ready", **checks})
    else:
        return JSONResponse(
            {"status": "not_ready", **checks},
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

# 글로벌 예외 핸들러
@app.exception_handler(UserNotFoundError)
async def user_not_found_handler(request, exc):
    return JSONResponse(
        status_code=404,
        content={"detail": str(exc)},
    )