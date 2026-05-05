# be/app/services/user.py
"""User Service — User 도메인 비즈니스 로직."""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    InvalidNicknameError,
    UserAlreadyExistsError,
    UserNotFoundError,
)
from app.core.logging import get_logger
from app.db.models.user import User
from app.repositories.user import UserRepository

logger = get_logger(__name__)


# 비즈니스 규칙 상수
NICKNAME_MIN_LENGTH = 2
NICKNAME_MAX_LENGTH = 20


class UserService:
    """User 도메인 비즈니스 로직.

    트랜잭션 경계 관리, 도메인 검증, Repository 조합을 담당.
    SQL은 Repository에 위임, HTTP 변환은 API 계층의 책임.
    """

    def __init__(
        self,
        session: AsyncSession,
        user_repo: UserRepository,
    ):
        self.session = session
        self.user_repo = user_repo

    # === 조회 ===

    async def get_user(self, user_id: UUID) -> User:
        """
        ID로 사용자 조회.

        없으면 UserNotFoundError.
        """
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise UserNotFoundError(user_id=user_id)
        return user

    async def get_user_by_email(self, email: str) -> User | None:
        """이메일로 사용자 조회.

        OAuth 콜백 시 사용 — 없으면 None 반환 (예외 아님).
        예외가 아닌 이유: "신규 가입할지 기존 로그인할지" 분기에 쓰임.
        """
        # TODO: 본인 구현
        user = await self.user_repo.get_by_email(email)
        if not user:
            return None
        return user


    # === 생성 ===

    async def create_user_oauth(
        self,
        email: str,
        nickname: str,
        oauth_provider: str,
        oauth_subject: str,
    ) -> User:
        """OAuth 사용자 생성.

        비즈니스 규칙:
        1. 이메일이 이미 존재하면 UserAlreadyExistsError
        2. 닉네임 길이 검증 (2~20자)
        3. 트랜잭션 커밋

        Returns:
            생성된 User (id, joined_at 포함)
        """
        # TODO: 본인 구현
        # 힌트:
        # 1. _validate_nickname 호출 (private 메서드, 아래에서 정의)
        self._validate_nickname(nickname=nickname)
        # 2. 이메일 중복 체크 (repo.get_by_email)
        check = await self.user_repo.get_by_email(email)
        if check:
            raise UserAlreadyExistsError(email=email)
        # 3. User 객체 생성
        user = User(
            email=email,
            nickname=nickname.strip(),
            oauth_provider=oauth_provider,
            oauth_subject=oauth_subject
        )
        # 4. repo.add 호출
        user = await self.user_repo.add(user=user)
        # 5. session.commit
        await self.session.commit()
        # 6. logger.info로 도메인 이벤트
        logger.info(
            "user_created_oauth",
            user_id=str(user.id),
            email=email,
            oauth_provider=oauth_provider,
        )
        # 7. user 반환
        return user

    # === 수정 ===

    async def update_nickname(self, user_id: UUID, new_nickname: str) -> User:
        """닉네임 변경.

        비즈니스 규칙:
        1. 사용자 존재 확인
        2. 닉네임 검증
        3. 변경 + 커밋
        """
        # TODO: 본인 구현
        user = await self.get_user(user_id=user_id)
        old_nickname = user.nickname
        self._validate_nickname(nickname=new_nickname)
        user = await self.user_repo.update_nickname(user=user, new_nickname=new_nickname.strip())
        await self.session.commit()
        logger.info(
            "user_nickname_updated",
            user_id=str(user_id),
            old=old_nickname,
            new=new_nickname,
        )
        return user
    # === 삭제 ===

    async def delete_user(self, user_id: UUID) -> None:
        """사용자 탈퇴.

        ON DELETE CASCADE로 chats, messages, refresh_tokens 모두 삭제됨.
        """
        # TODO: 본인 구현
        # 힌트:
        # 1. 사용자 존재 확인
        # 2. repo.delete 호출
        # 3. commit
        # 4. logger로 탈퇴 이벤트
        user = await self.get_user(user_id=user_id)
        await self.user_repo.delete(user=user)
        await self.session.commit()

        logger.info(
            "user_deleted",
            user_id=str(user_id),
            email=user.email
        )
        

    # === Private helpers ===

    def _validate_nickname(self, nickname: str) -> None:
        """닉네임 비즈니스 규칙 검증.

        실패 시 InvalidNicknameError.
        """
        # TODO: 본인 구현
        # 힌트:
        # - NICKNAME_MIN_LENGTH 미만이면 reason="too short"
        # - NICKNAME_MAX_LENGTH 초과이면 reason="too long"
        # - strip() 후 비어있으면 reason="empty"
        stripped = nickname.strip()
        reason = None
        if len(stripped) == 0:
            reason = "empty"
        elif len(stripped) < NICKNAME_MIN_LENGTH:
            reason = f"too short (min {NICKNAME_MIN_LENGTH} chars)"
        elif len(stripped) > NICKNAME_MAX_LENGTH:
            reason = f"too long (max {NICKNAME_MAX_LENGTH} chars)"
        if reason:
            raise InvalidNicknameError(nickname=nickname, reason=reason)