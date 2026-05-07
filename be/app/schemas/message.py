# be/app/schemas/message.py
"""Message 도메인 HTTP 입출력 스키마."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# v1 호환 disclaimer 문구 (DB엔 저장 안 함, 응답 시에만 추가)
DISCLAIMER = (
    "항상 정확한 답변을 제공하지 못할 수 있습니다. "
    "아래의 URL들을 참고하여 정확하고 자세한 정보를 확인하세요."
)


class MessageResponse(BaseModel):
    """단일 Message 응답.

    answer는 v1 형식: {answer, references, images} + disclaimer (응답 시 추가).
    """
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    chat_id: UUID
    question: str
    answer: dict[str, Any]
    created_at: datetime


class MessagePageResponse(BaseModel):
    """Message 목록."""
    items: list[MessageResponse]
    next_cursor: str | None = None
    has_more: bool


class MessageCreate(BaseModel):
    """POST /chats/{id}/messages 입력."""
    question: str = Field(min_length=1, max_length=2000, description="사용자 질문")