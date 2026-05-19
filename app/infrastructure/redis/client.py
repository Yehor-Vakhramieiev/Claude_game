from redis.asyncio import Redis, ConnectionPool

from app.core.config import settings

_pool: ConnectionPool | None = None


def create_pool() -> ConnectionPool:
    global _pool
    _pool = ConnectionPool.from_url(
        settings.redis_url,
        decode_responses=True,
        max_connections=20,
    )
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.aclose()
        _pool = None


def get_redis() -> Redis:
    if _pool is None:
        raise RuntimeError("Redis pool not initialised — call create_pool() first")
    return Redis(connection_pool=_pool)
