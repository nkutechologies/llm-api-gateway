"""
Simple in-memory response cache with TTL support.
Reduces redundant API calls for identical prompts.
"""

import hashlib
import time
from typing import Optional


class ResponseCache:
    """Thread-safe in-memory cache with TTL expiry."""

    def __init__(self, ttl: int = 3600, max_size: int = 1000):
        self.ttl = ttl
        self.max_size = max_size
        self._store: dict[str, dict] = {}

    def _make_key(self, prompt: str, model: str) -> str:
        """Generate a deterministic cache key from prompt + model."""
        raw = f"{model}::{prompt}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def get(self, prompt: str, model: str) -> Optional[str]:
        """Retrieve a cached response if it exists and hasn't expired."""
        key = self._make_key(prompt, model)
        entry = self._store.get(key)
        if entry is None:
            return None
        if time.time() - entry["timestamp"] > self.ttl:
            del self._store[key]
            return None
        return entry["response"]

    def put(self, prompt: str, model: str, response: str):
        """Store a response in cache. Evicts oldest entries if full."""
        if len(self._store) >= self.max_size:
            # Evict oldest entry
            oldest_key = min(self._store, key=lambda k: self._store[k]["timestamp"])
            del self._store[oldest_key]

        key = self._make_key(prompt, model)
        self._store[key] = {
            "response": response,
            "timestamp": time.time(),
        }

    def clear(self):
        """Clear all cached entries."""
        self._store.clear()

    @property
    def size(self) -> int:
        return len(self._store)
