import ipaddress
import logging
import time
import uuid
from typing import Optional

import redis.asyncio as aioredis
from fastapi import Request, status

from app.core.config import settings
from app.core.exceptions import AppException

logger = logging.getLogger("matchlambda")

# Single-process fallback. Expired keys are pruned; the map is hard-capped.
_local_rate_limit_cache: dict[str, list[float]] = {}
_LOCAL_CACHE_MAX_KEYS = 10000
_redis_client: Optional[aioredis.Redis] = None

_warned_missing_trusted_cidrs = False
_warned_untrusted_peer = False


def _trusted_proxy_networks() -> list:
    raw = str(getattr(settings, "TRUSTED_PROXY_CIDRS", "") or "")
    networks = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            networks.append(ipaddress.ip_network(part, strict=False))
        except ValueError:
            logger.warning("Ignoring malformed TRUSTED_PROXY_CIDRS entry %r", part)
    return networks


def client_address(request: Request) -> str:
    """Client IP for rate-limit keys, resistant to X-Forwarded-For spoofing.

    Deployment contract:
      * TRUSTED_PROXY_HOPS=0 (default): the socket peer is always used; XFF is
        ignored. Correct when the app is reached directly (no reverse proxy).
      * TRUSTED_PROXY_HOPS>0: XFF is honoured only when the request's socket
        peer is inside TRUSTED_PROXY_CIDRS. Take the address ``hops`` from the
        right of XFF so a client cannot forge the hop the proxy appended.
        Deployments MUST set TRUSTED_PROXY_CIDRS; without it every request falls
        back to the socket peer (never a spoofable key) and a warning is logged.

    When trust cannot be established we prefer the un-spoofable socket peer over
    a fabricated XFF value, accepting that such traffic may share one bucket.
    """
    global _warned_missing_trusted_cidrs, _warned_untrusted_peer
    peer = request.client.host if request.client and request.client.host else ""

    hops = int(getattr(settings, "TRUSTED_PROXY_HOPS", 0) or 0)
    if hops <= 0:
        return peer or "unknown"

    networks = _trusted_proxy_networks()
    if not networks:
        if not _warned_missing_trusted_cidrs:
            _warned_missing_trusted_cidrs = True
            logger.warning(
                "TRUSTED_PROXY_HOPS=%s but TRUSTED_PROXY_CIDRS is empty; "
                "ignoring X-Forwarded-For and falling back to the socket peer.",
                hops,
            )
        return peer or "unknown"

    trusted_peer = False
    if peer:
        try:
            peer_ip = ipaddress.ip_address(peer)
            trusted_peer = any(peer_ip in net for net in networks)
        except ValueError:
            trusted_peer = False
    if not trusted_peer:
        if not _warned_untrusted_peer:
            _warned_untrusted_peer = True
            logger.warning(
                "Request from %r is outside TRUSTED_PROXY_CIDRS; ignoring "
                "X-Forwarded-For (possible spoofing attempt).",
                peer or "unknown",
            )
        return peer or "unknown"

    forwarded = request.headers.get("x-forwarded-for", "")
    parts = [part.strip() for part in forwarded.split(",") if part.strip()]
    if len(parts) >= hops:
        return parts[-hops][:128]
    return peer or "unknown"


def _redis() -> aioredis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            max_connections=20,
        )
    return _redis_client


def _prune_local(now: float, window_seconds: int) -> None:
    stale = [
        key
        for key, stamps in _local_rate_limit_cache.items()
        if not stamps or now - stamps[-1] >= window_seconds
    ]
    for key in stale:
        _local_rate_limit_cache.pop(key, None)
    if len(_local_rate_limit_cache) <= _LOCAL_CACHE_MAX_KEYS:
        return
    oldest = sorted(
        _local_rate_limit_cache.items(),
        key=lambda item: item[1][-1] if item[1] else 0.0,
    )
    for key, _stamps in oldest[: len(_local_rate_limit_cache) - _LOCAL_CACHE_MAX_KEYS]:
        _local_rate_limit_cache.pop(key, None)


def _local_check(key: str, limit: int, window_seconds: int, now: float) -> None:
    _prune_local(now, window_seconds)
    timestamps = [stamp for stamp in _local_rate_limit_cache.get(key, []) if now - stamp < window_seconds]
    if len(timestamps) >= limit:
        raise AppException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            code="RATE_LIMITED",
            message="Rate limit exceeded. Please try again later.",
            headers={"Retry-After": str(window_seconds)},
        )
    timestamps.append(now)
    _local_rate_limit_cache[key] = timestamps


async def check_rate_limit(
    key: str,
    limit: int = 10,
    window_seconds: int = 60,
) -> None:
    """Sliding-window limiter. Redis is shared across workers; memory is the fallback."""
    now = time.time()
    try:
        client = _redis()
        redis_key = f"rate_limit:{key}"
        member = f"{now:.6f}:{uuid.uuid4().hex}"
        pipe = client.pipeline()
        pipe.zremrangebyscore(redis_key, 0, now - window_seconds)
        pipe.zadd(redis_key, {member: now})
        pipe.zcard(redis_key)
        pipe.expire(redis_key, window_seconds + 5)
        results = await pipe.execute()
        current_count = int(results[2])
        if current_count > limit:
            raise AppException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                code="RATE_LIMITED",
                message="Rate limit exceeded. Please try again later.",
                headers={"Retry-After": str(window_seconds)},
            )
    except AppException:
        raise
    except Exception:
        _local_check(key, limit, window_seconds, now)


def _local_consume(key: str, limit: int, window_seconds: int, now: float) -> bool:
    _prune_local(now, window_seconds)
    timestamps = [stamp for stamp in _local_rate_limit_cache.get(key, []) if now - stamp < window_seconds]
    if len(timestamps) >= limit:
        _local_rate_limit_cache[key] = timestamps
        return False
    timestamps.append(now)
    _local_rate_limit_cache[key] = timestamps
    return True


async def consume_rate_limit(
    key: str,
    limit: int = 10,
    window_seconds: int = 60,
) -> bool:
    """Sliding-window counter that returns False when ``limit`` is exceeded.

    Unlike :func:`check_rate_limit` this never raises, so a caller can degrade
    gracefully (for example, still register an account but skip the free trial).
    """
    now = time.time()
    try:
        client = _redis()
        redis_key = f"rate_limit:{key}"
        member = f"{now:.6f}:{uuid.uuid4().hex}"
        pipe = client.pipeline()
        pipe.zremrangebyscore(redis_key, 0, now - window_seconds)
        pipe.zadd(redis_key, {member: now})
        pipe.zcard(redis_key)
        pipe.expire(redis_key, window_seconds + 5)
        results = await pipe.execute()
        return int(results[2]) <= limit
    except Exception:
        return _local_consume(key, limit, window_seconds, now)
