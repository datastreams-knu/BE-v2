# be/app/repositories/user.py
"""User Repository — User 도메인의 데이터 접근 로직."""

from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.user import User


class UserRepository:
    """
    User 도메인 Repository.

    트랜잭션 commit·rollback은 호출자(Service)의 책임.
    이 Repository는 쿼리 실행과 flush까지만 담당.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, user_id: UUID) -> User | None:
        """ID로 사용자 조회. 없으면 None."""
        result = await self.session.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()
    

    async def get_by_email(self, email: str) -> User | None:
        """이메일로 사용자 조회. 없으면 None.

        OAuth 콜백 시 기존 사용자 매칭에 사용.
        """
        result = await self.session.execute(
            select(User).where(User.email == email)
        )
        return result.scalar_one_or_none()


    async def get_by_oauth(self, provider: str, subject: str) -> User | None:
        """
        OAuth provider + subject 조합으로 사용자 조회.

        같은 이메일이라도 다른 provider면 다른 사용자로 취급.
        """
        result = await self.session.execute(
            select(User).where(User.oauth_provider == provider, User.oauth_subject == subject)
        )
        return result.scalar_one_or_none()


    async def add(self, user: User) -> User:
        """
        사용자 추가.

        flush까지만 수행 (commit은 Service 책임).
        DB가 생성한 id, joined_at이 채워진 user 객체 반환.
        """
        self.session.add(user)
        await self.session.flush()
        return user

    async def update_nickname(self, user: User, new_nickname: str) -> User:
        """사용자 닉네임 수정."""
        user.nickname = new_nickname
        await self.session.flush()
        return user

    async def delete(self, user: User) -> None:
        """사용자 삭제.

        ON DELETE CASCADE로 chats, refresh_tokens도 함께 삭제됨.
        """
        await self.session.delete(user)
        await self.session.flush()

    async def count_total(self) -> int:
        """
        총 사용자 수.

        관리자 대시보드용.
        """
        result = await self.session.execute(
            select(func.count(User.id))
        )

        return result.scalar_one()