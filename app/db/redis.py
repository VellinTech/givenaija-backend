

from typing import Generator
import redis
from app.core.config import settings


redis_pool = redis.ConnectionPool.from_url(
    settings.REDIS_URL,
    decode_responses=True  
)


def get_redis_client() -> Generator[redis.Redis, None, None]:

    client = redis.Redis(connection_pool=redis_pool)
    try:
        yield client
    finally:
        client.close()


def get_redis() -> redis.Redis:
  
    return redis.Redis(connection_pool=redis_pool)