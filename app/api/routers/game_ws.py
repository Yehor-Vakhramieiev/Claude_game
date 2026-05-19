import json

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from fastapi_users.db import SQLAlchemyUserDatabase
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_redis
from app.api.users import UserManager, get_jwt_strategy
from app.domain.bridge.entities import Card, CardSuit
from app.domain.bridge.exceptions import (
    GameNotStartedError,
    InvalidMoveError,
    NotPlayersTurnError,
)
from app.domain.bridge.game import GameStatus
from app.infrastructure.db.models import User
from app.infrastructure.db.session import get_async_session
from app.infrastructure.repositories.room_repo import RoomRepository
from app.infrastructure.ws_manager import ws_manager
from app.schemas.ws import DrawCardMessage, IncomingMessage, PlayCardsMessage

router = APIRouter()


async def _authenticate(token: str, session: AsyncSession) -> User | None:
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


def _find_cards(hand: list[Card], requests: list) -> list[Card] | None:
    """Find Card objects in the player's hand matching the requested rank+suit pairs."""
    remaining = list(hand)
    result = []
    for req in requests:
        for i, card in enumerate(remaining):
            if card.rank == req.rank and card.suit == req.suit:
                result.append(remaining.pop(i))
                break
        else:
            return None
    return result


def _room_json(room) -> dict:
    return json.loads(room.model_dump_json())


async def _send_error(ws: WebSocket, detail: str) -> None:
    await ws.send_text(json.dumps({"event": "error", "detail": detail}))


@router.websocket("/{room_id}")
async def ws_game(
    room_id: str,
    ws: WebSocket,
    token: str = Query(...),
    session: AsyncSession = Depends(get_async_session),
    redis: Redis = Depends(get_redis),
) -> None:
    user = await _authenticate(token, session)
    if user is None:
        await ws.close(code=4001)
        return

    user_id = str(user.id)
    repo = RoomRepository(redis)

    room = await repo.get(room_id)
    if room is None:
        await ws.close(code=4004)
        return
    if user_id not in room.player_ids:
        await ws.close(code=4003)
        return

    await ws_manager.connect(room_id, ws, redis)
    await ws.send_text(json.dumps({"event": "room_snapshot", "room": _room_json(room)}))

    try:
        while True:
            raw = await ws.receive_text()
            try:
                msg = IncomingMessage.model_validate_json(raw)
            except Exception:
                await _send_error(ws, "Invalid message format")
                continue

            if isinstance(msg, PlayCardsMessage):
                await _handle_play(ws, repo, room_id, user_id, msg)
            elif isinstance(msg, DrawCardMessage):
                await _handle_draw(ws, repo, room_id, user_id)

    except WebSocketDisconnect:
        pass
    finally:
        await ws_manager.disconnect(room_id, ws)


async def _handle_play(
    ws: WebSocket,
    repo: RoomRepository,
    room_id: str,
    user_id: str,
    msg: PlayCardsMessage,
) -> None:
    async with repo.lock(room_id):
        room = await repo.get(room_id)
        if room is None or room.game is None:
            await _send_error(ws, "Room or game not found")
            return

        player = room.game.player_manager.players.get(user_id)
        if player is None:
            await _send_error(ws, "You are not in this game")
            return

        cards = _find_cards(player.hand, msg.cards)
        if cards is None:
            await _send_error(ws, "One or more cards not in your hand")
            return

        scores_before = dict(room.game.scores)
        try:
            room.game.play_cards(user_id, cards, msg.declared_suit)
        except (InvalidMoveError, NotPlayersTurnError, GameNotStartedError) as exc:
            await _send_error(ws, str(exc))
            return

        await repo.save(room)

    room_data = _room_json(room)

    if room.game.status == GameStatus.FINISHED:
        await ws_manager.broadcast(room_id, repo.redis, {
            "event": "game_over",
            "scores": room.game.scores,
            "room": room_data,
        })
    elif room.game.scores != scores_before:
        await ws_manager.broadcast(room_id, repo.redis, {
            "event": "round_ended",
            "winner_id": user_id,
            "scores": room.game.scores,
            "room": room_data,
        })
    else:
        await ws_manager.broadcast(room_id, repo.redis, {
            "event": "player_played",
            "player_id": user_id,
            "cards": [c.model_dump() for c in cards],
            "declared_suit": msg.declared_suit,
            "room": room_data,
        })


async def _handle_draw(
    ws: WebSocket,
    repo: RoomRepository,
    room_id: str,
    user_id: str,
) -> None:
    async with repo.lock(room_id):
        room = await repo.get(room_id)
        if room is None or room.game is None:
            await _send_error(ws, "Room or game not found")
            return

        try:
            drawn = room.game.draw_card(user_id)
        except (NotPlayersTurnError, GameNotStartedError) as exc:
            await _send_error(ws, str(exc))
            return

        await repo.save(room)

    await ws_manager.broadcast(room_id, repo.redis, {
        "event": "player_drew",
        "player_id": user_id,
        "count": len(drawn),
        "room": _room_json(room),
    })
