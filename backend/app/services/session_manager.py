import asyncio
from collections import OrderedDict
from uuid import UUID

from app.config import get_settings
from app.services.gemini_chain import SessionMemory

settings = get_settings()


class SessionManager:
    """In-memory scopes for concurrent WebSocket chat sessions (max 20)."""

    def __init__(self, max_sessions: int | None = None) -> None:
        self._max = max_sessions or settings.max_concurrent_sessions
        self._memories: OrderedDict[str, SessionMemory] = OrderedDict()
        self._locks: dict[str, asyncio.Lock] = {}
        self._global_lock = asyncio.Lock()

    async def register(self, session_id: UUID, memory: SessionMemory) -> bool:
        key = str(session_id)
        async with self._global_lock:
            if key in self._memories:
                return True
            if len(self._memories) >= self._max:
                # Evict oldest (LRU)
                oldest_key, _ = self._memories.popitem(last=False)
                self._locks.pop(oldest_key, None)
            self._memories[key] = memory
            self._locks[key] = asyncio.Lock()
            return True

    async def get_memory(self, session_id: UUID) -> SessionMemory | None:
        return self._memories.get(str(session_id))

    async def get_lock(self, session_id: UUID) -> asyncio.Lock | None:
        return self._locks.get(str(session_id))

    async def unregister(self, session_id: UUID) -> None:
        key = str(session_id)
        async with self._global_lock:
            self._memories.pop(key, None)
            self._locks.pop(key, None)

    def active_count(self) -> int:
        return len(self._memories)


session_manager = SessionManager()
