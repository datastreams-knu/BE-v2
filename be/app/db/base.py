# be/app/db/base.py
"""SQLAlchemy DeclarativeBase 정의.

모든 ORM 모델은 이 Base를 상속한다.
"""

from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from sqlalchemy import TIMESTAMP, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, mapped_column

# 자주 쓰는 컬럼 타입을 Annotated로 표준화
# UUID 기본값을 DB가 생성 (gen_random_uuid)
uuid_pk = Annotated[
    UUID,
    mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    ),
]

# 생성 시각
created_at = Annotated[
    datetime,
    mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
    ),
]


class Base(DeclarativeBase):
    def __repr__(self) -> str:
        cls_name = self.__class__.__name__
        pk_cols = [c.name for c in self.__table__.primary_key.columns]
        pk_repr = ", ".join(f"{c}={getattr(self, c)!r}" for c in pk_cols)
        return f"{cls_name}({pk_repr})"