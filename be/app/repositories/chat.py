# be/app/repositories/user.py
"""Chat Repository - Chat 도메인의 데이터 접근 로직"""

from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.chat import Chat

class ChatRepository:
    """
    Chat 도메인 Repository.

    트랜잭션 commit·rollback은 호출자(Service)의 책임.
    이 Repository는 쿼리 실행과 flush까지만 담당.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, chat_id:UUID) -> Chat | None:
        """ID로 채팅 조회. 없다면 None"""
        result = await self.session.execute(
            select(Chat).where(Chat.id == chat_id)
        )
        return result.scalar_one_or_none()

    async def create(self, user_id: UUID, name: str) -> Chat:
        """채팅 생성"""
        chat = Chat(user_id=user_id, name=name)
        self.session.add(chat)
        await self.session.flush()  # ID 생성 보장
        return chat

    async def delete(self, chat: Chat) -> None:
        """채팅 삭제"""
        await self.session.delete(chat)
        await self.session.flush()

    async def list_by_user(
        self,
        user_id: UUID,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Chat]:
        """사용자의 채팅 목록 조회 (최신순)"""
        result = await self.session.execute(
            select(Chat)
            .where(Chat.user_id == user_id)
            .order_by(Chat.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def count_by_user(self, user_id: UUID) -> int:
        """사용자의 채팅 개수"""
        result = await self.session.execute(
            select(func.count()).select_from(Chat).where(Chat.user_id == user_id)
        )
        return result.scalar_one()

    async def update_name(self, chat: Chat, name: str) -> Chat:
        """채팅 이름 변경"""
        chat.name = name
        await self.session.flush()
        return chat