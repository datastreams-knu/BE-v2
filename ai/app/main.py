# app/main.py

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health Check
@app.get("/health")
async def health():
    return {
        "status": "ok"
    }

# Mock AI Response
@app.post("/ai/ai-response")
async def ai_response():
    return {
        "answer": "mock answer",
        "references": [
            {
                "title": "mock reference",
                "url": "https://example.com"
            }
        ],
        "disclaimer": "항상 정확한 답변을 제공하지 못할 수 있습니다. 아래의 URL들을 참고하여 정확하고 자세한 정보를 확인하세요.",
        "images": [
            "https://example.com/mock-image.jpg"
        ]
    }