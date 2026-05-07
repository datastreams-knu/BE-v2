# be/app/repositories/message.py
"""Message Repository — Message 도메인의 데이터 접근 로직."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.message import Message


class MessageRepository:
    """
    Message 도메인 Repository.

    트랜잭션 commit·rollback은 호출자(Service)의 책임.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, message_id: UUID) -> Message | None:
        """ID로 Message 조회."""
        # TODO: 본인 구현 (Chat Repository 패턴 동일)
        result = await self.session.execute(
            select(Message).where(Message.id == message_id)
        )
        return result.scalar_one_or_none()

    async def get_by_id_and_chat(
        self,
        message_id: UUID,
        chat_id: UUID,
    ) -> Message | None:
        """
        ID + 소속 Chat으로 Message 조회.

        다른 Chat의 Message에 접근 시 None.
        Chat 소유권은 Service의 ChatService.get_chat에서 별도 검증.
        """
        # TODO: 본인 구현
        # 힌트: WHERE에 두 조건
        result = await self.session.execute(
            select(Message).where(Message.id == message_id, Message.chat_id == chat_id)
        )
        return result.scalar_one_or_none()

    async def list_by_chat(
        self,
        chat_id: UUID,
        limit: int,
        cursor_created_at: datetime | None = None,
        cursor_id: UUID | None = None,
    ) -> list[Message]:
        """Chat의 Message 목록 (cursor pagination, ASC).

        ⚠️ Chat과 다른 점:
        - 정렬: created_at ASC, id ASC (대화 순서)
        - cursor 비교: > (DESC면 <)
        """
        # TODO: 본인 구현
        # 힌트:
        # 1. select(Message).where(Message.chat_id == chat_id)
        # 2. .order_by(Message.created_at.asc(), Message.id.asc())
        # 3. cursor가 있으면 tuple_(...) > tuple_(...) (ASC라 >)
        # 4. .limit(limit + 1)
        stmt = (
            select(Message)
            .where(Message.chat_id == chat_id)
            .order_by(Message.created_at.asc(), Message.id.asc())
            .limit(limit + 1)
        )

        if cursor_created_at is not None and cursor_id is not None:
            stmt = stmt.where(
                tuple_(Message.created_at, Message.id) > tuple_(cursor_created_at, cursor_id)
            )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def add(self, message: Message) -> Message:
        """Message 추가."""
        # TODO: 본인 구현
        self.session.add(message)
        await self.session.flush()
        return message

    async def delete(self, message: Message) -> None:
        """Message 삭제."""
        # TODO: 본인 구현
        await self.session.delete(message)
        await self.session.flush()