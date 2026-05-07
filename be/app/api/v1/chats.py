# be/app/api/v1/chats.py
"""Chat API 엔드포인트.

ADR-014:
- RESTful 명명 (복수형, /chats)
- Cursor 기반 페이지네이션
- /me 패턴 확장 (소유권은 토큰에서)
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import ChatServiceDep, CurrentUserIdDep
from app.schemas.chat import (
    ChatCreate,
    ChatPageResponse,
    ChatResponse,
    ChatUpdate,
)

router = APIRouter(prefix="/chats", tags=["chats"])


@router.post(
    "",
    response_model=ChatResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_chat(
    payload: ChatCreate,
    user_id: CurrentUserIdDep,
    service: ChatServiceDep,
) -> ChatResponse:
    """새 Chat 생성.

    user_id는 토큰에서 자동 추출 (위조 불가능).
    """
    # TODO: 본인 구현
    # 힌트:
    # 1. service.create_chat(user_id, payload.name) 호출
    # 2. 결과를 ChatResponse로 변환
    chat = await service.create_chat(user_id=user_id, name=payload.name)
    return ChatResponse.model_validate(chat)


@router.get("", response_model=ChatPageResponse)
async def list_chats(
    user_id: CurrentUserIdDep,
    service: ChatServiceDep,
    limit: Annotated[int, Query(ge=1, le=100, description="페이지당 항목 수")] = 20,
    cursor: Annotated[str | None, Query(description="이전 페이지의 next_cursor")] = None,
) -> ChatPageResponse:
    """본인의 Chat 목록 (cursor pagination).

    첫 페이지는 cursor 없이 호출.
    이후 응답의 next_cursor를 다음 호출의 cursor로 전달.
    """
    # TODO: 본인 구현
    # 힌트:
    # 1. try/except로 cursor 디코딩 에러(ValueError) 처리 → 400 Bad Request
    # 2. service.list_chats(user_id, limit, cursor) 호출
    # 3. ChatPage → ChatPageResponse 변환
    #    - items: [ChatResponse.model_validate(c) for c in page.items]
    #    - next_cursor, has_more 그대로
    try:
        page = await service.list_chats(
            user_id=user_id,
            limit=limit,
            cursor=cursor,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=f"invalid cursor: {e}",
        )

    return ChatPageResponse(
        items=[ChatResponse.model_validate(c) for c in page.items],
        next_cursor=page.next_cursor,
        has_more=page.has_more,
    )

@router.get("/{chat_id}", response_model=ChatResponse)
async def get_chat(
    chat_id: UUID,
    user_id: CurrentUserIdDep,
    service: ChatServiceDep,
) -> ChatResponse:
    """단일 Chat 조회.

    본인 것이 아니면 404 (소유권 검증은 Service에서).
    """
    # TODO: 본인 구현
    # 힌트:
    # 1. service.get_chat(user_id, chat_id) 호출
    # 2. ChatResponse로 변환
    chat = await service.get_chat(user_id=user_id, chat_id=chat_id)
    return ChatResponse.model_validate(chat)


@router.patch("/{chat_id}", response_model=ChatResponse)
async def update_chat(
    chat_id: UUID,
    payload: ChatUpdate,
    user_id: CurrentUserIdDep,
    service: ChatServiceDep,
) -> ChatResponse:
    """Chat 이름 변경."""
    # TODO: 본인 구현
    # 힌트 (UserUpdate 패턴 동일):
    # 1. payload.name이 None이면 400
    # 2. service.update_chat_name(user_id, chat_id, payload.name)
    # 3. ChatResponse로 변환
    if payload.name is None:
        raise HTTPException(
            status_code=400,
            detail="At least one field must be provided",
        )
    chat = await service.update_chat_name(
        user_id=user_id,
        chat_id=chat_id,
        new_name=payload.name
    )
    return ChatResponse.model_validate(chat)

@router.delete("/{chat_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_chat(
    chat_id: UUID,
    user_id: CurrentUserIdDep,
    service: ChatServiceDep,
) -> None:
    """Chat 삭제. CASCADE로 Messages도 함께 삭제."""
    # TODO: 본인 구현
    await service.delete_chat(user_id=user_id, chat_id=chat_id)