# be/app/schemas/chat.py
"""Chat 도메인 HTTP 입출력 스키마."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ChatResponse(BaseModel):
    """단일 Chat 응답."""
    # TODO: 본인 구현
    # 힌트:
    # - model_config로 from_attributes=True
    # - 노출 필드: id, name, created_at
    # - user_id는 노출 안 함 (어차피 자기 자신 것만 보므로)
    ...


class ChatPageResponse(BaseModel):
    """Chat 목록 + cursor pagination 정보.

    Service의 ChatPage를 HTTP 응답 형식으로 변환.
    """
    # TODO: 본인 구현
    # 힌트:
    # - items: list[ChatResponse]
    # - next_cursor: str | None
    # - has_more: bool
    ...


class ChatCreate(BaseModel):
    """POST /chats 입력."""
    # TODO: 본인 구현
    # 힌트:
    # - name 필수 (Optional 아님)
    # - Field로 길이 제한 (1~100, Service의 _validate_name과 일치)
    ...


class ChatUpdate(BaseModel):
    """PATCH /chats/{id} 입력."""
    # TODO: 본인 구현
    # 힌트:
    # - name optional (UserUpdate처럼)
    # - 길이 제한 동일
    ...