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



async def _save_message_answer(
    sessionmaker: async_sessionmaker[AsyncSession],
    message_id: UUID,
    answer_text: str,
    references: list[Any],
    images: list[Any],
    status: str,
    error: str | None = None,
) -> None:
    """Message.answer를 DB에 저장.

    어떤 종료 경로(정상/예외/done 누락)에서도 호출 가능해야 하므로
    내부 예외는 흡수하고 로깅만 한다 (백그라운드 태스크가 죽지 않도록).
    """
    final_answer: dict[str, Any] = {
        "answer": answer_text,
        "references": references,
        "images": images,
        "status": status,
    }
    if error is not None:
        final_answer["error"] = error

    try:
        async with sessionmaker() as session:
            repo = MessageRepository(session)
            message = await repo.get_by_id(message_id=message_id)
            if message is None:
                logger.warning(
                    "message_not_found_on_save",
                    message_id=str(message_id),
                )
                return
            message.answer = final_answer
            await session.commit()
    except Exception:
        logger.exception(
            "message_answer_save_failed",
            message_id=str(message_id),
            status=status,
        )


async def process_message_streaming(
    message_id: UUID,
    question: str,
    sessionmaker: async_sessionmaker[AsyncSession],
    ai_client: AIClient,
    publisher: MessageStreamPublisher,
) -> None:
    """백그라운드 작업: AI 스트림을 받아 Pub/Sub으로 중계 + DB 업데이트.

    이벤트 흐름:
    - token  → publish + chunks에 누적
    - meta   → publish + references/images 저장
    - done   → DB 확정 저장 후 publish (DB 먼저, 알림 나중)
    - 실패   → partial 답변 + status="failed"로 DB 저장 + publish_error

    어떤 경로로 끝나도 message.answer.status는 "pending"이 아니어야 한다.
    """
    chunks: list[str] = []
    references: list[Any] = []
    images: list[Any] = []
    saved = False
    error_message: str | None = None

    try:
        async for event in ai_client.ask_streaming(question=question):
            event_type = event.get("type")

            if event_type == "token":
                chunks.append(event.get("content", ""))
                await publisher.publish(message_id=message_id, event=event)

            elif event_type == "meta":
                references = event.get("references", [])
                images = event.get("images", [])
                await publisher.publish(message_id=message_id, event=event)

            elif event_type == "done":
                # DB 먼저 확정 → 그 다음 클라이언트에 done 알림
                # (반대 순서면 클라이언트가 완료 받고 새로고침했을 때 pending 보일 수 있음)
                answer_text = "".join(chunks)
                await _save_message_answer(
                    sessionmaker=sessionmaker,
                    message_id=message_id,
                    answer_text=answer_text,
                    references=references,
                    images=images,
                    status="completed",
                )
                saved = True
                await publisher.publish(message_id=message_id, event=event)
                logger.info(
                    "message_streaming_completed",
                    message_id=str(message_id),
                    length=len(answer_text),
                )
                break

        # for 루프가 done 없이 끝난 경우 (AI 서버가 done 안 보내고 stream 종료)
        if not saved and error_message is None:
            error_message = "AI stream ended without 'done' event"
            logger.warning(
                "message_streaming_no_done",
                message_id=str(message_id),
                tokens_received=len(chunks),
            )

    except AIServiceError as e:
        error_message = str(e)
        logger.warning(
            "message_streaming_ai_error",
            message_id=str(message_id),
            error=error_message,
        )

    except Exception:
        error_message = "internal error"
        logger.exception(
            "message_streaming_failed",
            message_id=str(message_id),
        )

    finally:
        # 실패 경로: partial 답변 보존 + status="failed" 저장 + 클라이언트 알림
        if not saved:
            await _save_message_answer(
                sessionmaker=sessionmaker,
                message_id=message_id,
                answer_text="".join(chunks),
                references=references,
                images=images,
                status="failed",
                error=error_message or "unknown error",
            )
            await publisher.publish_error(
                message_id=message_id,
                error=error_message or "unknown error",
            )