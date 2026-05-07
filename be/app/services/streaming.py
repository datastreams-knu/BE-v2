# be/app/services/streaming.py
"""AI 스트림을 받아 Pub/Sub으로 중계하는 백그라운드 작업."""

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.exceptions import AIServiceError
from app.core.logging import get_logger
from app.repositories.message import MessageRepository
from app.services.ai_client import AIClient
from app.services.pubsub import MessageStreamPublisher

logger = get_logger(__name__)


async def process_message_streaming(
    message_id: UUID,
    question: str,
    sessionmaker: async_sessionmaker[AsyncSession],
    ai_client: AIClient,
    publisher: MessageStreamPublisher,
) -> None:
    """백그라운드 작업: AI 스트림을 받아 Pub/Sub으로 중계 + DB 업데이트.

    이벤트 흐름:
    - AI에서 받은 token 이벤트 → 그대로 publish + answer_text 누적
    - meta 이벤트 → 그대로 publish + references/images 저장
    - done 이벤트 → DB에 최종 answer 저장 + publish

    실패 시 publish_error로 클라이언트에 전달.
    """
    # TODO: 본인 구현
    answer_text = ""
    references = []
    images = []
    chunks: list[str] = []
    try:
        async for event in ai_client.ask_streaming(question=question):
            event_type = event.get("type")

            if event_type == "token":
                chunks.append(event["content"])
                await publisher.publish(message_id=message_id, event=event)

            elif event_type == "meta":
                references = event.get("references", [])
                images = event.get("images", [])
                await publisher.publish(message_id=message_id, event=event)

            elif event_type == "done":
                answer_text = "".join(chunks)
                final_answer = {
                    "answer": answer_text,
                    "references": references,
                    "images": images,
                }
                async with sessionmaker() as session:
                    repo = MessageRepository(session)
                    message = await repo.get_by_id(message_id=message_id)
                    if message:
                        message.answer = final_answer
                        await session.commit()
                await publisher.publish(message_id, event)
                logger.info(
                            "message_streaming_completed", 
                            message_id=str(message_id), 
                            length=len(answer_text)
                        )
    except AIServiceError as e:
        await publisher.publish_error(message_id=message_id, error=str(e))
    except Exception as e:
        logger.exception(
                        "message_streaming_failed",
                        message_id=str(message_id)
                        )
        await publisher.publish_error(message_id, "internal error")
    