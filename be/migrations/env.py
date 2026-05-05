"""Alembic 마이그레이션 환경 설정.

ADR-003·004: 비동기 SQLAlchemy + 타임스탬프 명명.
"""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

# 모든 모델을 import해야 autogenerate가 인식
from app.core.config import settings
from app.db.base import Base
from app.db.models import *  # noqa: F401, F403

# Alembic Config 객체
config = context.config

# settings에서 DATABASE_URL을 동적으로 주입
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

# Python 로깅 설정
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# autogenerate가 비교할 메타데이터
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """오프라인 모드 — DB 연결 없이 SQL 스크립트 생성."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """비동기 엔진으로 마이그레이션 실행."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """온라인 모드 — 실제 DB 연결 후 마이그레이션 적용."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()