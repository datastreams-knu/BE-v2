# be/app/db/models/user.py

from typing import TYPE_CHECKING
from app.db.base import Base, uuid_pk, created_at
from sqlalchemy import String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship


if TYPE_CHECKING:
    from app.db.models.chat import Chat
    from app.db.models.refresh_token import RefreshToken


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("oauth_provider", "oauth_subject", name="uq_users_oauth"),
    )

    # Metadata of columns
    id: Mapped[uuid_pk]
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
    )
    nickname: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )
    password_hash: Mapped[str | None] = mapped_column(String(255))
    oauth_provider: Mapped[str | None] = mapped_column(String(20))
    oauth_subject: Mapped[str | None] = mapped_column(String(255))
    num_of_question: Mapped[int] = mapped_column(
        default=0,
        nullable=False,
    )
    joined_at: Mapped[created_at]

    # Relation to other tables
    chats: Mapped[list["Chat"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="raise",
    )
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="raise",
    )
