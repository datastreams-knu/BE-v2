# be/app/services/ai_client.py
"""
AI 서버 통신 클라이언트.

책임:
- HTTP 통신 (httpx)
- 타임아웃·에러 변환
- 향후 Provider 추상화 가능 (현재는 단일 v1 AI 서버)
"""

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.core.config import settings
from app.core.exceptions import AIServiceError
from app.core.logging import get_logger

logger = get_logger(__name__)


class AIClient:
    """
    v1 AI 서버 (knu-chatbot-ai 컨테이너) 통신.

    엔드포인트: POST /ai/ai-response
    요청: {"question": str}
    응답: {"answer": str, "references": [...], "images": [...]}
          (disclaimer는 BE에서 추가, AI 서버는 반환 안 함)
    """

    AI_RESPONSE_PATH = "/ai/ai-response"
    REQUEST_TIMEOUT = 30.0  # AI 응답 시간 고려

    def __init__(self, http_client: httpx.AsyncClient):
        self._http = http_client

    async def ask(self, question: str) -> dict[str, Any]:
        """AI 서버에 질문, 응답 반환.

        Returns:
            {"answer": str, "references": list, "images": list}

        Raises:
            AIServiceError: 통신 실패, 타임아웃, 응답 형식 오류
        """
        url = f"{settings.AI_SERVICE_URL}{self.AI_RESPONSE_PATH}"

        try:
            response = await self._http.post(
                url,
                json={"question": question},
                timeout=self.REQUEST_TIMEOUT,
            )
        except httpx.TimeoutException as e:
            logger.error("ai_request_timeout", question_length=len(question))
            raise AIServiceError("AI server timeout") from e
        except httpx.RequestError as e:
            logger.error("ai_request_failed", error=str(e))
            raise AIServiceError(f"AI server unreachable: {e}") from e

        if response.status_code != 200:
            logger.error(
                "ai_response_error",
                status=response.status_code,
                body=response.text[:500],   # 전체 본문은 너무 길 수 있음
            )
            raise AIServiceError(f"AI server returned {response.status_code}")

        try:
            data = response.json()
        except Exception as e:
            raise AIServiceError(f"AI response not JSON: {e}") from e

        # 응답 형식 검증
        required_keys = {"answer", "references", "images"}
        missing = required_keys - data.keys()
        if missing:
            raise AIServiceError(f"AI response missing keys: {missing}")

        return {
            "answer": data["answer"],
            "references": data["references"],
            "images": data["images"],
        }
    
    async def ask_streaming(self, question: str) -> AsyncIterator[dict[str, Any]]:
        """AI 서버에 질문 + SSE 스트림 받기.

        Yields:
            각 SSE 이벤트의 파싱된 dict
            예: {"type": "token", "content": "수"}
                {"type": "meta", "references": [...], "images": [...]}
                {"type": "done"}

        Raises:
            AIServiceError: 통신 실패, 타임아웃, 형식 오류
        """
        url = f"{settings.AI_SERVICE_URL}{self.AI_RESPONSE_PATH}"

        try:
            async with self._http.stream("POST", url, json={"question": question}, timeout=self.REQUEST_TIMEOUT) as response:
                if response.status_code != 200:
                    body = await response.aread()
                    logger.error("ai_response_error", status=response.status_code, body=body[:500])
                    raise AIServiceError(f"AI server returned {response.status_code}")

                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue   # 빈 줄, 주석 등 무시

                    payload = line[len("data: "):]
                    try:
                        event = json.loads(payload)
                    except json.JSONDecodeError:
                        logger.warning("ai_invalid_sse_line", line=payload)
                        continue
                    yield event
        except httpx.TimeoutException as e:
            raise AIServiceError("AI server timeout") from e
        except httpx.RequestError as e:
            raise AIServiceError(f"AI server unreachable: {e}") from e
        