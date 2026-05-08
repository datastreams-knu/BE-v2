# be/tests/conftest.py
"""테스트 인프라 — testcontainers + async SQLAlchemy."""

import os

os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")
os.environ.setdefault("REDIS_CACHE_URL", "redis://localhost:6379/0")
os.environ.setdefault("REDIS_PUBSUB_URL", "redis://localhost:6379/1")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-not-for-production")
os.environ.setdefault("GOOGLE_CLIENT_ID", "test-client-id")
os.environ.setdefault("GOOGLE_CLIENT_SECRET", "test-client-secret")
os.environ.setdefault("GOOGLE_REDIRECT_URI", "http://localhost:8000/test")
os.environ.setdefault("AI_SERVER_URL", "http://localhost:8001")
os.environ.setdefault("LOG_LEVEL", "INFO")
# ===========================================================================

import asyncio
from collections.abc import AsyncIterator, Iterator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from testcontainers.postgres import PostgresContainer

from app.db.base import Base
# 모델 import — Base.metadata가 모든 테이블을 인식하도록
from app.db.models import User, Chat, Message, RefreshToken

import httpx
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from app.repositories.refresh_token import RefreshTokenRepository
from app.repositories.user import UserRepository
from app.services.auth.providers import GoogleOAuthProvider
from app.services.auth.service import AuthService
from app.services.auth.state_store import OAuthStateStore
from app.services.user import UserService


# ---------------------------------------------------------------------------
# 1. PostgreSQL 컨테이너 — 테스트 세션 전체에서 한 번만 띄움
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def postgres_container() -> Iterator[PostgresContainer]:
    """테스트 세션 동안 단일 PostgreSQL 컨테이너 운영."""
    with PostgresContainer("postgres:17-alpine", driver="asyncpg") as pg:
        yield pg


# ---------------------------------------------------------------------------
# 2. async 엔진 — 컨테이너에 연결
# ---------------------------------------------------------------------------
@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def engine(
    postgres_container: PostgresContainer,
) -> AsyncIterator[AsyncEngine]:
    """testcontainers가 띄운 DB에 비동기 엔진 연결."""
    url = postgres_container.get_connection_url()
    engine = create_async_engine(url, pool_pre_ping=True)

    # 스키마 생성 (Alembic 안 거치고 metadata 직접 사용)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    await engine.dispose()


# ---------------------------------------------------------------------------
# 3. async_sessionmaker — 테스트들이 독립 세션을 만들 때 사용
# ---------------------------------------------------------------------------
@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def sessionmaker(
    engine: AsyncEngine,
) -> async_sessionmaker[AsyncSession]:
    """매 호출마다 새로운 AsyncSession을 만드는 factory.

    동시성 테스트에서는 task별로 독립된 세션이 필요하므로
    이 factory를 task에 직접 넘긴다.
    """
    return async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )


# ---------------------------------------------------------------------------
# 4. clean_db — 매 테스트 함수마다 모든 테이블을 비움
# ---------------------------------------------------------------------------
@pytest_asyncio.fixture(scope="function", loop_scope="session", autouse=True)
async def clean_db(engine: AsyncEngine) -> AsyncIterator[None]:
    """각 테스트 시작 전에 모든 테이블을 비운다.

    autouse=True라 명시적으로 요청하지 않아도 매 테스트에 적용.
    DROP/CREATE 대신 TRUNCATE로 빠르게.
    """
    yield

    # 테스트 후 정리 — 다음 테스트가 깨끗한 상태에서 시작하도록
    async with engine.begin() as conn:
        # 외래키 무시하고 모든 테이블 truncate
        # CASCADE로 RefreshToken/Chat/Message까지 한 번에
        from sqlalchemy import text
        await conn.execute(
            text(
                "TRUNCATE TABLE refresh_tokens, messages, chats, users "
                "RESTART IDENTITY CASCADE"
            )
        )


# ---------------------------------------------------------------------------
# 5. session — 단일 세션이 필요한 테스트용 (race 테스트는 사용 X)
# ---------------------------------------------------------------------------
@pytest_asyncio.fixture(scope="function", loop_scope="session")
async def session(
    sessionmaker: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    """단일 세션. 일반 단위 테스트용.

    race condition 테스트는 이 fixture 쓰지 말 것.
    각 task가 독립 세션을 가져야 race가 진짜로 일어남.
    """
    async with sessionmaker() as s:
        yield s

@pytest.fixture(scope="function")
def auth_service_factory(
    sessionmaker: async_sessionmaker[AsyncSession],
):
    """task별 독립된 AuthService를 만드는 factory.

    race condition 테스트의 핵심:
    - 각 task가 자기만의 session을 가져야 진짜 race가 일어남
    - 같은 session을 공유하면 SQLAlchemy identity map이 race를 가려버림

    Returns:
        async context manager. session까지 함께 yield해서 호출자가
        commit/rollback을 직접 제어할 수 있게 함.
    """
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def _factory():
        async with sessionmaker() as session:
            user_repo = UserRepository(session)
            user_service = UserService(session=session, user_repo=user_repo)
            token_repo = RefreshTokenRepository(session)

            # OAuth Provider/StateStore는 race에 영향 없으므로
            # 같은 인스턴스를 task끼리 공유해도 무방하지만,
            # 단순화를 위해 task마다 새로 생성
            http_client = httpx.AsyncClient()
            try:
                oauth_provider = GoogleOAuthProvider(http_client)
                state_store = OAuthStateStore()

                auth_service = AuthService(
                    session=session,
                    oauth_provider=oauth_provider,
                    state_store=state_store,
                    user_service=user_service,
                    token_repo=token_repo,
                )
                yield auth_service, session
            finally:
                await http_client.aclose()

    return _factory