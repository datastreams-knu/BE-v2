# be/app/services/chat.py
"""Chat Service — Chat 도메인 비즈니스 로직."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ChatNotFoundError, InvalidChatNameError
from app.core.logging import get_logger
from app.db.models.chat import Chat
from app.repositories.chat import ChatRepository

logger = get_logger(__name__)


# 비즈니스 규칙 상수
CHAT_NAME_MIN_LENGTH = 1
CHAT_NAME_MAX_LENGTH = 100


# === Domain types ===

class ChatPage(BaseModel):
    """
    페이지네이션된 Chat 목록.

    items: 이번 페이지의 Chat들
    next_cursor: 다음 페이지 cursor (None이면 마지막 페이지)
    has_more: 다음 페이지 존재 여부
    """

    model_config = {"arbitrary_types_allowed": True}

    items: list[Chat]
    next_cursor: str | None
    has_more: bool


# === Service ===

class ChatService:
    """Chat 도메인 비즈니스 로직.

    소유권 검증, cursor 인코딩·디코딩 포함.
    """

    def __init__(
        self,
        session: AsyncSession,
        chat_repo: ChatRepository,
    ):
        self.session = session
        self.chat_repo = chat_repo

    # === 조회 ===

    async def get_chat(self, user_id: UUID, chat_id: UUID) -> Chat:
        """Chat 조회 + 소유권 검증.

        본인의 Chat이 아니면 ChatNotFoundError (404).
        """
        # TODO: 본인 구현
        # 힌트:
        # 1. repo.get_by_id_and_user(chat_id, user_id) 호출
        # 2. 없으면 ChatNotFoundError(chat_id) raise
        chat = await self.chat_repo.get_by_id_and_user(chat_id=chat_id, user_id=user_id)
        if not chat:
            raise ChatNotFoundError(chat_id=chat_id)
        return chat
        
    async def list_chats(
        self,
        user_id: UUID,
        limit: int = 20,
        cursor: str | None = None,
    ) -> ChatPage:
        """사용자의 Chat 목록 (cursor pagination).

        Args:
            limit: 페이지당 항목 수 (최대 100 권장)
            cursor: 이전 페이지의 next_cursor (첫 페이지면 None)
        """
        # TODO: 본인 구현
        # 힌트:
        # 1. cursor가 있으면 _decode_cursor(cursor) → (created_at, id)
        created_at = None
        chat_id = None
        if cursor:
            (created_at, id) = self._decode_cursor(cursor)

        # 2. repo.list_by_user(user_id, limit, ...) 호출
        chats = await self.chat_repo.list_by_user(
                                        user_id=user_id, 
                                        limit=limit,
                                        cursor_created_at=created_at,
                                        cursor_id=chat_id
        )
        
        # 3. has_more 판별, items 추출
        has_more = len(chats) > limit
        items = chats[:limit]

        # 5. next_curosr 계산
        next_cursor: str | None = None
        if has_more and items:
            last = items[-1]
            next_cursor = self._encode_cursor(last.created_at, last.id)

        return ChatPage(
            items=items,
            next_cursor=next_cursor,
            has_more=has_more,
        )
    
    # === 생성 ===

    async def create_chat(self, user_id: UUID, name: str) -> Chat:
        """새 Chat 생성."""
        # TODO: 본인 구현
        # 힌트:
        # 1. _validate_name 호출
        self._validate_name(name=name)
        # 2. Chat(user_id=user_id, name=name.strip()) 생성
        chat = Chat(
            user_id=user_id,
            name=name.strip()
        )
        # 3. repo.add → commit → log → return
        chat = await self.chat_repo.add(chat=chat)
        await self.session.commit()
        logger.info(
            "chat_created",
            chat_id=str(chat.id),
            chat_name=str(chat.name)
        )
        return chat

    # === 수정 ===

    async def update_chat_name(
        self,
        user_id: UUID,
        chat_id: UUID,
        new_name: str,
    ) -> Chat:
        """Chat 이름 변경 + 소유권 검증."""
        # TODO: 본인 구현
        # 힌트:
        # 1. _validate_name
        # 2. get_chat (소유권 검증 포함)
        # 3. repo.update_name → commit → log
        self._validate_name(new_name)
        chat = await self.get_chat(user_id=user_id, chat_id=chat_id)
        old_name = chat.name
        await self.chat_repo.update_name(chat, new_name)
        await self.session.commit()
        logger.info(
            "chat_name_updated",
            chat_id=str(chat_id),
            old=old_name,
            new=new_name,
        )
        return chat

    # === 삭제 ===

    async def delete_chat(self, user_id: UUID, chat_id: UUID) -> None:
        """Chat 삭제 + 소유권 검증."""
        # TODO: 본인 구현
        chat = await self.get_chat(user_id, chat_id)
        await self.chat_repo.delete(chat)
        await self.session.commit()

        logger.info(
            "chat_deleted",
            chat_id=str(chat_id),
        )

    # === Private helpers ===

    def _validate_name(self, name: str) -> None:
        """Chat 이름 검증.

        UserService._validate_nickname과 같은 패턴.
        """
        # TODO: 본인 구현
        # 힌트:
        # - strip 후 빈 문자열이면 reason="empty"
        # - CHAT_NAME_MAX_LENGTH 초과면 reason="too long"
        # - InvalidChatNameError raise
        stripped = name.strip()
        reason = None
        if len(stripped) == 0:
            reason = "empty"
        elif len(stripped) > CHAT_NAME_MAX_LENGTH:
            reason = f"too long (max {CHAT_NAME_MAX_LENGTH} chars)"
        if reason:
            raise InvalidChatNameError(name, reason=reason)

    @staticmethod
    def _encode_cursor(created_at: datetime, chat_id: UUID) -> str:
        """cursor 인코딩: (created_at, id) → base64 string."""
        import base64
        import json

        payload = {
            "created_at": created_at.isoformat(),
            "id": str(chat_id),
        }
        json_str = json.dumps(payload)
        return base64.urlsafe_b64encode(json_str.encode()).decode()

    @staticmethod
    def _decode_cursor(cursor: str) -> tuple[datetime, UUID]:
        """
        cursor 디코딩: base64 string → (created_at, id).

        잘못된 cursor면 ValueError.
        """
        import base64
        import json

        try:
            json_str = base64.urlsafe_b64decode(cursor.encode()).decode()
            payload = json.loads(json_str)
            return (
                datetime.fromisoformat(payload["created_at"]),
                UUID(payload["id"]),
            )
        except (ValueError, KeyError, json.JSONDecodeError) as e:
            raise ValueError(f"invalid cursor: {e}") from e