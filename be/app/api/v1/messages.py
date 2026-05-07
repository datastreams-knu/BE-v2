# be/app/api/v1/messages.py
"""Message API — Chat에 종속된 Nested Resource."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import CurrentUserIdDep, MessageServiceDep
from app.schemas.message import (
    DISCLAIMER,
    MessageCreate,
    MessagePageResponse,
    MessageResponse,
)

# prefix가 chats/{chat_id}/messages로 nested
router = APIRouter(prefix="/chats/{chat_id}/messages", tags=["messages"])


def _attach_disclaimer(message_response: MessageResponse) -> MessageResponse:
    """응답 직전 disclaimer 추가."""
    answer = dict(message_response.answer)
    answer.setdefault("disclaimer", DISCLAIMER)
    message_response.answer = answer
    return message_response


@router.post("", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
async def create_message(
    chat_id: UUID,
    payload: MessageCreate,
    user_id: CurrentUserIdDep,
    service: MessageServiceDep,
) -> MessageResponse:
    message = await service.create_message(
        user_id=user_id,
        chat_id=chat_id,
        question=payload.question,
    )
    return _attach_disclaimer(MessageResponse.model_validate(message))


@router.get("", response_model=MessagePageResponse)
async def list_messages(
    chat_id: UUID,
    user_id: CurrentUserIdDep,
    service: MessageServiceDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    cursor: Annotated[str | None, Query()] = None,
) -> MessagePageResponse:
    try:
        page = await service.list_messages(
            user_id=user_id,
            chat_id=chat_id,
            limit=limit,
            cursor=cursor,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"invalid cursor: {e}")

    return MessagePageResponse(
        items=[_attach_disclaimer(MessageResponse.model_validate(m)) for m in page.items],
        next_cursor=page.next_cursor,
        has_more=page.has_more,
    )


@router.get("/{message_id}", response_model=MessageResponse)
async def get_message(
    chat_id: UUID,
    message_id: UUID,
    user_id: CurrentUserIdDep,
    service: MessageServiceDep,
) -> MessageResponse:
    message = await service.get_message(
        user_id=user_id,
        chat_id=chat_id,
        message_id=message_id,
    )
    return _attach_disclaimer(MessageResponse.model_validate(message))


@router.delete("/{message_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_message(
    chat_id: UUID,
    message_id: UUID,
    user_id: CurrentUserIdDep,
    service: MessageServiceDep,
) -> None:
    await service.delete_message(
        user_id=user_id,
        chat_id=chat_id,
        message_id=message_id,
    )