# be/app/schemas/user.py

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

class UserResponse(BaseModel):
    """GET /users/me 응답"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: EmailStr
    nickname: str
    num_of_question: int
    joined_at: datetime


class UserUpdate(BaseModel):
    """PATCH /user/me 입력"""

    nickname: str | None = Field(
       default=None,
       min_length=2,
       max_length=20,
       description="새 닉네임",
   )

    