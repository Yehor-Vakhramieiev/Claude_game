from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import current_active_user, get_room, get_room_repo
from app.domain.bridge.entities import Player
from app.domain.bridge.exceptions import NotEnoughPlayersError
from app.domain.bridge.game import Game
from app.domain.bridge.player_manager import PlayerManager
from app.domain.room.room import Room
from app.infrastructure.db.models import User
from app.infrastructure.repositories.room_repo import RoomRepository
from app.schemas.room import RoomCreate, RoomResponse

router = APIRouter()


def _to_response(room: Room) -> RoomResponse:
    return RoomResponse(
        id=room.id,
        name=room.name,
        host_id=room.host_id,
        player_ids=room.player_ids,
        max_players=room.max_players,
        status=room.status,
    )


@router.post("", response_model=RoomResponse, status_code=status.HTTP_201_CREATED)
async def create_room(
    data: RoomCreate,
    user: User = Depends(current_active_user),
    repo: RoomRepository = Depends(get_room_repo),
) -> RoomResponse:
    user_id = str(user.id)
    room = Room(name=data.name, host_id=user_id, max_players=data.max_players)
    room.player_ids.append(user_id)
    repo.save(room)
    return _to_response(room)


@router.get("", response_model=list[RoomResponse])
async def list_rooms(
    repo: RoomRepository = Depends(get_room_repo),
    _: User = Depends(current_active_user),
) -> list[RoomResponse]:
    return [_to_response(r) for r in repo.all()]


@router.get("/{room_id}", response_model=RoomResponse)
async def get_room_detail(
    room: Room = Depends(get_room),
    _: User = Depends(current_active_user),
) -> RoomResponse:
    return _to_response(room)


@router.post("/{room_id}/join", response_model=RoomResponse)
async def join_room(
    room: Room = Depends(get_room),
    user: User = Depends(current_active_user),
    repo: RoomRepository = Depends(get_room_repo),
) -> RoomResponse:
    user_id = str(user.id)

    if room.status != "waiting":
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Game already started")
    if user_id in room.player_ids:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Already in this room")
    if len(room.player_ids) >= room.max_players:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Room is full")

    room.player_ids.append(user_id)
    repo.save(room)
    return _to_response(room)


@router.post("/{room_id}/leave", response_model=RoomResponse)
async def leave_room(
    room: Room = Depends(get_room),
    user: User = Depends(current_active_user),
    repo: RoomRepository = Depends(get_room_repo),
) -> RoomResponse:
    user_id = str(user.id)

    if user_id not in room.player_ids:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Not in this room")

    room.player_ids.remove(user_id)

    if not room.player_ids:
        repo.delete(room.id)
        return _to_response(room)

    if room.host_id == user_id:
        room.host_id = room.player_ids[0]

    repo.save(room)
    return _to_response(room)


@router.post("/{room_id}/start", response_model=RoomResponse)
async def start_game(
    room: Room = Depends(get_room),
    user: User = Depends(current_active_user),
    repo: RoomRepository = Depends(get_room_repo),
) -> RoomResponse:
    if str(user.id) != room.host_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Only the host can start the game")
    if room.status != "waiting":
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Game already started")

    pm = PlayerManager(max_players=room.max_players)
    game = Game(player_manager=pm)

    for player_id in room.player_ids:
        game.join(Player(id=player_id, name=player_id))

    try:
        game.start()
    except NotEnoughPlayersError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(e))

    room.game = game
    repo.save(room)
    return _to_response(room)


@router.delete("/{room_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_room(
    room: Room = Depends(get_room),
    user: User = Depends(current_active_user),
    repo: RoomRepository = Depends(get_room_repo),
) -> None:
    if str(user.id) != room.host_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Only the host can delete the room")
    repo.delete(room.id)
