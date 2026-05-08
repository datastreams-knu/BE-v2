# be/tests/services/auth/test_signup_race.py
"""OAuth 회원가입의 동시성(race condition) 검증.

목적:
- 동일 사용자의 OAuth 콜백이 동시에 두 번 도착했을 때
  현재 코드가 어떻게 깨지는지 재현.
- 수정 후 같은 시나리오가 정상 처리되는지 회귀 방지.

수정 전: 두 task 중 한쪽이 IntegrityError를 받음 → 본 테스트 실패.
수정 후: 두 task 모두 성공하고 같은 user_id 반환 → 본 테스트 통과.
"""

import asyncio

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from app.db.models.user import User
from app.services.auth.providers import OAuthUserInfo

from app.core.exceptions import UserAlreadyExistsError



def _user_info() -> OAuthUserInfo:
    """테스트 픽스처 — 가상의 Google OAuth 사용자."""
    return OAuthUserInfo(
        provider="google",
        subject="google-uid-race-test-12345",
        email="alice@example.com",
        name="Alice",
    )


async def test_concurrent_oauth_signup_creates_single_user(
    auth_service_factory,
    sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    """동시에 두 번 들어온 OAuth 콜백이 사용자 1명만 만들고
    두 요청 모두 성공해야 한다."""

    user_info = _user_info()

    async def attempt_signup() -> tuple[str, object]:
        """한 번의 OAuth 콜백을 흉내. 결과를 (status, payload) 튜플로 반환.

        예외를 raise하지 않고 return하는 이유:
        asyncio.gather에서 한 task의 예외가 다른 task를 취소하지 않도록.
        """
        try:
            async with auth_service_factory() as (auth_service, session):
                user = await auth_service._get_or_create_user(user_info)
                await session.commit()
                return ("ok", user.id)
        except Exception as e:
            return ("error", e)

    # 두 요청을 동시에 실행
    results = await asyncio.gather(
        attempt_signup(),
        attempt_signup(),
    )

    # ===== 검증 =====

    # 1. 둘 다 성공해야 한다
    statuses = [r[0] for r in results]
    errors = [r[1] for r in results if r[0] == "error"]
    assert all(s == "ok" for s in statuses), (
        f"한쪽 요청이 예외로 실패했음. errors={errors}"
    )

    # 2. 두 요청이 같은 user_id를 받아야 한다 (사용자 1명만 생성)
    user_ids = [r[1] for r in results]
    assert user_ids[0] == user_ids[1], (
        f"같은 사용자여야 하는데 다른 ID가 발급됨: {user_ids}"
    )

    # 3. DB에도 사용자가 정확히 1명만 있어야 한다
    async with sessionmaker() as verify_session:
        result = await verify_session.execute(
            select(func.count(User.id)).where(
                User.email == user_info.email
            )
        )
        count = result.scalar_one()
        assert count == 1, f"DB에 사용자가 {count}명. 정확히 1명이어야 함."

# ===========================================================================
# 비즈니스 로직 회귀 방지 — race 수정이 기존 정책을 깨지 않았는지
# ===========================================================================

async def test_different_oauth_with_same_email_raises_error(
    auth_service_factory,
) -> None:
    """다른 OAuth provider로 같은 이메일을 시도하면
    UserAlreadyExistsError가 떠야 한다.

    race condition이 아닌 진짜 비즈니스 충돌 시나리오:
    - Google로 alice@example.com 가입 완료
    - 누군가 Kakao로 alice@example.com 시도 → 거부

    수정된 _get_or_create_user는 INSERT를 시도하다 IntegrityError를
    잡고, (provider, subject) 재조회에서 못 찾으면 이 에러를 raise.
    """
    # 1. Google로 먼저 가입 완료
    google_user = OAuthUserInfo(
        provider="google",
        subject="google-uid-A",
        email="alice@example.com",
        name="Alice",
    )
    async with auth_service_factory() as (auth_service, session):
        await auth_service._get_or_create_user(google_user)
        await session.commit()

    # 2. 같은 이메일로 Kakao 시도 → 비즈니스 충돌
    kakao_user = OAuthUserInfo(
        provider="kakao",
        subject="kakao-uid-B",
        email="alice@example.com",  # 같은 이메일
        name="Alice",
    )
    with pytest.raises(UserAlreadyExistsError):
        async with auth_service_factory() as (auth_service, session):
            await auth_service._get_or_create_user(kakao_user)
            await session.commit()

