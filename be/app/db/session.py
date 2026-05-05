# be/app/db/session.py
"""SQLAlchemy AsyncSession 관리.

ADR-003: AsyncSession + asyncpg 드라이버
"""

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings


def create_engine() -> AsyncEngine:
    """비동기 엔진 생성.

    - pool_pre_ping: 풀에서 꺼낸 연결이 살아있는지 매번 확인 (stale 연결 방지)
    - pool_size·max_overflow: 본 규모엔 기본값으로 충분
    - echo: 개발 시 SQL 출력 (운영은 False)
    """
    return create_async_engine(
        settings.DATABASE_URL,
        pool_pre_ping=True,
        echo=settings.is_development,
    )


# 모듈 로드 시점에 엔진 생성하지 않음.
# lifespan에서 명시적으로 생성·소멸 → 자원 라이프사이클을 명확히
_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def init_db(engine: AsyncEngine) -> None:
    """lifespan 기동 시 호출. 전역 sessionmaker 초기화."""
    global _engine, _sessionmaker
    _engine = engine
    _sessionmaker = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,  # 커밋 후에도 객체 속성 접근 가능
        autoflush=False,         # flush를 명시적으로만 (실수 방지)
    )


async def dispose_db() -> None:
    """lifespan 종료 시 호출. 연결 풀 정리."""
    global _engine
    if _engine is not None:
        await _engine.dispose()
        _engine = None


async def get_db() -> AsyncIterator[AsyncSession]:
    """FastAPI 의존성 주입용.

    사용 예:
        async def route(db: Annotated[AsyncSession, Depends(get_db)]):
            ...

    한 요청 동안 하나의 세션을 보장.
    예외 발생 시 자동 rollback, 정상 종료 시 자동 close.
    트랜잭션 commit은 service 계층의 책임.
    """
    if _sessionmaker is None:
        raise RuntimeError("DB not initialized. Call init_db() in lifespan.")

    async with _sessionmaker() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        # 정상 종료 시 async with가 자동 close