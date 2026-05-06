# be/app/services/auth/providers.py
"""OAuth Provider 추상화.

ADR-005, ADR-013: Strategy 패턴으로 다중 Provider 확장 대비.
현재는 Google만 구현. Kakao/Naver 추가 시 같은 인터페이스로.
"""

from typing import Protocol

import httpx
from pydantic import BaseModel, EmailStr

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


# === Domain types ===

class OAuthUserInfo(BaseModel):
    """
    OAuth Provider에서 받은 사용자 정보 (정규화).

    Provider별로 응답 형식이 다르지만 이 형태로 통일.
    """

    provider: str           # "google", "kakao", ...
    subject: str            # Provider 내부 사용자 ID
    email: EmailStr
    name: str               # 닉네임 후보로 사용


# === Provider Protocol ===

class OAuthProvider(Protocol):
    """
    OAuth Provider 인터페이스.

    Protocol 사용 — 명시적 상속 없이도 type check 가능.
    """

    name: str

    def build_authorization_url(
        self,
        state: str,
        code_challenge: str,
    ) -> str:
        """OAuth 로그인 시작 URL 생성.

        Args:
            state: CSRF 방지용 무작위 문자열
            code_challenge: PKCE용 (code_verifier의 SHA-256 해시)

        Returns:
            Provider 로그인 페이지 URL
        """
        ...

    async def exchange_code(
        self,
        code: str,
        code_verifier: str,
    ) -> OAuthUserInfo:
        """Authorization Code를 사용자 정보로 교환.

        Args:
            code: Provider가 콜백에 보낸 인증 코드
            code_verifier: PKCE용 (1단계에서 저장해둔 원본)

        Returns:
            정규화된 사용자 정보
        """
        ...


# === Google Implementation ===

class GoogleOAuthProvider:
    """Google OAuth 2.0 + OIDC 구현."""

    name = "google"

    # Google OAuth 표준 엔드포인트
    AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
    TOKEN_URL = "https://oauth2.googleapis.com/token"
    USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"

    def __init__(self, http_client: httpx.AsyncClient):
        self._http = http_client

    def build_authorization_url(
        self,
        state: str,
        code_challenge: str,
    ) -> str:
        """Google 로그인 페이지 URL 생성."""
        params = {
            "response_type": "code",
            "client_id": settings.GOOGLE_CLIENT_ID,
            "redirect_uri": settings.GOOGLE_REDIRECT_URI,
            "scope": "openid email profile",
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            "access_type": "online",  # offline이면 google refresh token까지 — 본 프로젝트엔 불필요
            "prompt": "select_account",  # 사용자가 매번 계정 선택 가능
        }

        # URL encoding
        from urllib.parse import urlencode
        return f"{self.AUTHORIZE_URL}?{urlencode(params)}"

    async def exchange_code(
        self,
        code: str,
        code_verifier: str,
    ) -> OAuthUserInfo:
        """Google에 토큰 교환 + 사용자 정보 조회."""

        # 1. Authorization Code → Access Token
        token_response = await self._http.post(
            self.TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "code_verifier": code_verifier,
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET.get_secret_value(),
                "redirect_uri": settings.GOOGLE_REDIRECT_URI,
            },
        )

        if token_response.status_code != 200:
            logger.error(
                "google_token_exchange_failed",
                status=token_response.status_code,
                body=token_response.text,
            )
            raise OAuthError("token exchange failed")

        token_data = token_response.json()
        access_token = token_data.get("access_token")
        if not access_token:
            raise OAuthError("no access_token in response")

        # 2. Access Token → 사용자 정보
        userinfo_response = await self._http.get(
            self.USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )

        if userinfo_response.status_code != 200:
            logger.error(
                "google_userinfo_failed",
                status=userinfo_response.status_code,
            )
            raise OAuthError("userinfo fetch failed")

        userinfo = userinfo_response.json()

        # 3. 정규화
        return OAuthUserInfo(
            provider=self.name,
            subject=userinfo["sub"],
            email=userinfo["email"],
            name=userinfo.get("name", userinfo["email"].split("@")[0]),
        )


# === Exceptions ===

class OAuthError(Exception):
    """OAuth 처리 실패."""