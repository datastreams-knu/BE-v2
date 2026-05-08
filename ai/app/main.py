# mock AI 서버 (위치는 본인 프로젝트의 ai 서버 경로)

import asyncio
import json
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AIRequest(BaseModel):
    question: str


@app.get("/health")
async def health():
    return {"status": "ok"}


# === 진짜 LLM 스트리밍 시뮬레이션 ===

MOCK_ANSWER = (
    "수강신청은 2026년 8월 25일부터 9월 5일까지 진행됩니다. "
    "정정 기간은 9월 6일부터 9월 12일까지이며, "
    "수강확정 기간은 9월 15일부터 9월 19일까지입니다."
)

MOCK_REFERENCES = [
    {"title": "학사일정", "url": "https://example.com/calendar"},
    {"title": "수강신청 안내", "url": "https://example.com/enrollment"},
]

MOCK_IMAGES = ["https://example.com/calendar.jpg"]


@app.post("/ai/ai-response")
async def ai_response(payload: AIRequest):
    """SSE 스트리밍 응답.

    실제 LLM(OpenAI, Anthropic 등)이 토큰 생성하는 동작을 시뮬레이션.
    """
    async def generate():
        # 1. 토큰 단위 스트리밍 (실제 LLM은 1~3 글자 단위)
        for char in MOCK_ANSWER:
            event = {"type": "token", "content": char}
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
            await asyncio.sleep(0.3)  # 토큰당 30ms (실제 LLM 시뮬레이션)

        # 2. 메타데이터 (references, images) 마지막에 한 번
        meta_event = {
            "type": "meta",
            "references": MOCK_REFERENCES,
            "images": MOCK_IMAGES,
        }
        yield f"data: {json.dumps(meta_event, ensure_ascii=False)}\n\n"

        # 3. 완료 신호
        done_event = {"type": "done"}
        yield f"data: {json.dumps(done_event, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )