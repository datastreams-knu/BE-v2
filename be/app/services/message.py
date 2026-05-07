# be/app/services/message.py
"""Message Service — Message 도메인 비즈니스 로직."""

import base64
import json
import asyncio

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from app.core.exceptions import (
    InvalidQuestionError,
    MessageNotFoundError,
)
from app.core.logging import get_logger
from app.db.models.message import Message
from app.repositories.message import MessageRepository
from app.services.chat import ChatService
from app.services.ai_client import AIClient
from app.services.streaming import process_message_streaming
from app.services.pubsub import MessageStreamPublisher

logger = get_logger(__name__)

QUESTION_MIN_LENGTH = 1
QUESTION_MAX_LENGTH = 2000


class MessagePage(BaseModel):
    model_config = {"arbitrary_types_allowed": True}
    items: list[Message]
    next_cursor: str | None
    has_more: bool


class MessageService:
    def __init__(
        self,
        session: AsyncSession,
        message_repo: MessageRepository,
        chat_service: ChatService,
        ai_client: AIClient,
        publisher: MessageStreamPublisher,           
        sessionmaker: async_sessionmaker[AsyncSession]
    ):
        self.session = session
        self.message_repo = message_repo
        self.chat_service = chat_service
        self.ai_client = ai_client
        self.publisher = publisher
        self.sessionmaker = sessionmaker
    # === 조회 ===

    async def get_message(
        self,
        user_id: UUID,
        chat_id: UUID,
        message_id: UUID,
    ) -> Message:
        """Message 조회 + 이중 권한 검증.

        1. Chat 소유권 (ChatService)
        2. Message가 그 Chat에 속하는지 (Repository)
        """
        await self.chat_service.get_chat(user_id, chat_id)
        message = await self.message_repo.get_by_id_and_chat(message_id, chat_id)
        if not message:
            raise MessageNotFoundError(message_id)
        return message

    async def list_messages(
        self,
        user_id: UUID,
        chat_id: UUID,
        limit: int = 20,
        cursor: str | None = None,
    ) -> MessagePage:
        """
        Chat의 Message 목록 (cursor pagination, ASC).

        Chat 소유권 먼저 검증.
        """
        await self.chat_service.get_chat(user_id, chat_id)

        cursor_created_at: datetime | None = None
        cursor_id: UUID | None = None
        if cursor:
            cursor_created_at, cursor_id = self._decode_cursor(cursor)

        rows = await self.message_repo.list_by_chat(
            chat_id=chat_id,
            limit=limit,
            cursor_created_at=cursor_created_at,
            cursor_id=cursor_id,
        )

        has_more = len(rows) > limit
        items = rows[:limit]

        next_cursor: str | None = None
        if has_more and items:
            last = items[-1]
            next_cursor = self._encode_cursor(last.created_at, last.id)

        return MessagePage(items=items, next_cursor=next_cursor, has_more=has_more)

    # === 생성 ===

    async def create_message(
        self,
        user_id: UUID,
        chat_id: UUID,
        question: str,
    ) -> Message:
        """Message 생성 (스트리밍).

        응답은 즉시 반환 (placeholder answer).
        실제 AI 호출과 답변 저장은 백그라운드에서 진행.
        클라이언트는 응답의 message_id로 SSE 구독해서 실시간 답변 수신.
        """
        # 동기 처리
        # await self.chat_service.get_chat(user_id, chat_id)
        # self._validate_question(question)
  
        #answer_data = await self.ai_client.ask(question.strip())
        
        # message = Message(
        #     chat_id=chat_id,
        #     question=question.strip(),
        #     answer=answer_data,
        # )
        # message = await self.message_repo.add(message)
        # await self.session.commit()

        # logger.info(
        #     "message_created",
        #     chat_id=str(chat_id),
        #     message_id=str(message.id),
        #     question_length=len(question),
        # )

        # return message
        await self.chat_service.get_chat(user_id, chat_id)
        self._validate_question(question)

        answer_placeholder: dict[str, Any] = {
            "answer": "",
            "references": [],
            "images": [],
            "status": "pending",
        }

        message = Message(
            chat_id=chat_id,
            question=question.strip(),
            answer=answer_placeholder,
        )
        message = await self.message_repo.add(message)
        await self.session.commit()

        asyncio.create_task(
            process_message_streaming(
                message_id=message.id,
                question=question.strip(),
                sessionmaker=self.sessionmaker,
                ai_client=self.ai_client,
                publisher=self.publisher,
            )
        )
        
        logger.info(
            "message_created_streaming",
            chat_id=str(chat_id),
            message_id=str(message.id),
        )

        return message

        
    # === 삭제 ===

    async def delete_message(
        self,
        user_id: UUID,
        chat_id: UUID,
        message_id: UUID,
    ) -> None:
        """Message 삭제 + 이중 권한 검증."""
        message = await self.get_message(user_id, chat_id, message_id)
        await self.message_repo.delete(message)
        await self.session.commit()

        logger.info(
            "message_deleted",
            chat_id=str(chat_id),
            message_id=str(message_id),
        )

    # === Private helpers ===

    def _validate_question(self, question: str) -> None:
        stripped = question.strip()
        reason = None
        if len(stripped) == 0:
            reason = "empty"
        elif len(stripped) < QUESTION_MIN_LENGTH:
            reason = f"too short (min {QUESTION_MIN_LENGTH})"
        elif len(stripped) > QUESTION_MAX_LENGTH:
            reason = f"too long (max {QUESTION_MAX_LENGTH})"
        if reason:
            raise InvalidQuestionError(reason)

    @staticmethod
    def _encode_cursor(created_at: datetime, message_id: UUID) -> str:
        payload = {
            "created_at": created_at.isoformat(),
            "id": str(message_id),
        }
        return base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()

    @staticmethod
    def _decode_cursor(cursor: str) -> tuple[datetime, UUID]:
        try:
            payload = json.loads(base64.urlsafe_b64decode(cursor.encode()).decode())
            return (
                datetime.fromisoformat(payload["created_at"]),
                UUID(payload["id"]),
            )
        except (ValueError, KeyError, json.JSONDecodeError) as e:
            raise ValueError(f"invalid cursor: {e}") from e