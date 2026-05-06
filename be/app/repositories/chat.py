# be/app/repositories/chat.py
"""Chat Repository — Chat 도메인의 데이터 접근 로직."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.chat import Chat


class ChatRepository:
    """Chat 도메인 Repository.

    트랜잭션 commit·rollback은 호출자(Service)의 책임.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, chat_id: UUID) -> Chat | None:
        """ID로 Chat 조회. 없으면 None.

        주의: 권한 검증 없음. 일반 조회용.
        사용자 권한 확인이 필요하면 get_by_id_and_user 사용.
        """
        # TODO: 본인 구현
        result = await self.session.execute(
            select(Chat).where(Chat.id == chat_id)
        )
        return result.scalar_one_or_none()

    async def get_by_id_and_user(
        self,
        chat_id: UUID,
        user_id: UUID,
    ) -> Chat | None:
        """ID + 소유자로 Chat 조회.

        다른 사용자의 Chat 접근 시 None 반환 → Service에서 NotFound 처리.
        ADR-014: 정보 노출 방지를 위해 403 아닌 404.
        """
        # TODO: 본인 구현
        # 힌트: WHERE에 두 조건 (chat_id, user_id) 모두
        result = await self.session.execute(
            select(Chat).where(Chat.id == chat_id, Chat.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def list_by_user(
        self,
        user_id: UUID,
        limit: int,
        cursor_created_at: datetime | None = None,
        cursor_id: UUID | None = None,
    ) -> list[Chat]:
        """사용자의 Chat 목록 (cursor pagination).

        정렬: created_at DESC, id DESC (tie-breaker)
        cursor가 None이면 첫 페이지.
        반환: limit + 1 개 (호출자가 has_more 판별)
        """
        # TODO: 본인 구현
        # 힌트:
        # 1. select(Chat).where(Chat.user_id == user_id)
        # 2. cursor가 있으면 .where(tuple_(Chat.created_at, Chat.id) < (...))
        # 3. .order_by(Chat.created_at.desc(), Chat.id.desc())
        # 4. .limit(limit + 1)
        stmt = (
            select(Chat)
            .where(Chat.user_id == user_id)
            .order_by(Chat.created_at.desc(), Chat.id.desc())
            .limit(limit + 1)
        )
        if cursor_created_at is not None and cursor_id is not None:
            stmt = stmt.where(
                tuple_(Chat.created_at, Chat.id) < tuple_(cursor_created_at, cursor_id)
            )
        
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def add(self, chat: Chat) -> Chat:
        """Chat 추가."""
        # TODO: 본인 구현 (User Repository와 동일 패턴)
        self.session.add(chat)
        await self.session.flush()
        return chat

    async def update_name(self, chat: Chat, new_name: str) -> Chat:
        """Chat 이름 수정."""
        # TODO: 본인 구현
        chat.name = new_name
        await self.session.flush()
        return chat

    async def delete(self, chat: Chat) -> None:
        """Chat 삭제. CASCADE로 Messages도 함께 삭제됨."""
        # TODO: 본인 구현
        await self.session.delete(chat)
        await self.session.flush()

    async def count_by_user(self, user_id: UUID) -> int:
        """사용자의 총 Chat 수."""
        # TODO: 본인 구현
        result = await self.session.execute(
            select(func.count(Chat.id)).where(Chat.user_id == user_id)
        )
        return result.scalar_one()