from app.domain.bridge.entities import Card, CardRank, CardSuit


def can_play_cards(
    cards: list[Card],
    top_card: Card,
    active_suit: CardSuit | None,
    cover_active: bool,
) -> bool:
    if not cards:
        return False

    if len({c.rank for c in cards}) > 1:
        return False

    first = cards[0]
    effective_suit = active_suit or top_card.suit

    if cover_active:
        return first.rank == CardRank.SIX

    return first.rank == top_card.rank or first.suit == effective_suit


def is_bridge_call(cards: list[Card]) -> bool:
    """Four cards of the same rank played in one turn ends the round immediately."""
    return len(cards) == 4 and len({c.rank for c in cards}) == 1


def score_hand(hand: list[Card]) -> int:
    return sum(card.value for card in hand)
