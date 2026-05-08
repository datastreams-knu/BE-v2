# be/app/services/auth/service.py
"""Auth Service — OAuth + JWT 비즈니스 로직."""

import base64
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.core.exceptions import (
    AuthError,
    InvalidStateError,
    TokenReuseDetectedError,
    UserAlreadyExistsError,
)
from app.core.logging import get_logger
from app.core.security import (
    ExpiredTokenError,
    InvalidTokenError,
    create_access_token,
    decode_access_token,
    generate_refresh_token,
    hash_refresh_token,
)
from app.db.models.refresh_token import RefreshToken
from app.db.models.user import User
from app.repositories.refresh_token import RefreshTokenRepository
from app.services.auth.providers import OAuthError, OAuthProvider, OAuthUserInfo
from app.services.auth.state_store import OAuthStateStore
from app.services.user import UserService

logger = get_logger(__name__)


# === Domain types ===

class TokenPair(BaseModel):
    """발급된 토큰 한 쌍."""
    access_token: str
    refresh_token: str
    access_expires_in: int  # 초 단위


class AuthorizationStart(BaseModel):
    """OAuth 시작 응답."""
    authorization_url: str
    state: str


# === Service ===

class AuthService:
    def __init__(
        self,
        session: AsyncSession,
        oauth_provider: OAuthProvider,
        state_store: OAuthStateStore,
        user_service: UserService,
        token_repo: RefreshTokenRepository,
    ):
        self.session = session
        self.oauth_provider = oauth_provider
        self.state_store = state_store
        self.user_service = user_service
        self.token_repo = token_repo

    # === OAuth flow ===

    async def start_oauth_login(self) -> AuthorizationStart:
        """OAuth 로그인 시작.

        state, code_verifier 생성 → state_store에 저장 → 인가 URL 반환.
        """
        state = secrets.token_urlsafe(32)
        code_verifier = secrets.token_urlsafe(64)
        code_challenge = self._compute_code_challenge(code_verifier)

        await self.state_store.save(state, code_verifier)

        url = self.oauth_provider.build_authorization_url(
            state=state,
            code_challenge=code_challenge,
        )

        logger.info("oauth_login_started", provider=self.oauth_provider.name)

        return AuthorizationStart(authorization_url=url, state=state)

    async def handle_oauth_callback(
        self,
        code: str,
        state: str,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> TokenPair:
        """OAuth 콜백 처리.

        1. state 검증 (state_store에서 code_verifier 조회)
        2. Provider에 토큰 교환 요청
        3. 사용자 매칭 또는 신규 가입
        4. 토큰 페어 발급
        5. 트랜잭션 커밋
        """
        # 1. state → code_verifier
        code_verifier = await self.state_store.pop(state)
        if code_verifier is None:
            logger.warning("oauth_invalid_state", state=state)
            raise InvalidStateError("invalid or expired state")

        # 2. 토큰 교환
        try:
            user_info = await self.oauth_provider.exchange_code(
                code=code,
                code_verifier=code_verifier,
            )
        except OAuthError as e:
            logger.error("oauth_exchange_failed", error=str(e))
            raise AuthError(f"OAuth provider error: {e}") from e

        # 3. 사용자 매칭 또는 신규 가입
        user = await self._get_or_create_user(user_info)

        # 4. 토큰 발급
        token_pair = await self._issue_token_pair(
            user_id=user.id,
            user_agent=user_agent,
            ip_address=ip_address,
        )

        # 5. 커밋
        await self.session.commit()

        logger.info(
            "user_logged_in",
            user_id=str(user.id),
            provider=user_info.provider,
        )

        return token_pair

    # === Token refresh (Rotation) ===

    async def refresh_tokens(
        self,
        refresh_token: str,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> TokenPair:
        """Refresh Token으로 새 토큰 페어 발급 (Rotation).

        ADR-005:
        - 기존 refresh를 revoke + replaced_by 설정
        - 새 access + refresh 발급
        - 이미 revoke된 토큰 재사용 시도 → 체인 전체 revoke (탈취 의심)
        """
        token_hash = hash_refresh_token(refresh_token)

        existing = await self.token_repo.get_by_hash(token_hash)
        if existing is None:
            logger.warning("refresh_token_not_found")
            raise InvalidTokenError("refresh token not found")

        # 이미 revoke된 토큰 재사용 시도 — 탈취 의심
        if existing.revoked_at is not None:
            logger.warning(
                "refresh_token_reuse_detected",
                user_id=str(existing.user_id),
                token_id=str(existing.id),
            )
            # 체인 전체 revoke
            await self.token_repo.revoke_chain_from(existing)
            await self.session.commit()
            raise TokenReuseDetectedError("token reuse detected — all sessions revoked")

        # 만료 확인
        now = datetime.now(timezone.utc)
        if existing.expires_at < now:
            raise ExpiredTokenError()

        # 새 토큰 발급
        new_pair = await self._issue_token_pair(
            user_id=existing.user_id,
            user_agent=user_agent,
            ip_address=ip_address,
        )

        # 새 토큰의 DB 레코드 조회 (방금 저장된 것)
        new_hash = hash_refresh_token(new_pair.refresh_token)
        new_record = await self.token_repo.get_by_hash(new_hash)
        assert new_record is not None  # 방금 만들었으니 반드시 존재

        # 기존 토큰 revoke + replaced_by 연결
        await self.token_repo.revoke(existing, replaced_by_id=new_record.id)

        await self.session.commit()

        logger.info(
            "token_refreshed",
            user_id=str(existing.user_id),
        )

        return new_pair

    # === Logout ===

    async def logout(self, user_id: UUID) -> None:
        """현재 사용자의 모든 토큰 무효화.

        모든 디바이스에서 로그아웃되는 효과.
        """
        revoked_count = await self.token_repo.revoke_all_by_user(user_id)
        await self.session.commit()

        logger.info(
            "user_logged_out",
            user_id=str(user_id),
            revoked_tokens=revoked_count,
        )

    # === Access Token verification (다른 라우트에서 사용) ===

    async def verify_access_token(self, token: str) -> UUID:
        """Access Token 검증 → user_id 반환.

        만료·무효 시 예외.
        """
        payload = decode_access_token(token)
        return UUID(payload.sub)

    # === Private helpers ===

    @staticmethod
    def _compute_code_challenge(code_verifier: str) -> str:
        """PKCE code_challenge 계산 (S256)."""
        digest = hashlib.sha256(code_verifier.encode()).digest()
        return base64.urlsafe_b64encode(digest).decode().rstrip("=")

    async def _get_or_create_user(self, user_info: OAuthUserInfo) -> User:
        """OAuth 사용자 정보로 기존 사용자 찾기 or 신규 가입."""
        # 1. (provider, subject) 조합으로 정확 매칭
        existing = await self.user_service.user_repo.get_by_oauth(
            provider=user_info.provider,
            subject=user_info.subject,
        )
        if existing is not None:
            return existing

        # 2. 이메일로 매칭 (다른 provider로 같은 이메일 가입 가능성)
        # 본 프로젝트 v2는 OAuth만 지원하므로 이 경우 충돌 — UserAlreadyExists
        existing_by_email = await self.user_service.get_user_by_email(user_info.email)
        if existing_by_email is not None:
            # 이미 다른 provider로 가입된 사용자
            raise UserAlreadyExistsError(user_info.email)

        # 2. 신규 가입 시도
        try:
            nickname = self._derive_nickname(user_info.name)
            user = await self.user_service.create_user_oauth(
                email=user_info.email,
                nickname=nickname,
                oauth_provider=user_info.provider,
                oauth_subject=user_info.subject,
            )
            return user

        except UserAlreadyExistsError:
            # Type 1 race: 다른 task가 commit 끝낸 후 본 task가 사전 체크에서 발견.
            # (provider, subject)가 같으면 동일 사용자로 간주.
            logger.info(
                "oauth_signup_race_recovered_via_email_check",
                provider=user_info.provider,
                subject=user_info.subject,
            )
            recovered = await self.user_service.user_repo.get_by_oauth(
                provider=user_info.provider,
                subject=user_info.subject,
            )
            if recovered is not None:
                return recovered
            # (provider, subject)가 다른데 email만 같다면 진짜 충돌
            raise

        except IntegrityError:
            # Type 2 race: 두 INSERT가 동시 도달, DB unique 제약이 차단.
            # 세션을 롤백해야 이후 쿼리 가능.
            await self.session.rollback()
            logger.info(
                "oauth_signup_race_recovered_via_db_constraint",
                provider=user_info.provider,
                subject=user_info.subject,
            )

            # 재조회 — (provider, subject) 매칭이면 정상 복구
            recovered = await self.user_service.user_repo.get_by_oauth(
                provider=user_info.provider,
                subject=user_info.subject,
            )
            if recovered is not None:
                return recovered

            # email 충돌이면 진짜 비즈니스 에러
            raise UserAlreadyExistsError(user_info.email)

    @staticmethod
    def _derive_nickname(name: str) -> str:
        """OAuth name에서 닉네임 추출.

        Google name이 "John Doe" 같이 길거나 공백 포함될 수 있음.
        UserService의 _validate_nickname 규칙(2~20자)에 맞춤.
        """
        nickname = name.strip()[:20]  # 20자 제한
        if len(nickname) < 2:
            nickname = "User"  # fallback
        return nickname

    async def _issue_token_pair(
        self,
        user_id: UUID,
        user_agent: str | None,
        ip_address: str | None,
    ) -> TokenPair:
        """Access + Refresh 토큰 발급 + DB 저장."""
        # Access (JWT)
        access_token = create_access_token(user_id)
        access_expires_in = settings.JWT_ACCESS_EXPIRE_MINUTES * 60

        # Refresh (random + DB 저장)
        refresh_plain = generate_refresh_token()
        refresh_hash = hash_refresh_token(refresh_plain)
        expires_at = datetime.now(timezone.utc) + timedelta(
            days=settings.JWT_REFRESH_EXPIRE_DAYS
        )

        refresh_record = RefreshToken(
            user_id=user_id,
            token_hash=refresh_hash,
            expires_at=expires_at,
            user_agent=user_agent,
            ip_address=ip_address,
        )
        await self.token_repo.add(refresh_record)

        return TokenPair(
            access_token=access_token,
            refresh_token=refresh_plain,
            access_expires_in=access_expires_in,
        )