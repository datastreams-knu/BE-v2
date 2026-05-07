# be/app/api/deps.py
"""FastAPI 의존성 주입 함수들.

라우트 함수가 필요로 하는 객체들(Service, Repository 등)을
FastAPI Depends로 자동 주입할 수 있게 만드는 provider 함수들.
"""

from typing import Annotated
from uuid import UUID

from fastapi import Depends
from fastapi import Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.repositories.user import UserRepository
from app.services.user import UserService

from app.repositories.chat import ChatRepository
from app.services.chat import ChatService

from app.repositories.message import MessageRepository
from app.services.message import MessageService

import httpx
from fastapi import Request

from app.services.auth.providers import GoogleOAuthProvider

from app.services.ai_client import AIClient

from app.core.security import decode_access_token
from app.repositories.refresh_token import RefreshTokenRepository
from app.services.auth.providers import OAuthProvider
from app.services.auth.service import AuthService
from app.services.auth.state_store import OAuthStateStore

from redis.asyncio import Redis


# === Type aliases ===
# 라우트 함수에서 반복되는 의존성을 짧게 표현하기 위한 별칭

DbSession = Annotated[AsyncSession, Depends(get_db)]


# === Repository providers ===

def get_user_repo(session: DbSession) -> UserRepository:
    """UserRepository 인스턴스 제공.

    같은 요청 내에서 같은 session을 공유.
    """
    return UserRepository(session)


UserRepoDep = Annotated[UserRepository, Depends(get_user_repo)]


# === Service providers ===

def get_user_service(
    session: DbSession,
    user_repo: UserRepoDep,
) -> UserService:
    """UserService 인스턴스 제공.

    Repository와 Session 모두 주입받음.
    """
    return UserService(session=session, user_repo=user_repo)


UserServiceDep = Annotated[UserService, Depends(get_user_service)]


def get_http_client(request: Request) -> httpx.AsyncClient:
    """lifespan에서 만든 공유 httpx 클라이언트."""
    return request.app.state.http_client


def get_google_provider(
    http_client: Annotated[httpx.AsyncClient, Depends(get_http_client)],
) -> GoogleOAuthProvider:
    return GoogleOAuthProvider(http_client)


GoogleProviderDep = Annotated[GoogleOAuthProvider, Depends(get_google_provider)]


# === RefreshTokenRepository ===

def get_refresh_token_repo(session: DbSession) -> RefreshTokenRepository:
    return RefreshTokenRepository(session)


RefreshTokenRepoDep = Annotated[
    RefreshTokenRepository, Depends(get_refresh_token_repo)
]


# === OAuth State Store ===

_state_store_singleton = OAuthStateStore()


def get_state_store() -> OAuthStateStore:
    """OAuth state store는 앱 전체가 공유하는 싱글턴.

    in-memory dict 기반이라 같은 인스턴스를 모든 요청이 공유해야 함.
    """
    return _state_store_singleton


StateStoreDep = Annotated[OAuthStateStore, Depends(get_state_store)]


# === AuthService ===

def get_auth_service(
    session: DbSession,
    oauth_provider: GoogleProviderDep,
    state_store: StateStoreDep,
    user_service: UserServiceDep,
    token_repo: RefreshTokenRepoDep,
) -> AuthService:
    return AuthService(
        session=session,
        oauth_provider=oauth_provider,
        state_store=state_store,
        user_service=user_service,
        token_repo=token_repo,
    )


AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]


async def get_current_user_id(
    authorization: Annotated[str | None, Header()] = None,
) -> UUID:
    """Authorization 헤더에서 JWT를 추출해 user_id 반환.

    Phase 4까지의 임시 구현을 대체.
    `Authorization: Bearer <jwt>` 형식 기대.
    """
    if authorization is None:
        raise HTTPException(
            status_code=401,
            detail="missing Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Bearer 스키마 파싱
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=401,
            detail="invalid Authorization format (expected 'Bearer <token>')",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = parts[1]

    # JWT 검증 (예외는 글로벌 핸들러가 401로 변환)
    payload = decode_access_token(token)
    return UUID(payload.sub)


CurrentUserIdDep = Annotated[UUID, Depends(get_current_user_id)]


def get_chat_repo(session: DbSession) -> ChatRepository:
    return ChatRepository(session)


ChatRepoDep = Annotated[ChatRepository, Depends(get_chat_repo)]


def get_chat_service(
    session: DbSession,
    chat_repo: ChatRepoDep,
) -> ChatService:
    return ChatService(session=session, chat_repo=chat_repo)


ChatServiceDep = Annotated[ChatService, Depends(get_chat_service)]


def get_message_repo(session: DbSession) -> MessageRepository:
    return MessageRepository(session)


MessageRepoDep = Annotated[MessageRepository, Depends(get_message_repo)]


def get_ai_client(
    http_client: Annotated[httpx.AsyncClient, Depends(get_http_client)],
) -> AIClient:
    return AIClient(http_client)


AIClientDep = Annotated[AIClient, Depends(get_ai_client)]


def get_message_service(
    session: DbSession,
    message_repo: MessageRepoDep,
    chat_service: ChatServiceDep,
    ai_client: AIClientDep,
) -> MessageService:
    return MessageService(
        session=session,
        message_repo=message_repo,
        chat_service=chat_service,
        ai_client=ai_client,
    )


MessageServiceDep = Annotated[MessageService, Depends(get_message_service)]


def get_redis(request: Request) -> Redis:
    return request.app.state.redis


RedisDep = Annotated[Redis, Depends(get_redis)]


