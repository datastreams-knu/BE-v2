# be/app/core/logging.py
"""구조화 로깅 설정 — structlog 기반.

ADR-012: JSON 출력 + Correlation ID 자동 포함 + PII 마스킹
"""

import logging
import sys
from typing import Any

import structlog
from structlog.types import EventDict, Processor

from app.core.config import settings

# PII로 간주할 키 (대소문자 무관 부분 일치)
_SENSITIVE_KEYS = frozenset({
    "password",
    "passwd",
    "secret",
    "token",
    "authorization",
    "api_key",
    "apikey",
    "credit_card",
    "ssn",
})


def _mask_sensitive(
    _logger: Any,
    _method_name: str,
    event_dict: EventDict,
) -> EventDict:
    """민감 정보를 가진 키를 ***REDACTED***로 마스킹.

    structlog processor 시그니처를 따름.
    """
    for key in list(event_dict.keys()):
        if any(s in key.lower() for s in _SENSITIVE_KEYS):
            event_dict[key] = "***REDACTED***"
    return event_dict


def _build_processors(*, json_output: bool) -> list[Processor]:
    """환경별 processor 체인 구성.

    개발: 사람 가독성 우선 (ConsoleRenderer)
    운영: 기계 처리 우선 (JSONRenderer)
    """
    shared: list[Processor] = [
        # contextvars에 바인딩된 값(correlation_id 등)을 모든 로그에 자동 추가
        structlog.contextvars.merge_contextvars,
        # 로그 레벨 정보를 event_dict에 추가
        structlog.processors.add_log_level,
        # ISO 8601 형식의 타임스탬프
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        # 예외 발생 시 traceback을 dict로 변환
        structlog.processors.dict_tracebacks,
        # 민감 정보 마스킹 (커스텀)
        _mask_sensitive,
    ]

    if json_output:
        # 운영: JSON 한 줄 출력
        return [*shared, structlog.processors.JSONRenderer()]
    else:
        # 개발: 색상 + 들여쓰기로 가독성
        return [*shared, structlog.dev.ConsoleRenderer(colors=True)]


def configure_logging() -> None:
    """앱 기동 시 1회 호출.

    - structlog 자체 설정
    - 표준 logging 라이브러리도 같은 형식으로 출력 (uvicorn 로그 등)
    """
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    json_output = settings.log_renderer == "json"

    processors = _build_processors(json_output=json_output)

    # structlog 본체 설정
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # 표준 logging도 structlog 형식으로 출력
    # uvicorn, sqlalchemy 등이 표준 logging을 사용하기 때문
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """모듈에서 logger 인스턴스를 얻을 때 사용.

    사용 예: logger = get_logger(__name__)
    """
    return structlog.get_logger(name)