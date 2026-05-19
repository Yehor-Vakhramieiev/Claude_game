from fastapi import Depends, HTTPException, Query, status
from fastapi_users.db import SQLAlchemyUserDatabase
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.users import UserManager, current_active_user as _current_active_user  # noqa: F401
from app.api.users import get_jwt_strategy
from app.domain.room.room import Room
from app.infrastructure.db.models import User
from app.infrastructure.db.session import get_async_session
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


async def get_ws_user(
    token: str = Query(...),
    session: AsyncSession = Depends(get_async_session),
) -> User | None:
    """JWT auth for WebSocket endpoints (token passed as query param)."""
    strategy = get_jwt_strategy()
    user_db = SQLAlchemyUserDatabase(session, User)
    user_manager = UserManager(user_db)
    try:
        user = await strategy.read_token(token, user_manager)
    except Exception:
        return None
    if user is None or not user.is_active:
        return None
    return user
