"""Coverage for app.core.rate_limiter.

The rest of the suite stubs the limiter out (see conftest.bypass_rate_limiter);
every test here opts back in with the ``live_rate_limit`` marker so the real
sliding-window logic, and one real endpoint, run unstubbed.
"""
import time
import uuid

import pytest
import redis.asyncio as aioredis
from httpx import ASGITransport, AsyncClient

from app.core import rate_limiter
from app.core.config import settings
from app.core.exceptions import AppException
from app.main import app

pytestmark = pytest.mark.live_rate_limit

_LOCAL_REDIS_URL = "redis://127.0.0.1:6379/0"


def _clear_local_cache() -> None:
    rate_limiter._local_rate_limit_cache.clear()


def _reset_redis_client() -> None:
    # The module caches one client; each pytest-asyncio test runs in its own
    # event loop, so a cached client would be bound to a closed loop.
    rate_limiter._redis_client = None


async def _reachable_redis_url() -> str:
    """Prefer the configured URL, fall back to localhost for host-side test runs."""
    for url in (settings.REDIS_URL, _LOCAL_REDIS_URL):
        client = aioredis.from_url(url, decode_responses=True)
        try:
            await client.ping()
            await client.aclose()
            return url
        except Exception:
            await client.aclose()
    pytest.skip("No reachable Redis instance for the shared-bucket path")


def test_local_window_allows_up_to_limit_then_rejects():
    _clear_local_cache()
    key = f"unit:{uuid.uuid4().hex}"
    now = time.time()
    for _ in range(3):
        rate_limiter._local_check(key, limit=3, window_seconds=60, now=now)
    with pytest.raises(AppException) as exc:
        rate_limiter._local_check(key, limit=3, window_seconds=60, now=now)
    assert exc.value.status_code == 429
    assert exc.value.code == "RATE_LIMITED"
    assert exc.value.headers["Retry-After"] == "60"


def test_local_window_recovers_after_it_slides():
    _clear_local_cache()
    key = f"unit:{uuid.uuid4().hex}"
    start = time.time()
    for _ in range(2):
        rate_limiter._local_check(key, limit=2, window_seconds=10, now=start)
    with pytest.raises(AppException):
        rate_limiter._local_check(key, limit=2, window_seconds=10, now=start)
    # Once the window slides past the recorded stamps the key is usable again.
    rate_limiter._local_check(key, limit=2, window_seconds=10, now=start + 11)


def test_prune_local_drops_stale_keys():
    _clear_local_cache()
    key = f"unit:{uuid.uuid4().hex}"
    rate_limiter._local_rate_limit_cache[key] = [time.time() - 3600]
    rate_limiter._prune_local(time.time(), window_seconds=60)
    assert key not in rate_limiter._local_rate_limit_cache


@pytest.mark.asyncio
async def test_check_rate_limit_falls_back_to_memory_when_redis_fails(monkeypatch):
    _clear_local_cache()

    def _broken_redis():
        raise RuntimeError("redis unavailable")

    monkeypatch.setattr(rate_limiter, "_redis", _broken_redis)
    key = f"fallback:{uuid.uuid4().hex}"
    for _ in range(2):
        await rate_limiter.check_rate_limit(key, limit=2, window_seconds=60)
    with pytest.raises(AppException) as exc:
        await rate_limiter.check_rate_limit(key, limit=2, window_seconds=60)
    assert exc.value.status_code == 429


@pytest.mark.asyncio
async def test_check_rate_limit_uses_redis_when_available(monkeypatch):
    url = await _reachable_redis_url()
    client = aioredis.from_url(url, decode_responses=True)
    monkeypatch.setattr(rate_limiter, "_redis", lambda: client)

    key = f"redisunit:{uuid.uuid4().hex}"
    redis_key = f"rate_limit:{key}"
    try:
        for _ in range(2):
            await rate_limiter.check_rate_limit(key, limit=2, window_seconds=60)
        with pytest.raises(AppException) as exc:
            await rate_limiter.check_rate_limit(key, limit=2, window_seconds=60)
        assert exc.value.status_code == 429
    finally:
        await client.delete(redis_key)
        await client.aclose()


@pytest.mark.asyncio
async def test_login_endpoint_returns_429_after_budget():
    """End-to-end: 10 logins pass the limiter, the 11th is rejected with 429."""
    _clear_local_cache()
    _reset_redis_client()
    redis_client = rate_limiter._redis()
    redis_available = True
    try:
        await redis_client.ping()
        keys = await redis_client.keys("rate_limit:login:*")
        if keys:
            await redis_client.delete(*keys)
    except Exception:
        redis_available = False

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        body = {"email": "nobody@example.com", "password": "WrongPassword123!"}
        statuses = []
        for _ in range(11):
            res = await client.post("/v1/auth/login", json=body)
            statuses.append(res.status_code)
        assert statuses[-1] == 429, f"expected the 11th login to be limited, got {statuses}"
        assert res.json()["error"]["code"] == "RATE_LIMITED"
        # The first ten were all handed to the auth path (401), not limited.
        assert all(status == 401 for status in statuses[:10])

    if redis_available:
        keys = await redis_client.keys("rate_limit:login:*")
        if keys:
            await redis_client.delete(*keys)
