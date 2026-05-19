import uuid
from unittest.mock import AsyncMock

import fakeredis
import pytest
from fastapi.testclient import TestClient

from app.api.deps import current_active_user, get_redis, get_ws_user
from app.infrastructure.db.models import User
from main import app


def _make_user(n: int) -> User:
    u = User()
    u.id = uuid.UUID(f"00000000-0000-0000-0000-{n:012d}")
    u.email = f"user{n}@test.com"
    u.is_active = True
    u.is_superuser = False
    u.is_verified = False
    u.hashed_password = "hashed"
    return u


USER1 = _make_user(1)
USER2 = _make_user(2)
USER3 = _make_user(3)
USER4 = _make_user(4)

USER1_ID = str(USER1.id)
USER2_ID = str(USER2.id)
USER3_ID = str(USER3.id)
USER4_ID = str(USER4.id)


@pytest.fixture
def fake_redis():
    return fakeredis.FakeAsyncRedis(decode_responses=True)


@pytest.fixture(autouse=True)
def reset_ws_manager():
    """Clear WebSocketManager state between tests to prevent bleed-over."""
    from app.infrastructure.ws_manager import ws_manager
    ws_manager._connections.clear()
    ws_manager._listeners.clear()
    yield
    ws_manager._connections.clear()
    ws_manager._listeners.clear()


@pytest.fixture
def client(fake_redis, monkeypatch):
    """TestClient authenticated as USER1 with fake Redis and no real DB."""
    # Prevent lifespan from connecting to PostgreSQL
    monkeypatch.setattr("main.create_db_tables", AsyncMock())

    app.dependency_overrides[current_active_user] = lambda: USER1
    app.dependency_overrides[get_ws_user] = lambda: USER1
    app.dependency_overrides[get_redis] = lambda: fake_redis
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def switch_user(user: User) -> None:
    """Change the active user for subsequent requests within the same test."""
    app.dependency_overrides[current_active_user] = lambda u=user: u
    app.dependency_overrides[get_ws_user] = lambda u=user: u
