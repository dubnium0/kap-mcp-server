from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class _Entry:
    expires_at: float
    value: Any


class TTLCache:
    """Small async single-process TTL cache for reusable KAP metadata."""

    def __init__(self, ttl_seconds: float = 900, max_entries: int = 64) -> None:
        self.ttl_seconds = ttl_seconds
        self.max_entries = max_entries
        self._items: dict[str, _Entry] = {}
        self._lock = asyncio.Lock()

    async def get_or_load(self, key: str, loader: Callable[[], Awaitable[Any]]) -> Any:
        now = time.monotonic()
        cached = self._items.get(key)
        if cached and cached.expires_at > now:
            return cached.value
        async with self._lock:
            now = time.monotonic()
            cached = self._items.get(key)
            if cached and cached.expires_at > now:
                return cached.value
            value = await loader()
            if len(self._items) >= self.max_entries:
                oldest = min(self._items, key=lambda item: self._items[item].expires_at)
                del self._items[oldest]
            self._items[key] = _Entry(now + self.ttl_seconds, value)
            return value
