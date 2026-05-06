# be/app/core/security.py
"""JWT 토큰 발급 및 검증 유틸리티.

ADR-005: Access Token (15분) + Refresh Token (14일)
"""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from jose import JWTError, jwt
from pydantic import BaseModel

from app.core.config import settings


# === Constants ===

JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_TYPE = "access"
REFRESH_TOKEN_BYTES = 32  # 256 bits — 충분한 엔트로피


# === Payload schema ===

class JWTPayload(BaseModel):
    """Access Token의 payload 구조.

    type 필드로 access/refresh 구분.
    refresh는 jwt가 아니지만 일관성 차원에서 넣음.
    """

    sub: str        # User ID (UUID 문자열)
    iat: int        # Issued at (Unix timestamp)
    exp: int        # Expiration (Unix timestamp)
    type: str       # "access"


# === Access Token (JWT) ===

def create_access_token(user_id: UUID) -> str:
    """Access Token 발급.

    수명: settings.JWT_ACCESS_EXPIRE_MINUTES (기본 15분)
    """
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.JWT_ACCESS_EXPIRE_MINUTES)

    payload: dict[str, Any] = {
        "sub": str(user_id),
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "type": ACCESS_TOKEN_TYPE,
    }

    return jwt.encode(
        payload,
        settings.JWT_SECRET_KEY.get_secret_value(),
        algorithm=JWT_ALGORITHM,
    )


def decode_access_token(token: str) -> JWTPayload:
    """Access Token 검증 + 디코딩.

    검증 실패 시 InvalidTokenError 또는 ExpiredTokenError 던짐.
    """
    try:
        decoded = jwt.decode(
            token,
            settings.JWT_SECRET_KEY.get_secret_value(),
            algorithms=[JWT_ALGORITHM],
        )
    except jwt.ExpiredSignatureError as e:
        raise ExpiredTokenError() from e
    except JWTError as e:
        raise InvalidTokenError(str(e)) from e

    payload = JWTPayload.model_validate(decoded)

    # type 검증 (refresh가 access로 잘못 사용되지 않도록)
    if payload.type != ACCESS_TOKEN_TYPE:
        raise InvalidTokenError(f"wrong token type: {payload.type}")

    return payload


# === Refresh Token (random string) ===

def generate_refresh_token() -> str:
    """Refresh Token 생성.

    JWT 아닌 무작위 문자열 (URL-safe base64).
    이유: JWT는 payload 노출 — refresh token엔 의미 없는 데이터만 필요.
    """
    return secrets.token_urlsafe(REFRESH_TOKEN_BYTES)


def hash_refresh_token(token: str) -> str:
    """Refresh Token 해시.

    DB 저장용. SHA-256 hex (64자).
    bcrypt 안 쓰는 이유: token 자체가 고엔트로피라 무차별 대입 불가능.
    """
    return hashlib.sha256(token.encode()).hexdigest()


# === Exceptions ===

class TokenError(Exception):
    """모든 토큰 관련 예외의 부모."""


class InvalidTokenError(TokenError):
    """토큰이 무효함 (서명 오류, 형식 오류 등)."""


class ExpiredTokenError(TokenError):
    """토큰이 만료됨."""