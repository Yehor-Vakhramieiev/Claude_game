"""
Unit tests for WebSocketManager.

WebSocket objects are mocked with AsyncMock — no real HTTP connections needed.
Tests use asyncio.run() for simplicity.
"""

import asyncio
import json
from unittest.mock import AsyncMock, patch

import fakeredis
import pytest

from app.infrastructure.ws_manager import WebSocketManager


# ──────────────────────────────── helpers ────────────────────────────────────

def make_ws() -> AsyncMock:
    ws = AsyncMock()
    ws.accept = AsyncMock()
    ws.send_text = AsyncMock()
    ws.close = AsyncMock()
    return ws


def make_manager() -> WebSocketManager:
    return WebSocketManager()


def make_redis():
    return fakeredis.FakeAsyncRedis(decode_responses=True)


# ──────────────────────────────── connect ────────────────────────────────────

def test_connect_calls_ws_accept():
    async def _():
        manager = make_manager()
        ws = make_ws()
        redis = make_redis()
        await manager.connect("r1", ws, redis)
        ws.accept.assert_called_once()
        await manager.disconnect("r1", ws)
    asyncio.run(_())


def test_connect_adds_to_connections():
    async def _():
        manager = make_manager()
        ws = make_ws()
        redis = make_redis()
        await manager.connect("r1", ws, redis)
        assert ws in manager._connections["r1"]
        await manager.disconnect("r1", ws)
    asyncio.run(_())


def test_connect_creates_listener_task():
    async def _():
        manager = make_manager()
        ws = make_ws()
        redis = make_redis()
        await manager.connect("r1", ws, redis)
        assert "r1" in manager._listeners
        assert not manager._listeners["r1"].done()
        await manager.disconnect("r1", ws)
    asyncio.run(_())


def test_second_connect_reuses_listener():
    async def _():
        manager = make_manager()
        ws1, ws2 = make_ws(), make_ws()
        redis = make_redis()
        await manager.connect("r1", ws1, redis)
        first_task = manager._listeners["r1"]
        await manager.connect("r1", ws2, redis)
        assert manager._listeners["r1"] is first_task   # same task
        await manager.disconnect("r1", ws1)
        await manager.disconnect("r1", ws2)
    asyncio.run(_())


# ──────────────────────────────── disconnect ─────────────────────────────────

def test_disconnect_removes_connection():
    async def _():
        manager = make_manager()
        ws = make_ws()
        redis = make_redis()
        await manager.connect("r1", ws, redis)
        await manager.disconnect("r1", ws)
        assert ws not in manager._connections.get("r1", set())
    asyncio.run(_())


def test_disconnect_last_connection_cancels_listener():
    async def _():
        manager = make_manager()
        ws = make_ws()
        redis = make_redis()
        await manager.connect("r1", ws, redis)
        task = manager._listeners["r1"]
        await manager.disconnect("r1", ws)
        assert "r1" not in manager._listeners
        # Give the event loop a tick to actually cancel the task
        await asyncio.sleep(0)
        assert task.cancelled() or task.done()
    asyncio.run(_())


def test_disconnect_non_last_keeps_listener():
    async def _():
        manager = make_manager()
        ws1, ws2 = make_ws(), make_ws()
        redis = make_redis()
        await manager.connect("r1", ws1, redis)
        await manager.connect("r1", ws2, redis)
        task = manager._listeners["r1"]
        await manager.disconnect("r1", ws1)
        assert "r1" in manager._listeners
        assert manager._listeners["r1"] is task   # task still running
        await manager.disconnect("r1", ws2)
    asyncio.run(_())


def test_disconnect_unknown_ws_is_noop():
    async def _():
        manager = make_manager()
        ws = make_ws()
        await manager.disconnect("nonexistent", ws)   # must not raise
    asyncio.run(_())


# ──────────────────────────────── broadcast ──────────────────────────────────

def test_broadcast_publishes_to_redis_channel():
    async def _():
        manager = make_manager()
        redis = make_redis()
        ws = make_ws()
        await manager.connect("r1", ws, redis)
        await asyncio.sleep(0)   # let listener subscribe

        payload = {"event": "test", "data": 42}
        await manager.broadcast("r1", redis, payload)

        # Give the listener a tick to process the message
        await asyncio.sleep(0.05)

        ws.send_text.assert_called_once()
        delivered = json.loads(ws.send_text.call_args[0][0])
        assert delivered == payload
        await manager.disconnect("r1", ws)
    asyncio.run(_())


def test_broadcast_reaches_all_connections_in_room():
    async def _():
        manager = make_manager()
        redis = make_redis()
        ws1, ws2 = make_ws(), make_ws()
        await manager.connect("r1", ws1, redis)
        await manager.connect("r1", ws2, redis)

        await asyncio.sleep(0)   # let listener subscribe

        await manager.broadcast("r1", redis, {"event": "ping"})
        await asyncio.sleep(0.05)

        ws1.send_text.assert_called_once()
        ws2.send_text.assert_called_once()
        await manager.disconnect("r1", ws1)
        await manager.disconnect("r1", ws2)
    asyncio.run(_())


def test_broadcast_does_not_reach_other_room():
    async def _():
        manager = make_manager()
        redis = make_redis()
        ws_r1 = make_ws()
        ws_r2 = make_ws()
        await manager.connect("r1", ws_r1, redis)
        await manager.connect("r2", ws_r2, redis)

        await asyncio.sleep(0)

        await manager.broadcast("r1", redis, {"event": "only-r1"})
        await asyncio.sleep(0.05)

        ws_r1.send_text.assert_called_once()
        ws_r2.send_text.assert_not_called()
        await manager.disconnect("r1", ws_r1)
        await manager.disconnect("r2", ws_r2)
    asyncio.run(_())


# ──────────────────────────────── fan_out ────────────────────────────────────

def test_fan_out_removes_dead_connection():
    """If send_text raises, the dead WS is removed from connections."""
    async def _():
        manager = make_manager()
        redis = make_redis()
        ws_good = make_ws()
        ws_dead = make_ws()
        ws_dead.send_text.side_effect = RuntimeError("connection lost")

        await manager.connect("r1", ws_good, redis)
        await manager.connect("r1", ws_dead, redis)

        await asyncio.sleep(0)

        await manager.broadcast("r1", redis, {"event": "test"})
        await asyncio.sleep(0.05)

        assert ws_dead not in manager._connections.get("r1", set())
        ws_good.send_text.assert_called_once()
        await manager.disconnect("r1", ws_good)
    asyncio.run(_())


# ──────────────────────────────── full pub/sub flow ──────────────────────────

def test_multiple_broadcasts_delivered_in_order():
    async def _():
        manager = make_manager()
        redis = make_redis()
        ws = make_ws()
        await manager.connect("r1", ws, redis)
        await asyncio.sleep(0)

        await manager.broadcast("r1", redis, {"seq": 1})
        await manager.broadcast("r1", redis, {"seq": 2})
        await manager.broadcast("r1", redis, {"seq": 3})
        await asyncio.sleep(0.1)

        assert ws.send_text.call_count == 3
        calls = [json.loads(c[0][0]) for c in ws.send_text.call_args_list]
        assert calls == [{"seq": 1}, {"seq": 2}, {"seq": 3}]
        await manager.disconnect("r1", ws)
    asyncio.run(_())


def test_no_delivery_after_disconnect():
    async def _():
        manager = make_manager()
        redis = make_redis()
        ws = make_ws()
        await manager.connect("r1", ws, redis)
        await asyncio.sleep(0)
        await manager.disconnect("r1", ws)
        await asyncio.sleep(0)

        # Broadcast AFTER disconnect — ws should receive nothing
        await manager.broadcast("r1", redis, {"event": "late"})
        await asyncio.sleep(0.05)

        ws.send_text.assert_not_called()
    asyncio.run(_())
