from app.domain.bridge.entities import Card, CardRank, CardSuit
from app.domain.bridge.rules import can_play_cards, is_bridge_call, score_hand


def card(rank: CardRank, suit: CardSuit) -> Card:
    return Card(rank=rank, suit=suit)


TOP = card(CardRank.TEN, CardSuit.HEARTS)


# ---------------------------------------------------------- can_play_cards

def test_play_same_suit():
    assert can_play_cards([card(CardRank.NINE, CardSuit.HEARTS)], TOP, None, False)


def test_play_same_rank():
    assert can_play_cards([card(CardRank.TEN, CardSuit.SPADES)], TOP, None, False)


def test_cannot_play_different_suit_and_rank():
    assert not can_play_cards([card(CardRank.NINE, CardSuit.SPADES)], TOP, None, False)


def test_cannot_play_empty_list():
    assert not can_play_cards([], TOP, None, False)


def test_cannot_play_mixed_ranks():
    cards = [card(CardRank.TEN, CardSuit.HEARTS), card(CardRank.NINE, CardSuit.HEARTS)]
    assert not can_play_cards(cards, TOP, None, False)


def test_play_multiple_same_rank():
    cards = [card(CardRank.TEN, CardSuit.SPADES), card(CardRank.TEN, CardSuit.CLUBS)]
    assert can_play_cards(cards, TOP, None, False)


def test_active_suit_overrides_top_card_suit():
    # Top is 10♥, Jack changed suit to ♠, so 9♠ is valid
    assert can_play_cards(
        [card(CardRank.NINE, CardSuit.SPADES)],
        card(CardRank.JACK, CardSuit.HEARTS),
        CardSuit.SPADES,
        False,
    )


def test_active_suit_wrong_suit_rejected():
    assert not can_play_cards(
        [card(CardRank.NINE, CardSuit.CLUBS)],
        card(CardRank.JACK, CardSuit.HEARTS),
        CardSuit.SPADES,
        False,
    )


def test_cover_active_only_six_allowed():
    top_six = card(CardRank.SIX, CardSuit.HEARTS)
    assert can_play_cards([card(CardRank.SIX, CardSuit.CLUBS)], top_six, None, True)
    assert not can_play_cards([card(CardRank.TEN, CardSuit.HEARTS)], top_six, None, True)


def test_cover_active_ignores_active_suit():
    top_six = card(CardRank.SIX, CardSuit.HEARTS)
    # Even if active_suit matches, non-6 is still rejected
    assert not can_play_cards(
        [card(CardRank.NINE, CardSuit.SPADES)], top_six, CardSuit.SPADES, True
    )


# ---------------------------------------------------------- is_bridge_call

def test_bridge_call_four_of_same_rank():
    cards = [
        card(CardRank.TEN, CardSuit.HEARTS),
        card(CardRank.TEN, CardSuit.CLUBS),
        card(CardRank.TEN, CardSuit.DIAMONDS),
        card(CardRank.TEN, CardSuit.SPADES),
    ]
    assert is_bridge_call(cards)


def test_not_bridge_call_three_cards():
    cards = [
        card(CardRank.TEN, CardSuit.HEARTS),
        card(CardRank.TEN, CardSuit.CLUBS),
        card(CardRank.TEN, CardSuit.DIAMONDS),
    ]
    assert not is_bridge_call(cards)


def test_not_bridge_call_mixed_ranks():
    cards = [
        card(CardRank.TEN, CardSuit.HEARTS),
        card(CardRank.TEN, CardSuit.CLUBS),
        card(CardRank.TEN, CardSuit.DIAMONDS),
        card(CardRank.NINE, CardSuit.SPADES),
    ]
    assert not is_bridge_call(cards)


def test_not_bridge_call_single_card():
    assert not is_bridge_call([card(CardRank.TEN, CardSuit.HEARTS)])


# ------------------------------------------------------------ score_hand

def test_score_hand():
    hand = [
        card(CardRank.TEN, CardSuit.HEARTS),    # 10
        card(CardRank.QUEEN, CardSuit.CLUBS),    # 10
        card(CardRank.ACE, CardSuit.DIAMONDS),   # 15
        card(CardRank.SIX, CardSuit.SPADES),     # 0
        card(CardRank.NINE, CardSuit.HEARTS),    # 0
    ]
    assert score_hand(hand) == 35


def test_score_empty_hand():
    assert score_hand([]) == 0


def test_score_all_zero_rank_cards():
    hand = [card(r, CardSuit.HEARTS) for r in (CardRank.SIX, CardRank.SEVEN, CardRank.EIGHT, CardRank.NINE)]
    assert score_hand(hand) == 0
