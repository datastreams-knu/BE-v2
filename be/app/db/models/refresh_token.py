# be/app/db/models/refresh_token.py
"""RefreshToken 모델 — ADR-005 Refresh Token Rotation."""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import TIMESTAMP, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import INET, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, created_at, uuid_pk

if TYPE_CHECKING:
    from app.db.models.user import User


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"
    __table_args__ = (
        # 만료 토큰 정리 시 사용
        Index("ix_refresh_tokens_expires_at", 
              "expires_at",
        ),
        # 사용자별 활성 토큰 조회
        Index(
            "ix_refresh_tokens_user_active",
            "user_id",
            "revoked_at",
        ),
    )

    id: Mapped[uuid_pk]
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    # 평문 저장 금지 (ADR-005) — SHA-256 해시만 저장
    token_hash: Mapped[str] = mapped_column(
        String(64),  # SHA-256 hex = 64자
        unique=True,
        nullable=False,
    )

    issued_at: Mapped[created_at]

    expires_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
    )

    # NULL이면 활성, 값 있으면 무효화됨
    revoked_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True),
    )

    # Rotation 추적 (탈취 탐지용 — ADR-005)
    replaced_by_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("refresh_tokens.id", ondelete="SET NULL"),
    )

    # 메타데이터
    user_agent: Mapped[str | None] = mapped_column(String(500))
    ip_address: Mapped[str | None] = mapped_column(INET)

    user: Mapped["User"] = relationship(back_populates="refresh_tokens", lazy="raise")