# be/app/core/exceptions.py
"""도메인 예외 정의.

Service 계층에서 던지는 비즈니스 예외들.
HTTP 응답 변환은 API 계층에서 처리 (ADR-014).
"""

from uuid import UUID

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class DomainError(Exception):
    """모든 도메인 예외의 부모.

    API 계층에서 예외 핸들러로 일괄 처리하기 위함.
    """


class NotFoundError(DomainError):
    """리소스를 찾을 수 없을 때."""


class ConflictError(DomainError):
    """리소스 충돌"""


class ValidationError(DomainError):
    """비즈니스 검증 실패."""


# === User 도메인 ===

class UserNotFoundError(NotFoundError):
    def __init__(self, user_id: UUID | None = None, email: str | None = None):
        self.user_id = user_id
        self.email = email
        if user_id:
            msg = f"User not found: id={user_id}"
        elif email:
            msg = f"User not found: email={email}"
        else:
            msg = "User not found"
        super().__init__(msg)


class UserAlreadyExistsError(ConflictError):
    def __init__(self, email: str):
        self.email = email
        super().__init__(f"User already exists: email={email}")


class InvalidNicknameError(ValidationError):
    def __init__(self, nickname: str, reason: str):
        self.nickname = nickname
        self.reason = reason
        super().__init__(f"Invalid nickname '{nickname}': {reason}")


def register_exception_handlers(app: FastAPI) -> None:
    """글로벌 예외 핸들러 등록.

    main.py의 lifespan 또는 앱 초기화 시 호출.
    Phase 4 이후 RFC 9457 Problem Details로 확장 예정.
    """

    @app.exception_handler(NotFoundError)
    async def not_found_handler(request: Request, exc: NotFoundError) -> JSONResponse:
        return JSONResponse(
            status_code=404,
            content={"detail": str(exc)},
        )

    @app.exception_handler(ConflictError)
    async def conflict_handler(request: Request, exc: ConflictError) -> JSONResponse:
        return JSONResponse(
            status_code=409,
            content={"detail": str(exc)},
        )

    @app.exception_handler(ValidationError)
    async def validation_handler(request: Request, exc: ValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={"detail": str(exc)},
        )