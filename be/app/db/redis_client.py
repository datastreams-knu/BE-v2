# be/app/db/redis_client.py
"""Redis 비동기 클라이언트."""

from redis.asyncio import Redis, from_url

from app.core.config import settings


def create_redis() -> Redis:
    return from_url(
        settings.REDIS_URL,
        encoding="utf-8",
        decode_responses=True,
        max_connections=20,
    )