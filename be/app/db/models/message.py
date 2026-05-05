# be/app/db/models/message.py
"""Message 모델 — 사용자 질문과 AI 응답의 한 쌍."""

from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, created_at, uuid_pk

if TYPE_CHECKING:
    from app.db.models.chat import Chat


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (
        # Chat별 시간순 조회 (ADR-014 cursor pagination)
        Index("ix_messages_chat_created", "chat_id", "created_at"),
    )

    id: Mapped[uuid_pk]
    chat_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("chats.id", ondelete="CASCADE"),
        nullable=False,
    )
    question_text: Mapped[str] = mapped_column(
        Text, 
        nullable=False
    )

    # AI 응답: {answer, disclaimer, images, references} (ADR-002 JSONB)
    answer: Mapped[dict[str, Any]] = mapped_column(
        JSONB, 
        nullable=False,
    )

    created_at: Mapped[created_at]

    chat: Mapped["Chat"] = relationship(
        back_populates="messages", 
        lazy="raise",
    )