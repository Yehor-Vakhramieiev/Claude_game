import pytest

from app.domain.bridge.entities import Player, Deck
from app.domain.bridge.exceptions import PlayerNotFoundError, RoomIsFullError, RoomIsEmptyError
from app.domain.bridge.player_manager import PlayerManager


def make_player(player_id: str) -> Player:
    return Player(id=player_id, name=f"Player {player_id}")


def make_manager(max_players: int = 5) -> PlayerManager:
    return PlayerManager(max_players=max_players)


def ordered_manager(*player_ids: str) -> PlayerManager:
    """Create a manager with a deterministic turn order (max_players > count to skip shuffle)."""
    pm = make_manager(max_players=10)
    for pid in player_ids:
        pm.add_player(make_player(pid))
    pm.turn_order = list(player_ids)
    pm.current_player_index = 0
    return pm


# ------------------------------------------------------------------ add_player

def test_add_player():
    pm = make_manager()
    pm.add_player(make_player("1"))
    assert "1" in pm.players
    assert "1" in pm.turn_order


def test_add_player_room_full():
    pm = make_manager(max_players=2)
    pm.add_player(make_player("1"))
    pm.add_player(make_player("2"))
    with pytest.raises(RoomIsFullError):
        pm.add_player(make_player("3"))


def test_add_player_duplicate_raises():
    pm = make_manager()
    pm.add_player(make_player("1"))
    with pytest.raises(ValueError):
        pm.add_player(make_player("1"))


def test_add_player_shuffles_when_full():
    # Just checks that shuffle doesn't break anything; order may or may not change
    pm = make_manager(max_players=2)
    pm.add_player(make_player("1"))
    pm.add_player(make_player("2"))
    assert set(pm.turn_order) == {"1", "2"}


def test_max_players_unchanged_after_remove():
    pm = make_manager(max_players=3)
    p1, p2 = make_player("1"), make_player("2")
    pm.add_player(p1)
    pm.add_player(p2)
    pm.remove_player(p1)
    assert pm.max_players == 3


# --------------------------------------------------------------- remove_player

def test_remove_player():
    pm = ordered_manager("1", "2", "3")
    pm.remove_player(make_player("2"))
    assert "2" not in pm.players
    assert "2" not in pm.turn_order


def test_remove_player_not_found_raises():
    pm = make_manager()
    with pytest.raises(PlayerNotFoundError):
        pm.remove_player(make_player("99"))


def test_remove_last_player_raises():
    pm = make_manager()
    p = make_player("1")
    pm.add_player(p)
    with pytest.raises(RoomIsEmptyError):
        pm.remove_player(p)


def test_remove_player_before_current_adjusts_index():
    pm = ordered_manager("1", "2", "3")
    pm.current_player_index = 2  # current = "3"
    pm.remove_player(make_player("1"))  # removed before current
    assert pm.current_player_index == 1  # shifted left
    assert pm.current_player_id == "3"


def test_remove_player_after_current_keeps_index():
    pm = ordered_manager("1", "2", "3")
    pm.current_player_index = 0  # current = "1"
    pm.remove_player(make_player("3"))  # removed after current
    assert pm.current_player_index == 0
    assert pm.current_player_id == "1"


def test_remove_current_player_wraps_index():
    pm = ordered_manager("1", "2", "3")
    pm.current_player_index = 2  # current = "3" (last)
    pm.remove_player(make_player("3"))
    # index was 2, now len=2, so wraps to 0
    assert pm.current_player_index == 0


# -------------------------------------------------------- current/next player

def test_current_player_id():
    pm = ordered_manager("1", "2", "3")
    assert pm.current_player_id == "1"


def test_next_player_id_normal():
    pm = ordered_manager("1", "2", "3")
    assert pm.next_player_id == "2"


def test_next_player_id_wraps():
    pm = ordered_manager("1", "2", "3")
    pm.current_player_index = 2
    assert pm.next_player_id == "1"


def test_current_player_id_empty_raises():
    pm = make_manager()
    with pytest.raises(RoomIsEmptyError):
        _ = pm.current_player_id


# ------------------------------------------------------------ advance_move

def test_advance_move_cycles():
    pm = ordered_manager("1", "2", "3")
    pm.advance_move()
    assert pm.current_player_id == "2"
    pm.advance_move()
    assert pm.current_player_id == "3"
    pm.advance_move()
    assert pm.current_player_id == "1"


def test_advance_move_skips_one_player():
    pm = ordered_manager("1", "2", "3")
    pm.skips["2"] = 1
    pm.advance_move()
    assert pm.current_player_id == "3"
    assert "2" not in pm.skips


def test_advance_move_skip_count_decremented():
    pm = ordered_manager("1", "2", "3")
    pm.skips["2"] = 2
    pm.advance_move()
    # First advance: skip consumed once → "2" still has 1 skip, land on "3"
    assert pm.current_player_id == "3"
    assert pm.skips.get("2") == 1


def test_advance_move_all_others_skipped_returns_to_current():
    pm = ordered_manager("1", "2", "3")
    pm.skips["2"] = 1
    pm.skips["3"] = 1
    pm.advance_move()
    assert pm.current_player_id == "1"
    assert not pm.skips


def test_advance_move_empty_raises():
    pm = make_manager()
    with pytest.raises(RoomIsEmptyError):
        pm.advance_move()


# -------------------------------------------------------- get / give / remove cards

def test_get_player():
    pm = make_manager()
    p = make_player("1")
    pm.add_player(p)
    assert pm.get_player("1") is p


def test_get_player_not_found_raises():
    pm = make_manager()
    with pytest.raises(PlayerNotFoundError):
        pm.get_player("99")


def test_give_and_remove_cards():
    pm = make_manager()
    pm.add_player(make_player("1"))
    cards = Deck().draw_card(3)
    pm.give_cards_to_player("1", cards)
    assert len(pm.players["1"].hand) == 3
    pm.remove_cards_from_player("1", cards[:2])
    assert len(pm.players["1"].hand) == 1
