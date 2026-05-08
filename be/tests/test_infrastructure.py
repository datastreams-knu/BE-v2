# be/tests/test_infrastructure.py
"""conftest 인프라가 제대로 작동하는지 점검하는 sanity test."""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def test_db_is_alive(session: AsyncSession) -> None:
    """DB 연결이 살아있는가?"""
    result = await session.execute(text("SELECT 1"))
    assert result.scalar_one() == 1


async def test_tables_exist(session: AsyncSession) -> None:
    """스키마가 제대로 생성됐는가?"""
    result = await session.execute(
        text(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public' "
            "ORDER BY table_name"
        )
    )
    tables = [row[0] for row in result.all()]
    assert "users" in tables
    assert "chats" in tables
    assert "messages" in tables
    assert "refresh_tokens" in tables


async def test_clean_db_works(session: AsyncSession) -> None:
    """clean_db fixture가 매 테스트마다 작동하는가?
    
    이 테스트가 통과하고, 이전 테스트들이 데이터를 남겼다면
    여기서 user count가 0이 아닐 것.
    """
    from app.db.models import User
    from sqlalchemy import select, func

    result = await session.execute(select(func.count(User.id)))
    assert result.scalar_one() == 0