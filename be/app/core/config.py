# be/app/core/config.py
"""애플리케이션 설정 — Pydantic Settings 기반.

ADR-009: .env 파일을 통한 시크릿 외부화
ADR-013: ENVIRONMENT 필드로 환경별 동작 분기
"""

from enum import StrEnum
from typing import Annotated

from pydantic import AnyUrl, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(StrEnum):
    """배포 환경 — 동작 분기에 사용."""

    DEVELOPMENT = "development"
    TEST = "test"
    PRODUCTION = "production"


class Settings(BaseSettings):
    """앱 설정. 누락된 필수 값은 기동 시점에 차단됨."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",  # .env에 정의된 모르는 키 무시 (다른 서비스용 변수)
    )

    # ===========================================
    # 환경
    # ===========================================
    ENVIRONMENT: Environment = Environment.DEVELOPMENT

    # ===========================================
    # 데이터베이스
    # ===========================================
    DATABASE_URL: str

    # ===========================================
    # Redis (ADR-007)
    # ===========================================
    REDIS_CACHE_URL: str
    REDIS_PUBSUB_URL: str

    # ===========================================
    # JWT (ADR-005)
    # ===========================================
    JWT_SECRET_KEY: SecretStr
    JWT_ACCESS_EXPIRE_MINUTES: Annotated[int, Field(ge=1, le=60)] = 15
    JWT_REFRESH_EXPIRE_DAYS: Annotated[int, Field(ge=1, le=90)] = 14

    # ===========================================
    # Google OAuth (ADR-005)
    # ===========================================
    GOOGLE_CLIENT_ID: str
    GOOGLE_CLIENT_SECRET: SecretStr
    GOOGLE_REDIRECT_URI: str

    # ===========================================
    # AI 서버
    # ===========================================
    AI_SERVER_URL: str

    # ===========================================
    # 로깅 (ADR-012)
    # ===========================================
    LOG_LEVEL: str = "INFO"

    # ===========================================
    # 환경 의존 동작 분기
    # ===========================================
    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == Environment.PRODUCTION

    @property
    def is_development(self) -> bool:
        return self.ENVIRONMENT == Environment.DEVELOPMENT

    @property
    def log_renderer(self) -> str:
        """환경별 로그 렌더러 결정.

        - 운영: JSON (로그 수집 도구 친화적, ADR-012)
        - 개발: Console (사람이 읽기 좋게 색상 + 들여쓰기)
        """
        return "json" if self.is_production else "console"


# 싱글턴 인스턴스 — 앱 전역에서 import
settings = Settings()  # type: ignore[call-arg]