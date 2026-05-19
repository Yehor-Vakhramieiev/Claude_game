import asyncio
import uuid
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from redis.asyncio import Redis

from app.domain.room.room import Room

_ROOM_KEY = "room:{}"
_ROOMS_SET = "rooms:all"
_LOCK_KEY = "lock:room:{}"
_LOCK_TIMEOUT = 10      # seconds before auto-expire
_LOCK_WAIT = 5.0        # max seconds to wait for the lock
_LOCK_POLL = 0.05       # polling interval


class RoomRepository:
    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    @property
    def redis(self) -> Redis:
        return self._redis

    async def get(self, room_id: str) -> Room | None:
        data = await self._redis.get(_ROOM_KEY.format(room_id))
        if data is None:
            return None
        return Room.model_validate_json(data)

    async def all(self) -> list[Room]:
        room_ids = await self._redis.smembers(_ROOMS_SET)
        if not room_ids:
            return []
        pipe = self._redis.pipeline()
        for room_id in room_ids:
            pipe.get(_ROOM_KEY.format(room_id))
        results = await pipe.execute()
        rooms = []
        for data in results:
            if data is not None:
                rooms.append(Room.model_validate_json(data))
        return rooms

    async def save(self, room: Room) -> Room:
        pipe = self._redis.pipeline()
        pipe.set(_ROOM_KEY.format(room.id), room.model_dump_json())
        pipe.sadd(_ROOMS_SET, room.id)
        await pipe.execute()
        return room

    async def delete(self, room_id: str) -> None:
        pipe = self._redis.pipeline()
        pipe.delete(_ROOM_KEY.format(room_id))
        pipe.srem(_ROOMS_SET, room_id)
        await pipe.execute()

    @asynccontextmanager
    async def lock(self, room_id: str) -> AsyncGenerator[None, None]:
        """
        Distributed lock via SET NX EX — compatible with fakeredis (no Lua/EVALSHA needed).
        Uses a unique token so only the owner can release.
        """
        key = _LOCK_KEY.format(room_id)
        token = str(uuid.uuid4())
        loop = asyncio.get_event_loop()
        deadline = loop.time() + _LOCK_WAIT

        while True:
            acquired = await self._redis.set(key, token, nx=True, ex=_LOCK_TIMEOUT)
            if acquired:
                break
            if loop.time() >= deadline:
                raise TimeoutError(f"Could not acquire lock for room {room_id}")
            await asyncio.sleep(_LOCK_POLL)

        try:
            yield
        finally:
            current = await self._redis.get(key)
            if current == token:
                await self._redis.delete(key)
