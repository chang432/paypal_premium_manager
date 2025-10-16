from typing import Optional
from redis.asyncio import Redis, from_url

from app.core.config import settings


class RedisCache:
    def __init__(self, url: Optional[str] = None, ttl_seconds: Optional[int] = None):
        self.url = url or settings.redis_url
        self.ttl = ttl_seconds or settings.redis_ttl_seconds
        self._client: Optional[Redis] = None

    async def get_client(self) -> Redis:
        if self._client is None:
            self._client = from_url(self.url, decode_responses=True)
        return self._client

    async def get_premium(self, email: str) -> Optional[bool]:
        client = await self.get_client()
        val = await client.get(f"premium:{email.lower()}")
        if val is None:
            return None
        return val == "1"

    async def set_premium(self, email: str, is_premium: bool):
        client = await self.get_client()
        await client.setex(f"premium:{email.lower()}", self.ttl, "1" if is_premium else "0")

    async def close(self):
        if self._client:
            await self._client.close()
            self._client = None
