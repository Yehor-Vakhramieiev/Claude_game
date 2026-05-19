from fastapi import Depends, HTTPException, status
from redis.asyncio import Redis

from app.api.users import current_active_user as _current_active_user  # noqa: F401 — re-exported
from app.domain.room.room import Room
from app.infrastructure.redis.client import get_redis as _get_redis
from app.infrastructure.repositories.room_repo import RoomRepository

current_active_user = _current_active_user


def get_redis() -> Redis:
    return _get_redis()


def get_room_repo(redis: Redis = Depends(get_redis)) -> RoomRepository:
    return RoomRepository(redis)


async def get_room(
    room_id: str,
    repo: RoomRepository = Depends(get_room_repo),
) -> Room:
    room = await repo.get(room_id)
    if room is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Room not found")
    return room
