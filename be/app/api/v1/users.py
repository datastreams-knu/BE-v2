# be/app/api/v1/users.py
"""
User API 엔드포인트.

ADR-014:
- /me 패턴 (자기 자신 리소스)
- RESTful 명명
- 표준 HTTP 메서드
"""

from fastapi import APIRouter, status, HTTPException

from app.api.deps import CurrentUserIdDep, UserServiceDep
from app.schemas.user import UserResponse, UserUpdate

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserResponse)
async def get_me(
    user_id: CurrentUserIdDep,
    service: UserServiceDep,
) -> UserResponse:
    """현재 사용자 정보 조회."""
    # TODO: 본인 구현
    # 힌트:
    # 1. service.get_user(user_id) 호출
    # 2. UserResponse.model_validate(user)로 변환해 반환
    user = await service.get_user(user_id=user_id)
    return UserResponse.model_validate(user)


@router.patch("/me", response_model=UserResponse)
async def update_me(
    payload: UserUpdate,
    user_id: CurrentUserIdDep,
    service: UserServiceDep,
) -> UserResponse:
    """현재 사용자 정보 수정.

    현재는 nickname만 변경 가능.
    """
    # TODO: 본인 구현
    # 힌트:
    # 1. payload.nickname이 None이면? — 변경할 게 없음
    #    → 그냥 현재 정보 반환할지, 400 에러 던질지 결정
    # 2. None이 아니면 service.update_nickname(user_id, payload.nickname)
    # 3. 결과를 UserResponse로 변환
    if payload.nickname is not None:
        user = await service.update_nickname(user_id=user_id, new_nickname=payload.nickname)
        return UserResponse.model_validate(user)
    else:
        raise HTTPException(
        status_code=400,
        detail="At least one field must be provided",
    )
    


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_me(
    user_id: CurrentUserIdDep,
    service: UserServiceDep,
) -> None:
    """현재 사용자 탈퇴.

    ON DELETE CASCADE로 chats, messages, refresh_tokens 모두 삭제.
    """
    # TODO: 본인 구현
    # 힌트:
    # 1. service.delete_user(user_id) 호출
    # 2. 반환값 없음 (204 No Content)
    await service.delete_user(user_id=user_id)
    
    