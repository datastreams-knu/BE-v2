# be/app/api/v1/__init__.py
"""API v1 라우터 통합."""

from fastapi import APIRouter

from app.api.v1 import auth, users, chats, messages

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(users.router)
api_router.include_router(auth.router)
api_router.include_router(chats.router)
api_router.include_router(messages.router) 