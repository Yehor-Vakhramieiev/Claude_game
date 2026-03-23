from enum import StrEnum

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


CARD_REGISTRY = {
    (CardRank.SIX, None): SixCard,
    (CardRank.SEVEN, None): SevenCard,
    (CardRank.EIGHT, None): EightCard,
    (CardRank.JACK, None): JackCard,
    (CardRank.JACK, CardSuit.SPADES): JackSpadesCard,
    (CardRank.KING, CardSuit.HEARTS): KingHeartsCard,
    (CardRank.ACE, None): AceCard,
}
