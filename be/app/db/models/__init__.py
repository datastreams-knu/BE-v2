# be/app/db/models/__init__.py
"""모든 모델을 한 곳에서 import 가능하게.

Alembic의 autogenerate가 모든 모델을 인식하려면
이 파일에서 import되어 있어야 함.
"""

from app.db.models.chat import Chat
from app.db.models.message import Message
from app.db.models.refresh_token import RefreshToken
from app.db.models.user import User

__all__ = ["Chat", "Message", "RefreshToken", "User"]