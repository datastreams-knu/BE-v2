# be/app/repositories/refresh_token.py
"""RefreshToken Repository.

ADR-005: Refresh Token Rotation 추적용.
"""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.refresh_token import RefreshToken


def _utcnow() -> datetime:
    """현재 시각을 timezone-aware UTC로 반환.

    Repository 전반에서 revoked_at 등 시각 기록에 사용.
    datetime.utcnow()는 naive를 반환하므로 사용하지 않는다.
    """
    return datetime.now(timezone.utc)


class RefreshTokenRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_hash(self, token_hash: str) -> RefreshToken | None:
        """해시로 토큰 조회. 검증 시 사용."""
        result = await self.session.execute(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        )
        return result.scalar_one_or_none()

    async def add(self, token: RefreshToken) -> RefreshToken:
        """새 토큰 저장."""
        self.session.add(token)
        await self.session.flush()
        return token

    async def revoke(
        self,
        token: RefreshToken,
        replaced_by_id: UUID | None = None,
    ) -> RefreshToken:
        """토큰 무효화.

        replaced_by_id가 주어지면 Rotation 체인 형성.
        """
        token.revoked_at = _utcnow()
        token.replaced_by_id = replaced_by_id
        await self.session.flush()
        return token

    async def revoke_chain_from(self, token: RefreshToken) -> int:
        """주어진 토큰부터 시작하는 체인 전체를 revoke.

        탈취 탐지 시 사용. 체인을 따라가며 모두 무효화.
        Returns: revoked된 토큰 개수
        """
        now = _utcnow()
        count = 0
        current: RefreshToken | None = token

        while current is not None:
            if current.revoked_at is None:
                current.revoked_at = now
                count += 1
            # 다음 체인 찾기
            if current.replaced_by_id is None:
                break
            result = await self.session.execute(
                select(RefreshToken).where(RefreshToken.id == current.replaced_by_id)
            )
            current = result.scalar_one_or_none()

        await self.session.flush()
        return count

    async def revoke_all_by_user(self, user_id: UUID) -> int:
        """사용자의 모든 활성 토큰 무효화. 로그아웃 시 사용."""
        now = _utcnow()
        result = await self.session.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == user_id)
            .where(RefreshToken.revoked_at.is_(None))
            .values(revoked_at=now)
        )
        return result.rowcount