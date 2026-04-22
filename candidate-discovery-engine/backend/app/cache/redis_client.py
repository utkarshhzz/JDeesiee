# createsa redis connection pool that all sevrics share\
# all servides like embedder , rate limiter etc share this pool

from __future__ import annotations

import redis.asyncio as aioredis
import structlog
from app.config import settings

logger=structlog.get_logger()

_redis_pool: aioredis.Redis | None=None

async def get_redis_pool() -> aioredis.Redis:
    global _redis_pool

    if _redis_pool is not None:
        return _redis_pool

    _redis_pool= aioredis.from_url(
        settings.REDIS_URL,
        decode_responses=True,
        encoding="utf-8",
        max_connections=20,
    )
    try:
        await _redis_pool.ping()
        logger.info("REDIS_connected",url=settings.REDIS_URL)
    except Exception as e:
        logger.error("Redis_connection_failed", error=str(e))
        raise

    return _redis_pool

async def close_redis_pool() -> None:
    global _redis_pool

    if _redis_pool is not None:
        await _redis_pool.close()
        _redis_pool=None
        logger.info("Redis_disconnected")

async def get_redis() -> aioredis.Redis:
    if _redis_pool is None:
        raise RuntimeError("Redis pool not initialied .call get_redis_pool() first")
    return _redis_pool

