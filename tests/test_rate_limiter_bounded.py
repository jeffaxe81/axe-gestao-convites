"""Bounded in-memory rate limiting, including saturation and expiry."""
from concurrent.futures import ThreadPoolExecutor

import pytest

from app.security import RequestRateLimiter


def test_limit_per_client_and_expiry(monkeypatch):
    clock = [100.0]
    monkeypatch.setattr("app.security.time.monotonic", lambda: clock[0])
    limiter = RequestRateLimiter(2, window_seconds=60, max_clients=2)
    assert limiter.allow("client-a")
    assert limiter.allow("client-a")
    assert not limiter.allow("client-a")
    assert limiter.allow("client-b")
    assert len(limiter._clients) == 2
    clock[0] = 161.0
    assert limiter.allow("client-a")


def test_full_capacity_denies_new_client_without_evicting_active():
    limiter = RequestRateLimiter(1, max_clients=2)
    assert limiter.allow("a")
    assert limiter.allow("b")
    assert not limiter.allow("c")
    assert list(limiter._clients) == ["a", "b"]
    assert not limiter.allow("a")
    assert len(limiter._clients) == 2


def test_expired_oldest_is_replaced_in_constant_work(monkeypatch):
    clock = [10.0]
    monkeypatch.setattr("app.security.time.monotonic", lambda: clock[0])
    limiter = RequestRateLimiter(3, window_seconds=60, max_clients=2)
    assert limiter.allow("a")
    clock[0] = 30.0
    assert limiter.allow("b")
    clock[0] = 50.0
    assert limiter.allow("a")  # 'b' now oldest, but still active.
    clock[0] = 91.0
    assert limiter.allow("c")  # 'b' expired; keep the newer 'a'.
    assert list(limiter._clients) == ["a", "c"]
    assert not limiter.allow("b")


def test_rejected_requests_cannot_keep_oldest_bucket_alive(monkeypatch):
    clock = [1.0]
    monkeypatch.setattr("app.security.time.monotonic", lambda: clock[0])
    limiter = RequestRateLimiter(1, window_seconds=60, max_clients=2)
    assert limiter.allow("a")
    clock[0] = 2.0
    assert limiter.allow("b")
    clock[0] = 3.0
    assert not limiter.allow("a")
    assert list(limiter._clients) == ["a", "b"]
    clock[0] = 62.0
    assert limiter.allow("c")
    assert list(limiter._clients) == ["b", "c"]


def test_disabled_limiter_does_not_allocate_client_state():
    limiter = RequestRateLimiter(0, max_clients=1)
    for address in range(200):
        assert limiter.allow(str(address))
    assert not limiter._clients


def test_concurrent_requests_never_exceed_shared_limit():
    limiter = RequestRateLimiter(5, max_clients=1)
    with ThreadPoolExecutor(max_workers=16) as pool:
        permitted = list(pool.map(limiter.allow, ["same-client"] * 100))
    assert sum(permitted) == 5
    assert len(limiter._clients) == 1


@pytest.mark.parametrize("capacity", [0, -1, True, None])
def test_invalid_client_capacity_is_rejected(capacity):
    with pytest.raises(ValueError, match="max_clients"):
        RequestRateLimiter(10, max_clients=capacity)
