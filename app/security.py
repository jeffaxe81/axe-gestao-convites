"""Public API rate limiting and bearer parsing.

No proxy forwarding header is trusted unless an upstream proxy is explicitly configured.
The in-memory window is a defense-in-depth control, not a distributed rate limiter.
"""
import time
from collections import deque
from threading import Lock

from flask import request


class RequestRateLimiter:
    def __init__(self, limit: int, window_seconds: int = 60):
        self.limit = max(0, limit)
        self.window_seconds = window_seconds
        self._clients = {}
        self._lock = Lock()

    def allow(self, address: str) -> bool:
        if self.limit == 0:
            return True
        now = time.monotonic()
        with self._lock:
            bucket = self._clients.setdefault(address, deque())
            while bucket and bucket[0] <= now - self.window_seconds:
                bucket.popleft()
            if len(bucket) >= self.limit:
                return False
            bucket.append(now)
            # Remove expired empty entries periodically without growing memory unbounded.
            if len(self._clients) > 20000:
                for key, records in list(self._clients.items()):
                    if records[-1] <= now - self.window_seconds:
                        del self._clients[key]
            return True


def bearer_token() -> str | None:
    value = request.headers.get("Authorization", "")
    if not value.startswith("Bearer "):
        return None
    parts = value.split()
    return parts[1] if len(parts) == 2 and parts[0] == "Bearer" else None
