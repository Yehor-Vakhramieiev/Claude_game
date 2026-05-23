import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.api.deps import get_ws_user
from main import app
from tests.api.conftest import (
    USER1, USER1_ID, USER2, USER2_ID, switch_user,
)
from tests.api.test_rooms import create_room


# ──────────────────────────────── helpers ────────────────────────────────────

def setup_started_game(client: TestClient, fake_redis) -> str:
    """Create a 2-player room and start the game via ready flow. Returns room_id."""
    room = create_room(client, max_players=2)
    room_id = room["id"]

    switch_user(USER2)
    client.post(f"/rooms/{room_id}/join")
    client.post(f"/rooms/{room_id}/ready")

    switch_user(USER1)
    r = client.post(f"/rooms/{room_id}/ready")  # triggers auto-start
    assert r.json()["status"] == "playing"
    return room_id


def get_first_player_id(client: TestClient, room_id: str) -> str:
    """Connect briefly to read who goes first, then disconnect."""
    with client.websocket_connect(f"/ws/rooms/{room_id}") as ws:
        snap = ws.receive_json()
    pm = snap["room"]["game"]["player_manager"]
    return pm["turn_order"][pm["current_player_index"]]


def ws_url(room_id: str) -> str:
    return f"/ws/rooms/{room_id}"


# ──────────────────────────────── auth / room guards ─────────────────────────

def test_unauthenticated_connect_closes_4001(client, fake_redis):
    room = create_room(client)
    app.dependency_overrides[get_ws_user] = lambda: None

    with client.websocket_connect(ws_url(room["id"])) as ws:
        with pytest.raises(WebSocketDisconnect) as exc_info:
            ws.receive_text()
    assert exc_info.value.code == 4001


def test_connect_nonexistent_room_closes_4004(client):
    with client.websocket_connect(ws_url("00000000-0000-0000-0000-000000000000")) as ws:
        with pytest.raises(WebSocketDisconnect) as exc_info:
            ws.receive_text()
    assert exc_info.value.code == 4004


def test_connect_not_member_closes_4003(client, fake_redis):
    room = create_room(client)   # created by USER1
    switch_user(USER2)           # USER2 is not in this room

    with client.websocket_connect(ws_url(room["id"])) as ws:
        with pytest.raises(WebSocketDisconnect) as exc_info:
            ws.receive_text()
    assert exc_info.value.code == 4003


# ──────────────────────────────── connection ─────────────────────────────────

def test_connect_receives_snapshot(client, fake_redis):
    room = create_room(client)
    with client.websocket_connect(ws_url(room["id"])) as ws:
        msg = ws.receive_json()
    assert msg["event"] == "room_snapshot"
    assert msg["room"]["id"] == room["id"]


def test_invalid_message_format_returns_error(client, fake_redis):
    room = create_room(client)
    with client.websocket_connect(ws_url(room["id"])) as ws:
        ws.receive_json()          # snapshot
        ws.send_text("not valid json {{")
        err = ws.receive_json()
    assert err["event"] == "error"
    assert "Invalid message format" in err["detail"]


def test_unknown_action_returns_error(client, fake_redis):
    room = create_room(client)
    with client.websocket_connect(ws_url(room["id"])) as ws:
        ws.receive_json()          # snapshot
        ws.send_json({"action": "fly_to_moon"})
        err = ws.receive_json()
    assert err["event"] == "error"


# ──────────────────────────────── game not started ───────────────────────────

def test_draw_card_game_not_started(client, fake_redis):
    room = create_room(client)
    with client.websocket_connect(ws_url(room["id"])) as ws:
        ws.receive_json()
        ws.send_json({"action": "draw_card"})
        err = ws.receive_json()
    assert err["event"] == "error"


def test_play_cards_game_not_started(client, fake_redis):
    room = create_room(client)
    with client.websocket_connect(ws_url(room["id"])) as ws:
        ws.receive_json()
        ws.send_json({"action": "play_cards", "cards": [{"rank": "6", "suit": "hearts"}]})
        err = ws.receive_json()
    assert err["event"] == "error"


# ──────────────────────────────── game actions ───────────────────────────────

def test_draw_card_not_your_turn(client, fake_redis):
    room_id = setup_started_game(client, fake_redis)

    switch_user(USER1)
    first_id = get_first_player_id(client, room_id)

    # Connect as the NON-first player
    if first_id == USER1_ID:
        switch_user(USER2)
    else:
        switch_user(USER1)

    with client.websocket_connect(ws_url(room_id)) as ws:
        ws.receive_json()
        ws.send_json({"action": "draw_card"})
        err = ws.receive_json()

    assert err["event"] == "error"
    assert "turn" in err["detail"].lower()


def test_draw_card_broadcasts_event(client, fake_redis):
    room_id = setup_started_game(client, fake_redis)

    # Determine first player, then reconnect as them
    switch_user(USER1)
    first_id = get_first_player_id(client, room_id)

    if first_id == USER2_ID:
        switch_user(USER2)
    else:
        switch_user(USER1)

    with client.websocket_connect(ws_url(room_id)) as ws:
        ws.receive_json()          # snapshot
        ws.send_json({"action": "draw_card"})
        event = ws.receive_json()

    assert event["event"] == "player_drew"
    assert event["count"] >= 1
    assert "room" in event


def test_play_card_not_in_hand(client, fake_redis):
    room_id = setup_started_game(client, fake_redis)

    switch_user(USER1)
    first_id = get_first_player_id(client, room_id)

    if first_id == USER2_ID:
        switch_user(USER2)
    else:
        switch_user(USER1)

    with client.websocket_connect(ws_url(room_id)) as ws:
        ws.receive_json()          # snapshot
        # Try to play 4 sixes — almost certainly not all in hand
        ws.send_json({
            "action": "play_cards",
            "cards": [
                {"rank": "6", "suit": "hearts"},
                {"rank": "6", "suit": "spades"},
                {"rank": "6", "suit": "diamonds"},
                {"rank": "6", "suit": "clubs"},
            ],
        })
        err = ws.receive_json()

    assert err["event"] == "error"


def test_play_valid_card_broadcasts_event(client, fake_redis):
    room_id = setup_started_game(client, fake_redis)

    switch_user(USER1)
    first_id = get_first_player_id(client, room_id)

    if first_id == USER2_ID:
        switch_user(USER2)
    else:
        switch_user(USER1)

    with client.websocket_connect(ws_url(room_id)) as ws:
        snapshot = ws.receive_json()
        game = snapshot["room"]["game"]
        pm = game["player_manager"]
        current_id = pm["turn_order"][pm["current_player_index"]]

        hand = game["player_manager"]["players"][current_id]["hand"]
        top_card = game["top_card"]
        cover_active = game.get("cover_active", False)
        active_suit = game.get("active_suit")

        playable = _find_playable(hand, top_card, active_suit, cover_active)

        if playable is None:
            # No playable card found — draw instead
            ws.send_json({"action": "draw_card"})
            event = ws.receive_json()
            assert event["event"] == "player_drew"
        else:
            # For Jack, must declare a suit
            payload: dict = {"action": "play_cards", "cards": [playable]}
            if playable["rank"] == "J":
                payload["declared_suit"] = "hearts"
            ws.send_json(payload)
            event = ws.receive_json()
            assert event["event"] in ("player_played", "round_ended", "game_over")


def _find_playable(hand: list[dict], top_card: dict, active_suit, cover_active: bool) -> dict | None:
    for card in hand:
        if cover_active:
            if card["rank"] == "6":
                return card
        else:
            effective_suit = active_suit or top_card["suit"]
            if card["rank"] == top_card["rank"] or card["suit"] == effective_suit:
                return card
    return None


# ──────────────────────────────── two-player broadcast ───────────────────────

def test_two_player_broadcast(client, fake_redis):
    """Both players connected via WS receive the same draw event."""
    room_id = setup_started_game(client, fake_redis)

    switch_user(USER1)
    first_id = get_first_player_id(client, room_id)

    # Identify which user goes first and which goes second
    if first_id == USER1_ID:
        first_user, second_user = USER1, USER2
    else:
        first_user, second_user = USER2, USER1

    # Connect first player's WS
    switch_user(first_user)
    with client.websocket_connect(ws_url(room_id)) as ws_first:
        ws_first.receive_json()   # snapshot

        # Connect second player's WS
        switch_user(second_user)
        with client.websocket_connect(ws_url(room_id)) as ws_second:
            ws_second.receive_json()   # snapshot

            # First player draws a card
            switch_user(first_user)
            ws_first.send_json({"action": "draw_card"})

            # Both should receive the broadcast
            e_first = ws_first.receive_json()
            e_second = ws_second.receive_json()

    assert e_first["event"] == "player_drew"
    assert e_second["event"] == "player_drew"
    assert e_first["player_id"] == e_second["player_id"] == first_id


# ──────────────────────────────── lobby events ───────────────────────────────

def test_ws_receives_game_started_event(client, fake_redis):
    room = create_room(client, max_players=2)
    room_id = room["id"]

    switch_user(USER2)
    client.post(f"/rooms/{room_id}/join")

    switch_user(USER1)
    with client.websocket_connect(ws_url(room_id)) as ws:
        ws.receive_json()          # snapshot

        # Both players mark ready; USER2 first, then USER1 (triggers auto-start)
        switch_user(USER2)
        client.post(f"/rooms/{room_id}/ready")
        ws.receive_json()          # player_ready USER2

        switch_user(USER1)
        client.post(f"/rooms/{room_id}/ready")
        ws.receive_json()          # player_ready USER1

        event = ws.receive_json()  # game_started

    assert event["event"] == "game_started"
    assert event["room"]["status"] == "playing"


def test_ws_receives_player_joined_event(client, fake_redis):
    room = create_room(client, max_players=3)
    room_id = room["id"]

    switch_user(USER1)
    with client.websocket_connect(ws_url(room_id)) as ws:
        ws.receive_json()          # snapshot

        switch_user(USER2)
        client.post(f"/rooms/{room_id}/join")

        event = ws.receive_json()

    assert event["event"] == "player_joined"
    assert event["player_id"] == USER2_ID
