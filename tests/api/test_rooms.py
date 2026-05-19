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
    room = create_room(client, max_players=2)
    room_id = room["id"]

    switch_user(USER2)
    client.post(f"/rooms/{room_id}/join")

    switch_user(USER1)
    client.post(f"/rooms/{room_id}/start")

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


# ──────────────────────────────── start ──────────────────────────────────────

def test_start_game_not_host(client, fake_redis):
    room = create_room(client, max_players=2)
    room_id = room["id"]

    switch_user(USER2)
    client.post(f"/rooms/{room_id}/join")
    r = client.post(f"/rooms/{room_id}/start")
    assert r.status_code == 403


def test_start_game_not_enough_players(client):
    room = create_room(client, max_players=2)
    r = client.post(f"/rooms/{room['id']}/start")
    assert r.status_code == 409
    assert "players" in r.json()["detail"].lower()


def test_start_game_success(client, fake_redis):
    room = create_room(client, max_players=2)
    room_id = room["id"]

    switch_user(USER2)
    client.post(f"/rooms/{room_id}/join")

    switch_user(USER1)
    r = client.post(f"/rooms/{room_id}/start")
    assert r.status_code == 200
    assert r.json()["status"] == "playing"


def test_start_game_already_started(client, fake_redis):
    room = create_room(client, max_players=2)
    room_id = room["id"]

    switch_user(USER2)
    client.post(f"/rooms/{room_id}/join")

    switch_user(USER1)
    client.post(f"/rooms/{room_id}/start")
    r = client.post(f"/rooms/{room_id}/start")
    assert r.status_code == 409


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
