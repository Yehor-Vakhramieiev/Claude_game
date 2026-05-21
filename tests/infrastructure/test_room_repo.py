"""
Unit tests for RoomRepository.

All I/O goes through fakeredis — no real Redis required.
Tests use asyncio.run() to keep things simple without pytest-anyio config.
"""

import asyncio

import fakeredis
import pytest

from app.domain.room.room import Room
from app.infrastructure.repositories.room_repo import RoomRepository, _LOCK_KEY


# ──────────────────────────────── fixtures ───────────────────────────────────

def make_redis():
    return fakeredis.FakeAsyncRedis(decode_responses=True)


def make_room(**kwargs) -> Room:
    defaults = {"name": "test", "host_id": "host-1"}
    return Room(**{**defaults, **kwargs})


def make_repo(redis=None) -> RoomRepository:
    return RoomRepository(redis or make_redis())


# ──────────────────────────────── get ────────────────────────────────────────

def test_get_missing_returns_none():
    async def _():
        repo = make_repo()
        assert await repo.get("nonexistent") is None
    asyncio.run(_())


def test_get_returns_saved_room():
    async def _():
        repo = make_repo()
        room = make_room()
        await repo.save(room)
        loaded = await repo.get(room.id)
        assert loaded is not None
        assert loaded.id == room.id
        assert loaded.name == room.name
    asyncio.run(_())


def test_get_deserialises_all_fields():
    async def _():
        repo = make_repo()
        room = make_room(name="Bridge", host_id="u1", max_players=3)
        room.player_ids = ["u1", "u2"]
        await repo.save(room)
        loaded = await repo.get(room.id)
        assert loaded.name == "Bridge"
        assert loaded.host_id == "u1"
        assert loaded.max_players == 3
        assert loaded.player_ids == ["u1", "u2"]
    asyncio.run(_())


# ──────────────────────────────── all ────────────────────────────────────────

def test_all_empty():
    async def _():
        repo = make_repo()
        assert await repo.all() == []
    asyncio.run(_())


def test_all_returns_every_saved_room():
    async def _():
        redis = make_redis()
        repo = make_repo(redis)
        r1 = make_room(name="A")
        r2 = make_room(name="B")
        await repo.save(r1)
        await repo.save(r2)
        rooms = await repo.all()
        assert len(rooms) == 2
        names = {r.name for r in rooms}
        assert names == {"A", "B"}
    asyncio.run(_())


def test_all_skips_key_without_data():
    """Rooms whose JSON key is missing (TTL-expired) should be silently skipped."""
    async def _():
        redis = make_redis()
        repo = make_repo(redis)
        room = make_room()
        await repo.save(room)
        # Manually remove the room key but leave the ID in the set
        await redis.delete(f"room:{room.id}")
        rooms = await repo.all()
        assert rooms == []
    asyncio.run(_())


# ──────────────────────────────── save ───────────────────────────────────────

def test_save_overwrites_existing():
    async def _():
        repo = make_repo()
        room = make_room(name="old")
        await repo.save(room)
        room.name = "new"
        await repo.save(room)
        loaded = await repo.get(room.id)
        assert loaded.name == "new"
    asyncio.run(_())


def test_save_registers_id_in_set():
    async def _():
        redis = make_redis()
        repo = make_repo(redis)
        room = make_room()
        await repo.save(room)
        members = await redis.smembers("rooms:all")
        assert room.id in members
    asyncio.run(_())


# ──────────────────────────────── delete ─────────────────────────────────────

def test_delete_removes_room():
    async def _():
        repo = make_repo()
        room = make_room()
        await repo.save(room)
        await repo.delete(room.id)
        assert await repo.get(room.id) is None
    asyncio.run(_())


def test_delete_removes_id_from_set():
    async def _():
        redis = make_redis()
        repo = make_repo(redis)
        room = make_room()
        await repo.save(room)
        await repo.delete(room.id)
        members = await redis.smembers("rooms:all")
        assert room.id not in members
    asyncio.run(_())


def test_delete_nonexistent_is_noop():
    async def _():
        repo = make_repo()
        await repo.delete("nonexistent")   # must not raise
    asyncio.run(_())


def test_delete_only_removes_target():
    async def _():
        repo = make_repo()
        r1 = make_room(name="A")
        r2 = make_room(name="B")
        await repo.save(r1)
        await repo.save(r2)
        await repo.delete(r1.id)
        assert await repo.get(r2.id) is not None
    asyncio.run(_())


# ──────────────────────────────── lock ───────────────────────────────────────

def test_lock_acquired_and_released():
    async def _():
        redis = make_redis()
        repo = make_repo(redis)
        room = make_room()

        async with repo.lock(room.id):
            key = _LOCK_KEY.format(room.id)
            assert await redis.exists(key)   # key present while held

        assert not await redis.exists(key)  # released after exit
    asyncio.run(_())


def test_lock_released_on_exception():
    async def _():
        redis = make_redis()
        repo = make_repo(redis)
        room = make_room()
        key = _LOCK_KEY.format(room.id)

        with pytest.raises(RuntimeError):
            async with repo.lock(room.id):
                raise RuntimeError("boom")

        assert not await redis.exists(key)
    asyncio.run(_())


def test_lock_not_double_acquired_concurrently():
    """Two coroutines competing for the same lock — only one holds it at a time."""
    async def _():
        import app.infrastructure.repositories.room_repo as m
        redis = make_redis()
        repo = make_repo(redis)
        room = make_room()

        held_simultaneously = False
        inside = [False]

        async def critical_section():
            nonlocal held_simultaneously
            async with repo.lock(room.id):
                if inside[0]:
                    held_simultaneously = True
                inside[0] = True
                await asyncio.sleep(0.05)   # hold for 50 ms
                inside[0] = False

        # Patch wait and poll so the test finishes quickly
        original_wait = m._LOCK_WAIT
        original_poll = m._LOCK_POLL
        m._LOCK_WAIT = 2.0
        m._LOCK_POLL = 0.01
        try:
            await asyncio.gather(critical_section(), critical_section())
        finally:
            m._LOCK_WAIT = original_wait
            m._LOCK_POLL = original_poll

        assert not held_simultaneously
    asyncio.run(_())


def test_lock_timeout_raises():
    async def _():
        import app.infrastructure.repositories.room_repo as m
        redis = make_redis()
        repo = make_repo(redis)
        room = make_room()
        key = _LOCK_KEY.format(room.id)

        # Manually occupy the lock key
        await redis.set(key, "someone-else", ex=30)

        m._LOCK_WAIT = 0.1
        m._LOCK_POLL = 0.02
        try:
            with pytest.raises(TimeoutError):
                async with repo.lock(room.id):
                    pass
        finally:
            m._LOCK_WAIT = 5.0
            m._LOCK_POLL = 0.05
    asyncio.run(_())


def test_lock_does_not_release_foreign_key():
    """If the lock key was overwritten by someone else (TTL race), don't delete it."""
    async def _():
        redis = make_redis()
        repo = make_repo(redis)
        room = make_room()
        key = _LOCK_KEY.format(room.id)

        async with repo.lock(room.id):
            # Simulate another process overwriting our token
            await redis.set(key, "other-token")

        # The key should still be there — we didn't own it at release time
        assert await redis.exists(key)
    asyncio.run(_())


# ──────────────────────────────── redis property ─────────────────────────────

def test_redis_property_returns_same_instance():
    redis = make_redis()
    repo = make_repo(redis)
    assert repo.redis is redis
