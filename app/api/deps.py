from fastapi import Depends, HTTPException, status

from app.api.users import current_active_user as _current_active_user  # noqa: F401 — re-exported
from app.domain.room.room import Room
from app.infrastructure.repositories.room_repo import RoomRepository, room_repo

current_active_user = _current_active_user


def get_room_repo() -> RoomRepository:
    return room_repo


def get_room(
    room_id: str,
    repo: RoomRepository = Depends(get_room_repo),
) -> Room:
    room = repo.get(room_id)
    if room is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Room not found")
    return room
