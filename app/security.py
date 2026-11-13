"""Public API rate limiting and bearer parsing.

No proxy forwarding header is trusted unless an upstream proxy is explicitly configured.
The in-memory window is a defense-in-depth control, not a distributed rate limiter.
"""
import time
from collections import OrderedDict, deque
from threading import Lock

from flask import request


class RequestRateLimiter:
    def __init__(self, limit: int, window_seconds: int = 60,
                 max_clients: int = 20000):
        if not isinstance(max_clients, int) or isinstance(max_clients, bool) or max_clients < 1:
            raise ValueError("max_clients deve ser positivo.")
        if window_seconds <= 0:
            raise ValueError("window_seconds deve ser positivo.")
        self.limit = max(0, limit)
        self.window_seconds = window_seconds
        self.max_clients = max_clients
        # Ordenado pelo último acesso *permitido*. Um IP que só recebe 429
        # não pode deslocar entradas ativas e burlar a capacidade máxima.
        self._clients = OrderedDict()
        self._lock = Lock()

    def allow(self, address: str) -> bool:
        if self.limit == 0:
            return True
        now = time.monotonic()
        cutoff = now - self.window_seconds
        with self._lock:
            bucket = self._clients.get(address)
            if bucket is None:
                if len(self._clients) >= self.max_clients:
                    # O bucket mais antigo tem o menor último acesso
                    # permitido. Se ainda está ativo, todos os demais
                    # também estão: rejeitar sem percorrer 20 mil IPs.
                    oldest_key, oldest_bucket = next(iter(self._clients.items()))
                    if oldest_bucket[-1] > cutoff:
                        return False
                    del self._clients[oldest_key]
                bucket = deque()
                self._clients[address] = bucket
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()
            if len(bucket) >= self.limit:
                return False
            bucket.append(now)
            self._clients.move_to_end(address)
            return True


def bearer_token() -> str | None:
    value = request.headers.get("Authorization", "")
    if not value.startswith("Bearer "):
        return None
    parts = value.split()
    return parts[1] if len(parts) == 2 and parts[0] == "Bearer" else None
