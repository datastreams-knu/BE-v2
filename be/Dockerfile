# be/Dockerfile

# ===========================================
# Stage 1: Builder — 의존성 설치
# ===========================================
FROM python:3.12-slim AS builder

# uv 설치 (공식 권장 방식)
COPY --from=ghcr.io/astral-sh/uv:0.5.0 /uv /uvx /bin/

WORKDIR /app

# 의존성 파일만 먼저 복사 (Docker 캐시 효율)
COPY pyproject.toml uv.lock ./

# 의존성 설치 (가상환경은 /app/.venv에 생성)
# --frozen: lock 파일을 정확히 따름 (재해석 안 함)
# --no-install-project: 자기 자신은 설치 안 함 (코드는 별도 복사)
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv
RUN uv sync --frozen --no-install-project --no-dev

# ===========================================
# Stage 2: Runtime — 애플리케이션 실행
# ===========================================
FROM python:3.12-slim AS runtime

# healthcheck용 curl 설치
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# builder에서 가상환경만 가져옴
COPY --from=builder /app/.venv /app/.venv

# 애플리케이션 코드 복사
COPY ./app ./app
COPY ./migrations ./migrations
COPY ./alembic.ini ./

# 비루트 사용자 생성 및 권한 변경 (보안)
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# 가상환경의 실행 파일들이 PATH에 잡히도록
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]