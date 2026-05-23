import pytest
from fastapi.testclient import TestClient

from tests.api.conftest import USER1, USER1_ID, USER2, USER2_ID, USER3, USER3_ID, switch_user


# ──────────────────────────────── helpers ────────────────────────────────────

def create_room(client: TestClient, name: str = "test", max_players: int = 2) -> dict:
    r = client.post("/rooms", json={"name": name, "max_players": max_players})
    assert r.status_code == 201
    return r.json()


# ──────────────────────────────── create ─────────────────────────────────────

def test_create_room(client):
    data = create_room(client)
    assert data["name"] == "test"
    assert data["host_id"] == USER1_ID
    assert USER1_ID in data["player_ids"]
    assert data["max_players"] == 2
    assert data["ready_player_ids"] == []
    assert data["status"] == "waiting"


def test_create_room_validates_max_players(client):
    r = client.post("/rooms", json={"name": "x", "max_players": 1})
    assert r.status_code == 422

    r = client.post("/rooms", json={"name": "x", "max_players": 6})
    assert r.status_code == 422


# ──────────────────────────────── list / get ─────────────────────────────────

def test_list_rooms_empty(client):
    r = client.get("/rooms")
    assert r.status_code == 200
    assert r.json() == []


def test_list_rooms(client):
    create_room(client, "A")
    create_room(client, "B")
    rooms = client.get("/rooms").json()
    assert len(rooms) == 2
    names = {r["name"] for r in rooms}
    assert names == {"A", "B"}


def test_get_room(client):
    room = create_room(client)
    r = client.get(f"/rooms/{room['id']}")
    assert r.status_code == 200
    assert r.json()["id"] == room["id"]


def test_get_nonexistent_room(client):
    r = client.get("/rooms/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404


# ──────────────────────────────── join ───────────────────────────────────────

def test_join_room(client, fake_redis):
    room = create_room(client, max_players=3)
    room_id = room["id"]

    switch_user(USER2)
    r = client.post(f"/rooms/{room_id}/join")
    assert r.status_code == 200
    assert USER2_ID in r.json()["player_ids"]


def test_join_room_already_in(client):
    room = create_room(client)
    r = client.post(f"/rooms/{room['id']}/join")
    assert r.status_code == 409
    assert "Already in" in r.json()["detail"]


def test_join_room_full(client, fake_redis):
    room = create_room(client, max_players=2)
    room_id = room["id"]

    switch_user(USER2)
    client.post(f"/rooms/{room_id}/join")

    switch_user(USER3)
    r = client.post(f"/rooms/{room_id}/join")
    assert r.status_code == 409
    assert "full" in r.json()["detail"]


def test_join_started_game(client, fake_redis):
    room = create_room(client, max_players=3)
    room_id = room["id"]

    switch_user(USER2)
    client.post(f"/rooms/{room_id}/join")
    client.post(f"/rooms/{room_id}/ready")

    switch_user(USER1)
    client.post(f"/rooms/{room_id}/ready")  # triggers auto-start

    switch_user(USER3)
    r = client.post(f"/rooms/{room_id}/join")
    assert r.status_code == 409
    assert "started" in r.json()["detail"]


# ──────────────────────────────── leave ──────────────────────────────────────

def test_leave_room(client, fake_redis):
    room = create_room(client, max_players=3)
    room_id = room["id"]

    switch_user(USER2)
    client.post(f"/rooms/{room_id}/join")
    r = client.post(f"/rooms/{room_id}/leave")
    assert r.status_code == 200
    assert USER2_ID not in r.json()["player_ids"]


def test_leave_room_not_member(client, fake_redis):
    room = create_room(client)
    switch_user(USER2)
    r = client.post(f"/rooms/{room['id']}/leave")
    assert r.status_code == 409
    assert "Not in" in r.json()["detail"]


def test_leave_last_player_deletes_room(client):
    room = create_room(client)
    room_id = room["id"]

    client.post(f"/rooms/{room_id}/leave")

    r = client.get(f"/rooms/{room_id}")
    assert r.status_code == 404


def test_leave_transfers_host(client, fake_redis):
    room = create_room(client, max_players=3)
    room_id = room["id"]

    switch_user(USER2)
    client.post(f"/rooms/{room_id}/join")

    switch_user(USER1)
    r = client.post(f"/rooms/{room_id}/leave")
    assert r.status_code == 200
    assert r.json()["host_id"] == USER2_ID


# ──────────────────────────────── ready ──────────────────────────────────────

def test_ready_not_member(client, fake_redis):
    room = create_room(client)
    switch_user(USER2)
    r = client.post(f"/rooms/{room['id']}/ready")
    assert r.status_code == 403


def test_ready_game_already_started(client, fake_redis):
    room = create_room(client, max_players=2)
    room_id = room["id"]

    switch_user(USER2)
    client.post(f"/rooms/{room_id}/join")
    client.post(f"/rooms/{room_id}/ready")

    switch_user(USER1)
    client.post(f"/rooms/{room_id}/ready")  # triggers auto-start

    # Game started — ready again should fail
    r = client.post(f"/rooms/{room_id}/ready")
    assert r.status_code == 409
    assert "started" in r.json()["detail"]


def test_ready_already_ready(client):
    room = create_room(client)
    client.post(f"/rooms/{room['id']}/ready")
    r = client.post(f"/rooms/{room['id']}/ready")
    assert r.status_code == 409
    assert "ready" in r.json()["detail"].lower()


def test_ready_single_player_does_not_start(client):
    room = create_room(client)
    r = client.post(f"/rooms/{room['id']}/ready")
    assert r.status_code == 200
    assert r.json()["status"] == "waiting"
    assert USER1_ID in r.json()["ready_player_ids"]


def test_ready_auto_starts_when_all_ready(client, fake_redis):
    room = create_room(client, max_players=2)
    room_id = room["id"]

    switch_user(USER2)
    client.post(f"/rooms/{room_id}/join")
    r = client.post(f"/rooms/{room_id}/ready")
    assert r.json()["status"] == "waiting"

    switch_user(USER1)
    r = client.post(f"/rooms/{room_id}/ready")
    assert r.status_code == 200
    assert r.json()["status"] == "playing"
    assert r.json()["ready_player_ids"] == []  # cleared on start


def test_leave_clears_ready_status(client, fake_redis):
    room = create_room(client, max_players=3)
    room_id = room["id"]

    switch_user(USER2)
    client.post(f"/rooms/{room_id}/join")
    client.post(f"/rooms/{room_id}/ready")

    switch_user(USER3)
    client.post(f"/rooms/{room_id}/join")

    # USER2 leaves — should be removed from ready_player_ids
    switch_user(USER2)
    r = client.post(f"/rooms/{room_id}/leave")
    assert USER2_ID not in r.json()["ready_player_ids"]


def test_leave_triggers_auto_start_if_remaining_all_ready(client, fake_redis):
    room = create_room(client, max_players=3)
    room_id = room["id"]

    switch_user(USER2)
    client.post(f"/rooms/{room_id}/join")

    switch_user(USER3)
    client.post(f"/rooms/{room_id}/join")

    # USER1 and USER2 mark ready; USER3 does not
    switch_user(USER1)
    client.post(f"/rooms/{room_id}/ready")
    switch_user(USER2)
    client.post(f"/rooms/{room_id}/ready")

    # USER3 leaves → remaining (USER1, USER2) are all ready → auto-start
    switch_user(USER3)
    r = client.post(f"/rooms/{room_id}/leave")
    assert r.status_code == 200
    assert r.json()["status"] == "playing"


# ──────────────────────────────── delete ─────────────────────────────────────

def test_delete_room_not_host(client, fake_redis):
    room = create_room(client, max_players=3)
    room_id = room["id"]

    switch_user(USER2)
    client.post(f"/rooms/{room_id}/join")
    r = client.delete(f"/rooms/{room_id}")
    assert r.status_code == 403


def test_delete_room(client):
    room = create_room(client)
    r = client.delete(f"/rooms/{room['id']}")
    assert r.status_code == 204

    r = client.get(f"/rooms/{room['id']}")
    assert r.status_code == 404


# ──────────────────────────────── score_limit ────────────────────────────────

def test_create_room_default_score_limit(client):
    data = create_room(client)
    assert data["score_limit"] == 150


def test_create_room_with_score_limit_250(client):
    r = client.post("/rooms", json={"name": "bigroom", "score_limit": 250})
    assert r.status_code == 201
    assert r.json()["score_limit"] == 250


def test_create_room_invalid_score_limit(client):
    r = client.post("/rooms", json={"name": "x", "score_limit": 100})
    assert r.status_code == 422


def test_start_game_uses_score_limit(client, fake_redis):
    r = client.post("/rooms", json={"name": "bigroom", "max_players": 2, "score_limit": 250})
    room_id = r.json()["id"]

    switch_user(USER2)
    client.post(f"/rooms/{room_id}/join")

    switch_user(USER1)
    client.post(f"/rooms/{room_id}/start")

    r = client.get(f"/rooms/{room_id}")
    assert r.json()["score_limit"] == 250
