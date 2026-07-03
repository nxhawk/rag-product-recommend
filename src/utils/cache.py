"""Cache - Cache kết quả để tối ưu hiệu suất."""
import hashlib
import json
from typing import Any


class SimpleCache:
    """In-memory cache with optional Redis backend."""

    def __init__(self, backend: str = "memory"):
        self.backend = backend
        self._store: dict[str, Any] = {}

    def get(self, key: str) -> Any | None:
        return self._store.get(key)

    def set(self, key: str, value: Any, ttl: int = 3600) -> None:
        self._store[key] = value

    def make_key(self, *args) -> str:
        raw = json.dumps(args, sort_keys=True, default=str)
        # Cache-key hashing only — not used for security, so MD5 is fine here.
        return hashlib.md5(raw.encode(), usedforsecurity=False).hexdigest()
