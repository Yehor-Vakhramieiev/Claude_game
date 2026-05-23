import pytest

from app.domain.bridge.entities import Card, CardRank, CardSuit, Player
from app.domain.bridge.entities.card import (
    SixCard, SevenCard, EightCard, JackCard, KingHeartsCard, AceCard,
)
from app.domain.bridge.exceptions import (
    GameAlreadyStartedError,
    GameNotStartedError,
    InvalidMoveError,
    NotEnoughPlayersError,
    NotPlayersTurnError,
)
from app.domain.bridge.game import Game, GameStatus


# ------------------------------------------------------------------ helpers

def make_player(player_id: str) -> Player:
    return Player(id=player_id, name=f"Player {player_id}")


def make_game(*player_ids: str) -> Game:
    game = Game()
    for pid in player_ids:
        game.join(make_player(pid))
    return game


def started_game(*player_ids: str) -> Game:
    game = make_game(*player_ids)
    game.start()
    # Fix turn order for deterministic tests
    game.player_manager.turn_order = list(player_ids)
    game.player_manager.current_player_index = 0
    return game


def give_card(game: Game, player_id: str, card: Card) -> None:
    """Directly append a card to a player's hand (bypasses duplicate check)."""
    game.player_manager.players[player_id].hand.append(card)


def set_top(game: Game, card: Card) -> None:
    game.top_card = card
    game.active_suit = None
    game.cover_active = False


# ------------------------------------------------------------ join / start

def test_join_adds_player():
    game = Game()
    game.join(make_player("1"))
    assert "1" in game.player_manager.players


def test_cannot_join_started_game():
    game = started_game("1", "2")
    with pytest.raises(GameAlreadyStartedError):
        game.join(make_player("3"))


def test_start_requires_min_players():
    game = make_game("1")
    with pytest.raises(NotEnoughPlayersError):
        game.start()


def test_start_deals_cards_and_sets_top():
    game = started_game("1", "2")
    assert game.status == GameStatus.PLAYING
    assert game.top_card is not None
    for player in game.player_manager.players.values():
        assert len(player.hand) == 5


def test_cannot_start_twice():
    game = started_game("1", "2")
    with pytest.raises(GameAlreadyStartedError):
        game.start()


def test_play_before_start_raises():
    game = make_game("1", "2")
    with pytest.raises(GameNotStartedError):
        game.play_cards("1", [])


# ------------------------------------------------------------ play_cards

def test_play_matching_suit_advances_turn():
    game = started_game("1", "2")
    set_top(game, Card(rank=CardRank.TEN, suit=CardSuit.HEARTS))

    c = Card(rank=CardRank.NINE, suit=CardSuit.HEARTS)
    give_card(game, "1", c)
    game.play_cards("1", [c])

    assert game.top_card == c
    assert game.player_manager.current_player_id == "2"


def test_play_matching_rank_advances_turn():
    game = started_game("1", "2")
    set_top(game, Card(rank=CardRank.TEN, suit=CardSuit.HEARTS))

    c = Card(rank=CardRank.TEN, suit=CardSuit.SPADES)
    give_card(game, "1", c)
    game.play_cards("1", [c])

    assert game.top_card == c
    assert game.player_manager.current_player_id == "2"


def test_play_multiple_same_rank():
    game = started_game("1", "2")
    set_top(game, Card(rank=CardRank.TEN, suit=CardSuit.HEARTS))

    c1 = Card(rank=CardRank.TEN, suit=CardSuit.SPADES)
    c2 = Card(rank=CardRank.TEN, suit=CardSuit.CLUBS)
    give_card(game, "1", c1)
    give_card(game, "1", c2)

    hand_before = len(game.player_manager.players["1"].hand)
    game.play_cards("1", [c1, c2])
    assert len(game.player_manager.players["1"].hand) == hand_before - 2


def test_play_invalid_card_raises():
    game = started_game("1", "2")
    set_top(game, Card(rank=CardRank.TEN, suit=CardSuit.HEARTS))

    c = Card(rank=CardRank.NINE, suit=CardSuit.SPADES)
    give_card(game, "1", c)

    with pytest.raises(InvalidMoveError):
        game.play_cards("1", [c])


def test_play_wrong_turn_raises():
    game = started_game("1", "2")
    with pytest.raises(NotPlayersTurnError):
        game.play_cards("2", [])


def test_play_card_not_in_hand_raises():
    game = started_game("1", "2")
    set_top(game, Card(rank=CardRank.TEN, suit=CardSuit.HEARTS))
    c = Card(rank=CardRank.TEN, suit=CardSuit.SPADES)
    # Do NOT give it to player
    with pytest.raises(InvalidMoveError):
        game.play_cards("1", [c])


# ------------------------------------------------------------ effects: 7 (draw2 + skip)

def test_seven_draws_two_and_skips_next():
    game = started_game("1", "2", "3")
    set_top(game, Card(rank=CardRank.SEVEN, suit=CardSuit.HEARTS))

    seven = SevenCard(rank=CardRank.SEVEN, suit=CardSuit.HEARTS)
    give_card(game, "1", seven)

    hand_before = len(game.player_manager.players["2"].hand)
    game.play_cards("1", [seven])

    # Player 2 draws 2 immediately
    assert len(game.player_manager.players["2"].hand) == hand_before + 2
    # Player 2 is skipped → player 3 is next
    assert game.player_manager.current_player_id == "3"


def test_two_sevens_stack_effects():
    game = started_game("1", "2", "3")
    set_top(game, Card(rank=CardRank.SEVEN, suit=CardSuit.HEARTS))

    s1 = SevenCard(rank=CardRank.SEVEN, suit=CardSuit.HEARTS)
    s2 = SevenCard(rank=CardRank.SEVEN, suit=CardSuit.CLUBS)
    give_card(game, "1", s1)
    give_card(game, "1", s2)

    hand_before = len(game.player_manager.players["2"].hand)
    game.play_cards("1", [s1, s2])

    assert len(game.player_manager.players["2"].hand) == hand_before + 4
    assert game.player_manager.skips.get("2", 0) == 1  # 1 skip remaining after advance


# ------------------------------------------------------------ effects: 8 (draw1, no skip)

def test_eight_draws_one_no_skip():
    game = started_game("1", "2", "3")
    set_top(game, Card(rank=CardRank.EIGHT, suit=CardSuit.HEARTS))

    eight = EightCard(rank=CardRank.EIGHT, suit=CardSuit.HEARTS)
    give_card(game, "1", eight)

    hand_before = len(game.player_manager.players["2"].hand)
    game.play_cards("1", [eight])

    assert len(game.player_manager.players["2"].hand) == hand_before + 1
    assert game.player_manager.current_player_id == "2"  # not skipped


# ------------------------------------------------------------ effects: Ace (skip)

def test_ace_skips_next_player():
    game = started_game("1", "2", "3")
    set_top(game, Card(rank=CardRank.ACE, suit=CardSuit.HEARTS))

    ace = AceCard(rank=CardRank.ACE, suit=CardSuit.HEARTS)
    give_card(game, "1", ace)
    game.play_cards("1", [ace])

    assert game.player_manager.current_player_id == "3"


# ------------------------------------------------------------ effects: King♥ (draw5)

def test_king_hearts_draws_five():
    game = started_game("1", "2", "3")
    set_top(game, Card(rank=CardRank.KING, suit=CardSuit.HEARTS))

    kh = KingHeartsCard(rank=CardRank.KING, suit=CardSuit.HEARTS)
    give_card(game, "1", kh)

    hand_before = len(game.player_manager.players["2"].hand)
    game.play_cards("1", [kh])

    assert len(game.player_manager.players["2"].hand) == hand_before + 5
    assert game.player_manager.current_player_id == "2"  # not skipped


# ------------------------------------------------------------ effects: Jack (change suit)

def test_jack_changes_suit():
    game = started_game("1", "2")
    set_top(game, Card(rank=CardRank.JACK, suit=CardSuit.HEARTS))

    jack = JackCard(rank=CardRank.JACK, suit=CardSuit.HEARTS)
    give_card(game, "1", jack)
    game.play_cards("1", [jack], declared_suit=CardSuit.SPADES)

    assert game.active_suit == CardSuit.SPADES


def test_jack_without_declared_suit_raises():
    game = started_game("1", "2")
    set_top(game, Card(rank=CardRank.JACK, suit=CardSuit.HEARTS))

    jack = JackCard(rank=CardRank.JACK, suit=CardSuit.HEARTS)
    give_card(game, "1", jack)
    with pytest.raises(InvalidMoveError):
        game.play_cards("1", [jack])  # no declared_suit


def test_active_suit_used_for_next_play():
    game = started_game("1", "2")
    set_top(game, Card(rank=CardRank.JACK, suit=CardSuit.HEARTS))
    game.active_suit = CardSuit.SPADES

    # Player 2 plays 9♠ — matches active suit, not top card suit
    c = Card(rank=CardRank.NINE, suit=CardSuit.SPADES)
    give_card(game, "1", c)  # current is "1"
    game.play_cards("1", [c])
    assert game.active_suit is None  # reset after play


# ------------------------------------------------------------ effects: 6 (cover)

def test_six_sets_cover_active():
    game = started_game("1", "2")
    set_top(game, Card(rank=CardRank.SIX, suit=CardSuit.HEARTS))

    six = SixCard(rank=CardRank.SIX, suit=CardSuit.HEARTS)
    give_card(game, "1", six)
    game.play_cards("1", [six])

    assert game.cover_active is True
    assert game.player_manager.current_player_id == "2"


def test_cover_active_only_six_accepted():
    game = started_game("1", "2")
    set_top(game, Card(rank=CardRank.SIX, suit=CardSuit.HEARTS))
    game.cover_active = True
    game.player_manager.current_player_index = 1  # "2"'s turn

    non_six = Card(rank=CardRank.TEN, suit=CardSuit.HEARTS)
    give_card(game, "2", non_six)
    with pytest.raises(InvalidMoveError):
        game.play_cards("2", [non_six])


def test_draw_card_during_cover_does_not_advance_turn():
    game = started_game("1", "2")
    set_top(game, Card(rank=CardRank.SIX, suit=CardSuit.HEARTS))
    game.cover_active = True
    game.player_manager.current_player_index = 1  # "2"'s turn

    hand_before = len(game.player_manager.players["2"].hand)
    game.draw_card("2")

    assert game.player_manager.current_player_id == "2"  # still "2"
    assert len(game.player_manager.players["2"].hand) == hand_before + 1


# ------------------------------------------------------------ draw_card (normal)

def test_draw_card_advances_turn():
    game = started_game("1", "2")
    game.draw_card("1")
    assert game.player_manager.current_player_id == "2"


def test_draw_wrong_turn_raises():
    game = started_game("1", "2")
    with pytest.raises(NotPlayersTurnError):
        game.draw_card("2")


# ------------------------------------------------------------ bridge call

def test_bridge_call_ends_round():
    game = started_game("1", "2")
    set_top(game, Card(rank=CardRank.TEN, suit=CardSuit.HEARTS))

    cards = [
        Card(rank=CardRank.TEN, suit=CardSuit.HEARTS),
        Card(rank=CardRank.TEN, suit=CardSuit.CLUBS),
        Card(rank=CardRank.TEN, suit=CardSuit.DIAMONDS),
        Card(rank=CardRank.TEN, suit=CardSuit.SPADES),
    ]
    for c in cards:
        give_card(game, "1", c)

    game.play_cards("1", cards)
    # Winner "1" gets 0, "2" gets their hand's worth; new round starts
    assert game.scores.get("1", 0) == 0
    assert "2" in game.scores


# ------------------------------------------------------------ round / game end

def test_empty_hand_ends_round():
    game = started_game("1", "2")
    set_top(game, Card(rank=CardRank.TEN, suit=CardSuit.HEARTS))

    # Clear player 1's hand and give a single playable card
    game.player_manager.players["1"].hand.clear()
    c = Card(rank=CardRank.TEN, suit=CardSuit.SPADES)
    give_card(game, "1", c)

    game.play_cards("1", [c])
    # Round ended: "1" scored 0, "2" scored their hand; new round was started
    assert game.scores.get("1", 0) == 0
    assert "2" in game.scores
    # Hands were re-dealt for next round
    assert len(game.player_manager.players["1"].hand) == 5


def test_game_ends_when_score_reaches_max_points():
    game = started_game("1", "2")
    game.scores["2"] = 140  # "2" is near the limit

    set_top(game, Card(rank=CardRank.TEN, suit=CardSuit.HEARTS))
    game.player_manager.players["1"].hand.clear()
    c = Card(rank=CardRank.TEN, suit=CardSuit.SPADES)
    give_card(game, "1", c)

    # Player 2 still has cards worth >= 10 points — enough to push to 150
    game.player_manager.players["2"].hand = [Card(rank=CardRank.TEN, suit=CardSuit.HEARTS)]
    game.play_cards("1", [c])

    assert game.status == GameStatus.FINISHED


def test_scores_accumulate_across_rounds():
    game = started_game("1", "2")
    # Manually trigger end_round without playing
    game.scores["2"] = 30
    game._end_round(winner_id="1")
    # "2" should get hand value added to existing 30
    assert game.scores["2"] > 30


# ------------------------------------------------------------ burn rule

def test_burn_rule_150_limit_resets_score():
    game = started_game("1", "2")
    game.max_points = 150
    # Give player 2 a score that will hit exactly 145 after adding hand value
    game.player_manager.players["2"].hand = [Card(rank=CardRank.TEN, suit=CardSuit.HEARTS)]  # worth 10
    game.scores["2"] = 135  # 135 + 10 = 145 → burn to 0
    game._end_round(winner_id="1")
    assert game.scores["2"] == 0
    assert game.status != GameStatus.FINISHED


def test_burn_rule_250_limit_resets_score():
    game = started_game("1", "2")
    game.max_points = 250
    game.player_manager.players["2"].hand = [Card(rank=CardRank.TEN, suit=CardSuit.HEARTS)]  # worth 10
    game.scores["2"] = 235  # 235 + 10 = 245 → burn to 0
    game._end_round(winner_id="1")
    assert game.scores["2"] == 0
    assert game.status != GameStatus.FINISHED


def test_burn_rule_does_not_apply_when_score_is_not_threshold():
    game = started_game("1", "2")
    game.max_points = 150
    game.player_manager.players["2"].hand = [Card(rank=CardRank.TEN, suit=CardSuit.HEARTS)]  # worth 10
    game.scores["2"] = 130  # 130 + 10 = 140 → not 145, no burn
    game._end_round(winner_id="1")
    assert game.scores["2"] == 140


def test_game_ends_when_score_reaches_250_limit():
    game = started_game("1", "2")
    game.max_points = 250
    game.scores["2"] = 240  # after adding 10 → 250, game ends

    set_top(game, Card(rank=CardRank.TEN, suit=CardSuit.HEARTS))
    game.player_manager.players["1"].hand.clear()
    c = Card(rank=CardRank.TEN, suit=CardSuit.SPADES)
    give_card(game, "1", c)

    game.player_manager.players["2"].hand = [Card(rank=CardRank.TEN, suit=CardSuit.HEARTS)]
    game.play_cards("1", [c])

    assert game.status == GameStatus.FINISHED
