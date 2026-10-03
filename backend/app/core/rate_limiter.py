import time
from typing import Optional
from fastapi import Request, status
import redis.asyncio as aioredis
from app.core.config import settings
from app.core.exceptions import AppException

# In-memory fallback if Redis is unreachable
_local_rate_limit_cache = {}


async def check_rate_limit(
    key: str,
    limit: int = 10,
    window_seconds: int = 60,
):
    """
    Sliding window rate limiter adhering strictly to API spec section 5:
    429: RATE_LIMITED, with Retry-After header.
    """
    now = time.time()
    try:
        r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        # Using sorted set for sliding window
        redis_key = f"rate_limit:{key}"
        pipe = r.pipeline()
        pipe.zremrangebyscore(redis_key, 0, now - window_seconds)
        pipe.zadd(redis_key, {str(now): now})
        pipe.zcard(redis_key)
        pipe.expire(redis_key, window_seconds + 5)
        results = await pipe.execute()
        await r.aclose()

        current_count = results[2]
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
        # Fallback to local memory limiter
        timestamps = _local_rate_limit_cache.get(key, [])
        valid_timestamps = [t for t in timestamps if now - t < window_seconds]
        if len(valid_timestamps) >= limit:
            raise AppException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                code="RATE_LIMITED",
                message="Rate limit exceeded. Please try again later.",
                headers={"Retry-After": str(window_seconds)},
            )
        valid_timestamps.append(now)
        _local_rate_limit_cache[key] = valid_timestamps
