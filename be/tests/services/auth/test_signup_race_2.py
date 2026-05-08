# be/tests/services/auth/test_signup_race.py
"""OAuth 회원가입의 동시성(race condition) 검증.

목적:
- 동일 사용자의 OAuth 콜백이 동시에 두 번 도착했을 때
  현재 코드가 어떻게 깨지는지 재현.
- 수정 후 같은 시나리오가 정상 처리되는지 회귀 방지.

발생 가능한 race 두 종류 모두 검증:
- Type 1 (사전 체크 race): UserAlreadyExistsError
- Type 2 (DB 제약 race): IntegrityError
"""

import asyncio

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from app.db.models.user import User
from app.services.auth.providers import OAuthUserInfo
from app.core.exceptions import UserAlreadyExistsError


def _user_info(suffix: str = "") -> OAuthUserInfo:
    """테스트 픽스처. suffix로 케이스 격리."""
    return OAuthUserInfo(
        provider="google",
        subject=f"google-uid-race-{suffix}",
        email=f"alice{suffix}@example.com",
        name="Alice",
    )


async def test_concurrent_oauth_signup_creates_single_user(
    auth_service_factory,
    sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    """동시에 두 번 들어온 OAuth 콜백이 사용자 1명만 만들고
    두 요청 모두 성공해야 한다.

    Barrier로 두 task의 select·INSERT 시점을 강제로 동시화하여
    race condition이 매번 재현되도록 한다.
    """
    user_info = _user_info("barrier")

    # 두 task를 같은 시점에 출발시키기 위한 동기화 도구.
    # 둘 다 wait()에 도달해야 동시에 풀림.
    barrier = asyncio.Barrier(2)

    async def attempt_signup() -> tuple[str, object]:
        try:
            async with auth_service_factory() as (auth_service, session):
                # 두 task가 service 셋업을 끝낸 시점까지 같이 기다림
                # → 이후 _get_or_create_user 호출이 거의 동시에 시작
                await barrier.wait()
                user = await auth_service._get_or_create_user(user_info)
                await session.commit()
                return ("ok", user.id)
        except Exception as e:
            return ("error", e)

    results = await asyncio.gather(
        attempt_signup(),
        attempt_signup(),
    )

    # ===== 검증 =====

    statuses = [r[0] for r in results]
    errors = [r[1] for r in results if r[0] == "error"]

    # 1. 둘 다 성공해야 한다
    assert all(s == "ok" for s in statuses), (
        f"한쪽 요청이 예외로 실패했음.\n"
        f"  errors={errors}\n"
        f"  error_types={[type(e).__name__ for e in errors]}"
    )

    # 2. 같은 user_id를 받아야 한다
    user_ids = [r[1] for r in results]
    assert user_ids[0] == user_ids[1], (
        f"같은 사용자여야 하는데 다른 ID 발급: {user_ids}"
    )

    # 3. DB에는 사용자가 정확히 1명
    async with sessionmaker() as verify_session:
        result = await verify_session.execute(
            select(func.count(User.id)).where(User.email == user_info.email)
        )
        count = result.scalar_one()
        assert count == 1, f"DB에 사용자가 {count}명 있음. 정확히 1명이어야 함."

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

async def test_returning_user_login_does_not_create_duplicate(
    auth_service_factory,
    sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    """같은 사용자가 두 번 (순차) 로그인하면 첫 번째에서 생성된
    사용자가 그대로 반환되어야 한다.

    race가 아닌 정상 흐름(returning user)이 깨지지 않았는지 검증.
    """
    user_info = OAuthUserInfo(
        provider="google",
        subject="google-uid-returning",
        email="bob@example.com",
        name="Bob",
    )

    # 1차 로그인 — 신규 가입
    async with auth_service_factory() as (auth_service, session):
        first = await auth_service._get_or_create_user(user_info)
        await session.commit()
        first_id = first.id

    # 2차 로그인 — 기존 사용자 반환 (INSERT 없음)
    async with auth_service_factory() as (auth_service, session):
        second = await auth_service._get_or_create_user(user_info)
        await session.commit()
        second_id = second.id

    # 같은 user_id여야 한다
    assert first_id == second_id

    # DB에 사용자가 1명만 있어야 한다
    async with sessionmaker() as verify_session:
        result = await verify_session.execute(
            select(func.count(User.id)).where(User.email == user_info.email)
        )
        assert result.scalar_one() == 1