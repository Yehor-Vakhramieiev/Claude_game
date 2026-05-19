from contextlib import asynccontextmanager
from typing import AsyncGenerator

from redis.asyncio import Redis

from app.domain.room.room import Room

_ROOM_KEY = "room:{}"
_ROOMS_SET = "rooms:all"
_LOCK_KEY = "lock:room:{}"
_LOCK_TIMEOUT = 10  # seconds


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
        lock = self._redis.lock(
            _LOCK_KEY.format(room_id),
            timeout=_LOCK_TIMEOUT,
            blocking=True,
            blocking_timeout=5,
        )
        async with lock:
            yield
