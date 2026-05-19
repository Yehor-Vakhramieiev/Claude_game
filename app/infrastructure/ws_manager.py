import asyncio
import json
import logging
from collections import defaultdict

from fastapi import WebSocket
from redis.asyncio import Redis

logger = logging.getLogger(__name__)

_CHANNEL = "channel:room:{}"


class WebSocketManager:
    """
    Manages WebSocket connections per room and bridges them to Redis Pub/Sub
    so events published by any worker reach every connected client.
    """

    def __init__(self) -> None:
        # room_id → set of local WebSocket connections
        self._connections: dict[str, set[WebSocket]] = defaultdict(set)
        # room_id → background listener task
        self._listeners: dict[str, asyncio.Task] = {}

    async def connect(self, room_id: str, ws: WebSocket, redis: Redis) -> None:
        await ws.accept()
        self._connections[room_id].add(ws)
        if room_id not in self._listeners:
            self._listeners[room_id] = asyncio.create_task(
                self._listen(room_id, redis),
                name=f"pubsub:{room_id}",
            )

    async def disconnect(self, room_id: str, ws: WebSocket) -> None:
        self._connections[room_id].discard(ws)
        if not self._connections[room_id]:
            del self._connections[room_id]
            task = self._listeners.pop(room_id, None)
            if task:
                task.cancel()

    async def broadcast(self, room_id: str, redis: Redis, payload: dict) -> None:
        """Publish an event — every worker's listener will fan it out locally."""
        await redis.publish(_CHANNEL.format(room_id), json.dumps(payload))

    async def _listen(self, room_id: str, redis: Redis) -> None:
        pubsub = redis.pubsub()
        await pubsub.subscribe(_CHANNEL.format(room_id))
        try:
            async for message in pubsub.listen():
                if message["type"] != "message":
                    continue
                await self._fan_out(room_id, message["data"])
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("Pub/Sub listener for room %s crashed", room_id)
        finally:
            await pubsub.unsubscribe(_CHANNEL.format(room_id))
            await pubsub.aclose()

    async def _fan_out(self, room_id: str, data: str) -> None:
        dead: list[WebSocket] = []
        for ws in list(self._connections.get(room_id, [])):
            try:
                await ws.send_text(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            await self.disconnect(room_id, ws)


ws_manager = WebSocketManager()
