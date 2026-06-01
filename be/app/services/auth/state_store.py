# be/app/services/auth/state_store.py
"""OAuth state·code_verifier 임시 저장소.

OAuth 시작 시점과 콜백 시점 사이에 code_verifier를 보관.
"""

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


@dataclass
class OAuthSession:
    code_verifier: str
    created_at: datetime


class OAuthStateStore:
    """state → OAuthSession 매핑.

    TTL: 10분
    """

    TTL_MINUTES = 10

    def __init__(self) -> None:
        self._store: dict[str, OAuthSession] = {}
        self._lock = asyncio.Lock()

    async def save(self, state: str, code_verifier: str) -> None:
        async with self._lock:
            self._store[state] = OAuthSession(
                code_verifier=code_verifier,
                created_at=datetime.now(timezone.utc),
            )
            self._cleanup_expired()

    async def pop(self, state: str) -> str | None:
        """code_verifier 꺼내기 + 삭제 (1회용).

        없거나 만료됐으면 None.
        """
        async with self._lock:
            session = self._store.pop(state, None)
            if session is None:
                return None

            # TTL 검증
            age = datetime.now(timezone.utc) - session.created_at
            if age > timedelta(minutes=self.TTL_MINUTES):
                return None

            return session.code_verifier

    def _cleanup_expired(self) -> None:
        """만료된 항목 청소. save() 시 매번 호출."""
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=self.TTL_MINUTES)
        expired_keys = [
            key for key, session in self._store.items()
            if session.created_at < cutoff
        ]
        for key in expired_keys:
            self._store.pop(key, None)


class RedisOAuthStateStore:
    """Redis 기반 state store.

    저장 형식:
    - Key:   oauth:state:{state}
    - Value: code_verifier (raw string)
    - TTL:   Redis EXPIRE로 자동 만료 — 직접 cleanup 불필요

    멀티워커 안전성:
    - GETDEL을 사용해 pop의 GET+DELETE를 원자적으로 처리
    - 동시 callback이 와도 한 워커만 code_verifier를 받음 (Redis 6.2+)
    """

    KEY_PREFIX = "oauth:state:"
    TTL_SECONDS = 10 * 60  # 10분 — 사용자가 Google 로그인 완료에 충분

    def __init__(self, redis: Redis):
        self._redis = redis

    def _key(self, state: str) -> str:
        return f"{self.KEY_PREFIX}{state}"

    async def save(self, state: str, code_verifier: str) -> None:
        await self._redis.set(
            self._key(state),
            code_verifier,
            ex=self.TTL_SECONDS,
        )

    async def pop(self, state: str) -> str | None:
        value = await self._redis.getdel(self._key(state))
        if value is None:
            return None
        # redis-py는 decode_responses 설정에 따라 str 또는 bytes 반환
        if isinstance(value, bytes):
            return value.decode("utf-8")
        return value