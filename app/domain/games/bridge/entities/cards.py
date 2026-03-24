from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from .effects import Effect, DrawEffect, SkipEffect, CoverEffect, ChangeSuitEffect


class CardRank(StrEnum):
    SIX = "6"
    SEVEN = "7"
    EIGHT = "8"
    NINE = "9"
    TEN = "10"
    JACK = "J"
    QUEEN = "Q"
    KING = "K"
    ACE = "A"


class CardSuit(StrEnum):
    HEARTS = "hearts"
    CLUBS = "club"
    DIAMONDS = "diamonds"
    SPADES = "spades"


DEFAULT_VALUES = {
    CardRank.SIX: 0,
    CardRank.SEVEN: 0,
    CardRank.EIGHT: 0,
    CardRank.NINE: 0,
    CardRank.TEN: 10,
    CardRank.JACK: 20,
    CardRank.QUEEN: 10,
    CardRank.KING: 10,
    CardRank.ACE: 15,
}


class Card(BaseModel):
    rank: CardRank
    suit: CardSuit
    value: int = Field(
        frozen=True,
        default_factory=lambda data: DEFAULT_VALUES.get(data["rank"]),
    )

    def apply_effect(self) -> tuple[Effect] | tuple[Effect, Effect] | None:
        return


class SixCard(Card):
    def apply_effect(self) -> tuple[Effect]:
        return (CoverEffect(),)


class SevenCard(Card):
    def apply_effect(self) -> tuple[Effect, Effect]:
        return SkipEffect(), DrawEffect(amount=2)


class EightCard(Card):
    def apply_effect(self):
        return (DrawEffect(amount=1),)


class JackCard(Card):
    def apply_effect(self):
        return (ChangeSuitEffect(),)


class JackSpadesCard(JackCard):
    value: int = 40


class KingHeartsCard(Card):
    value: int = 50

    def apply_effect(self):
        return (DrawEffect(amount=5),)


class AceCard(Card):
    def apply_effect(self):
        return (SkipEffect(),)


CARD_REGISTRY: dict[tuple[CardRank, CardSuit | None], type[Card]] = {
    (CardRank.SIX, None): SixCard,
    (CardRank.SEVEN, None): SevenCard,
    (CardRank.EIGHT, None): EightCard,
    (CardRank.JACK, None): JackCard,
    (CardRank.JACK, CardSuit.SPADES): JackSpadesCard,
    (CardRank.KING, CardSuit.HEARTS): KingHeartsCard,
    (CardRank.ACE, None): AceCard,
}


def restore_from_data(pile_data: Any) -> list[Card]:
    if not pile_data:
        return []

    if isinstance(pile_data[0], Card):
        return pile_data

    restored_cards = []
    for card_dict in pile_data:
        rank = CardRank(card_dict["rank"])
        suit = CardSuit(card_dict["suit"])

        card_class = (
            CARD_REGISTRY.get((rank, suit)) or CARD_REGISTRY.get((rank, None)) or Card
        )

        restored_cards.append(card_class(rank=rank, suit=suit))

    return restored_cards
