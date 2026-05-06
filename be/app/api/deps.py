# be/app/api/deps.py
"""FastAPI 의존성 주입 함수들.

라우트 함수가 필요로 하는 객체들(Service, Repository 등)을
FastAPI Depends로 자동 주입할 수 있게 만드는 provider 함수들.
"""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.repositories.user import UserRepository
from app.services.user import UserService


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