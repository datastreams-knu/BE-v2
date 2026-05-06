# be/app/api/v1/auth.py
"""Auth API 엔드포인트.

ADR-005: OAuth + JWT
ADR-014: REST 명명 규칙
"""

from typing import Annotated

from fastapi import APIRouter, Cookie, HTTPException, Query, Request, Response, status
from fastapi.responses import RedirectResponse

from app.api.deps import AuthServiceDep, CurrentUserIdDep
from app.core.config import settings
from app.schemas.auth import LoginStartResponse, LogoutResponse, TokenResponse

router = APIRouter(prefix="/auth", tags=["auth"])


# === Cookie 설정 ===

REFRESH_COOKIE_NAME = "refresh_token"

# Cookie 보안 설정 (운영 환경에서는 secure=True 필수)
def _set_refresh_cookie(response: Response, refresh_token: str) -> None:
    """Refresh Token을 HttpOnly Cookie로 설정 (ADR-005)."""
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=refresh_token,
        max_age=settings.JWT_REFRESH_EXPIRE_DAYS * 24 * 60 * 60,  # 초 단위
        httponly=True,                          # JavaScript 접근 차단
        secure=settings.is_production,          # 운영: HTTPS만, 개발: HTTP 허용
        samesite="lax",                         # CSRF 방어 + OAuth 콜백 호환
        path="/api/v1/auth",                    # auth 엔드포인트에만 전송
    )


def _clear_refresh_cookie(response: Response) -> None:
    """Refresh Cookie 삭제."""
    response.delete_cookie(
        key=REFRESH_COOKIE_NAME,
        path="/api/v1/auth",
    )


# === Routes ===

@router.post("/google/login", response_model=LoginStartResponse)
async def google_login_start(
    auth_service: AuthServiceDep,
) -> LoginStartResponse:
    """Google OAuth 로그인 시작.

    프론트엔드는 응답의 authorization_url로 사용자를 리다이렉트.
    """
    result = await auth_service.start_oauth_login()
    return LoginStartResponse(
        authorization_url=result.authorization_url,
        state=result.state,
    )


@router.get("/google/callback")
async def google_login_callback(
    request: Request,
    auth_service: AuthServiceDep,
    code: Annotated[str, Query(description="Google이 보낸 인증 코드")],
    state: Annotated[str, Query(description="시작 시 발급한 state")],
    error: Annotated[str | None, Query(description="OAuth 에러")] = None,
) -> RedirectResponse:
    """Google OAuth 콜백.

    Google이 사용자 인증 후 이 엔드포인트로 리다이렉트.

    동작:
    1. 토큰 교환 + 사용자 매칭/가입
    2. Access Token은 응답으로, Refresh Token은 Cookie로
    3. 프론트엔드 페이지로 리다이렉트
    """
    # OAuth 에러 케이스 (사용자가 동의 거부 등)
    if error:
        raise HTTPException(
            status_code=400,
            detail=f"OAuth error: {error}",
        )

    # 사용자 메타데이터 (선택)
    user_agent = request.headers.get("user-agent")
    ip_address = request.client.host if request.client else None

    # 토큰 발급
    token_pair = await auth_service.handle_oauth_callback(
        code=code,
        state=state,
        user_agent=user_agent,
        ip_address=ip_address,
    )

    # 응답 — 프론트엔드로 리다이렉트하면서 access_token을 fragment로 전달
    # 임시 방식 (프론트엔드 통합 후 변경 가능)
    redirect_url = (
        f"/auth/success"
        f"#access_token={token_pair.access_token}"
        f"&expires_in={token_pair.access_expires_in}"
    )
    response = RedirectResponse(url=redirect_url, status_code=302)

    # Refresh Token을 Cookie로
    _set_refresh_cookie(response, token_pair.refresh_token)

    return response


@router.post("/refresh", response_model=TokenResponse)
async def refresh_tokens(
    request: Request,
    response: Response,
    auth_service: AuthServiceDep,
    refresh_token: Annotated[str | None, Cookie()] = None,
) -> TokenResponse:
    """토큰 갱신.

    Cookie의 refresh_token으로 새 access + refresh 발급 (Rotation).
    """
    if refresh_token is None:
        raise HTTPException(
            status_code=401,
            detail="refresh_token cookie missing",
        )

    user_agent = request.headers.get("user-agent")
    ip_address = request.client.host if request.client else None

    new_pair = await auth_service.refresh_tokens(
        refresh_token=refresh_token,
        user_agent=user_agent,
        ip_address=ip_address,
    )

    # 새 Refresh Token을 Cookie로 (기존 덮어쓰기)
    _set_refresh_cookie(response, new_pair.refresh_token)

    return TokenResponse(
        access_token=new_pair.access_token,
        expires_in=new_pair.access_expires_in,
    )


@router.post("/logout", response_model=LogoutResponse)
async def logout(
    response: Response,
    user_id: CurrentUserIdDep,
    auth_service: AuthServiceDep,
) -> LogoutResponse:
    """로그아웃.

    현재 사용자의 모든 Refresh Token 무효화 + Cookie 삭제.
    Access Token은 클라이언트가 자체 폐기 (서버는 stateless).
    """
    await auth_service.logout(user_id)
    _clear_refresh_cookie(response)
    return LogoutResponse()