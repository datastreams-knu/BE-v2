# be/app/services/pubsub.py
"""Message 스트리밍 Pub/Sub Manager.

AI 서버 SSE → BE Pub/Sub → 클라이언트 SSE
"""

import json
from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID

from redis.asyncio import Redis

from app.core.logging import get_logger

logger = get_logger(__name__)


def _channel(message_id: UUID) -> str:
    """Pub/Sub 채널명 (Publisher·Subscriber 공유)."""
    return f"message:{message_id}"


class MessageStreamPublisher:
    """채널에 이벤트를 publish."""

    def __init__(self, redis: Redis):
        self.redis = redis

    async def publish(self, message_id: UUID, event: dict[str, Any]) -> None:
        """임의의 이벤트 publish.

        AI 서버에서 받은 이벤트를 그대로 전달하는 데 사용.
        """
        # TODO: 본인 구현
        channel = _channel(message_id=message_id)
        payload = json.dumps(event, ensure_ascii=False)
        await self.redis.publish(channel, payload)
        

    async def publish_error(self, message_id: UUID, error: str) -> None:
        """에러 이벤트 publish.

        백그라운드 작업 실패 시 호출.
        """
        # TODO: 본인 구현
        # 힌트: publish에 {"type": "error", "error": error} 전달
        await self.publish(message_id, {"type": "error", "error": error})


class MessageStreamSubscriber:
    """채널 subscribe + 이벤트 yield. SSE 엔드포인트에서 사용."""

    def __init__(self, redis: Redis):
        self.redis = redis

    async def subscribe(
        self,
        message_id: UUID,
    ) -> AsyncIterator[dict[str, Any]]:
        """채널 구독, 이벤트 yield.

        "done" 또는 "error" 이벤트 받으면 종료.
        """
        # TODO: 본인 구현
        channel = _channel(message_id=message_id)
        pubsub = self.redis.pubsub()
        await pubsub.subscribe(channel)

        try:
            async for message in pubsub.listen():
                if message["type"] != "message":
                    continue

                data = json.loads(message["data"])
                yield data

                if data.get("type") in ("done", "error"):
                    break
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.aclose()