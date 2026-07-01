"""
Rate Limiter - Giới hạn tốc độ request để crawl lịch sự (polite crawling).
"""
import asyncio
import time


class RateLimiter:
    """Ensure a minimum delay between consecutive requests.

    Supports both sync (`wait`) and async (`await_ready`) usage so it can be
    shared by the sync HttpClient and async detail-page fetching.
    """

    def __init__(self, delay: float = 1.0):
        self.delay = delay
        self._last_call: float = 0.0
        self._lock = asyncio.Lock()

    def wait(self) -> None:
        """Block synchronously until the next request is allowed."""
        elapsed = time.monotonic() - self._last_call
        remaining = self.delay - elapsed
        if remaining > 0:
            time.sleep(remaining)
        self._last_call = time.monotonic()

    async def await_ready(self) -> None:
        """Async-safe wait between requests."""
        async with self._lock:
            elapsed = time.monotonic() - self._last_call
            remaining = self.delay - elapsed
            if remaining > 0:
                await asyncio.sleep(remaining)
            self._last_call = time.monotonic()
