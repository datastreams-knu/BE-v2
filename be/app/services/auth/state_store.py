# be/app/services/auth/state_store.py
"""OAuth state·code_verifier 임시 저장소.

OAuth 시작 시점과 콜백 시점 사이에 code_verifier를 보관.

현재 구현: in-memory dict (단일 프로세스에서만 동작)
TODO Phase 4 후속: Redis로 교체 (멀티 인스턴스 대응)
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

    TTL: 10분 (사용자가 OAuth 완료하기에 충분).
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