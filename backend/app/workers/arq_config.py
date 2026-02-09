"""ARQ Worker configuration for Digital Humans."""
from arq import create_pool
from arq.connections import RedisSettings

REDIS_SETTINGS = RedisSettings(
    host='localhost',
    port=6379,
    database=1,  # DB 1 for ARQ (DB 0 for general cache)
)


async def get_redis_pool():
    """Create and return an ARQ Redis connection pool."""
    return await create_pool(REDIS_SETTINGS)
