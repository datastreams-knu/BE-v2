# be/app/schemas/auth.py
"""Auth 도메인 HTTP 입출력 스키마."""

from pydantic import BaseModel, Field


class LoginStartResponse(BaseModel):
    """POST /auth/google/login 응답.

    프론트엔드는 authorization_url로 사용자를 리다이렉트.
    state는 향후 콜백 검증용.
    """

    authorization_url: str
    state: str


class TokenResponse(BaseModel):
    """OAuth 콜백 또는 refresh 응답.

    refresh_token은 응답 본문이 아닌 HttpOnly Cookie로 전달.
    여기서는 access_token만 노출.
    """

    access_token: str
    token_type: str = "Bearer"
    expires_in: int = Field(description="access_token 만료까지 남은 초")


class LogoutResponse(BaseModel):
    """POST /auth/logout 응답."""

    message: str = "logged out"