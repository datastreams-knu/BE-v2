# be/app/main.py
"""FastAPI 애플리케이션 진입점."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.db.session import create_engine, dispose_db, init_db
from app.middleware.correlation import CorrelationIDMiddleware

configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """앱 라이프사이클.

    기동: DB 엔진 생성 → sessionmaker 초기화
    종료: DB 연결 풀 정리
    """
    logger.info(
        "app_starting",
        environment=settings.ENVIRONMENT.value,
        log_level=settings.LOG_LEVEL,
    )

    # === 기동 ===
    engine = create_engine()
    init_db(engine)
    logger.info("db_initialized")

    try:
        yield
    finally:
        # === 종료 ===
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


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


# be/app/main.py 의 ready 함수 교체

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