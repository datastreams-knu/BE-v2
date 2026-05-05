# be/app/middleware/correlation.py
"""Correlation ID 미들웨어 — 분산 추적의 시작점.

ADR-012: ULID 기반 ID + 클라이언트 ID 검증 후 사용
"""

import re
from typing import Any

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from ulid import ULID

# ULID 형식 검증용 정규식
# Crockford's Base32 (26자) — 0~9, A~Z 중 일부 글자만
_ULID_PATTERN = re.compile(r"^[0-9A-HJKMNP-TV-Z]{26}$")

# HTTP 헤더 이름 (대소문자 무관하지만 표준 컨벤션)
_HEADER_NAME = "X-Correlation-ID"

# contextvars 바인딩 키
_CONTEXT_KEY = "correlation_id"


def _is_valid_ulid(value: str) -> bool:
    """클라이언트가 보낸 ID가 유효한 ULID 형식인지 검증.

    형식이 아니면 False — 새로 생성한다.
    """
    return bool(_ULID_PATTERN.match(value))


class CorrelationIDMiddleware(BaseHTTPMiddleware):
    """모든 요청에 Correlation ID 부여.

    동작:
    1. 요청 헤더 X-Correlation-ID 검사
       - 유효한 ULID면 그대로 사용
       - 없거나 형식 부적합이면 새로 생성
    2. structlog contextvars에 바인딩 → 이번 요청의 모든 로그에 자동 포함
    3. 응답 헤더 X-Correlation-ID에 동일 값 echo
    """

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        client_id = request.headers.get(_HEADER_NAME)

        if client_id and _is_valid_ulid(client_id):
            correlation_id = client_id
        else:
            correlation_id = str(ULID())

        # contextvars에 바인딩
        # → 이 요청을 처리하는 동안 호출되는 모든 logger에 자동 포함
        structlog.contextvars.bind_contextvars(**{_CONTEXT_KEY: correlation_id})

        try:
            response = await call_next(request)
        finally:
            # 요청 종료 시 contextvars 정리
            # 안 하면 다른 요청에 누설될 위험
            structlog.contextvars.clear_contextvars()

        # 응답에도 동일 ID 포함 (클라이언트가 로그 추적에 사용 가능)
        response.headers[_HEADER_NAME] = correlation_id
        return response