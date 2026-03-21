from pydantic import BaseModel, Field

from app.domain.games.bridge.entities.cards import (
    Card,
    CardSuit,
    CardRank,
    CARD_REGISTRY,
)


class Deck(BaseModel):
    draw_pile: list[Card] = Field(default_factory=list)
    discard_pile: list[Card] = Field(default_factory=list)
    flips_count: int = 0

    @classmethod
    def create_standard_36(cls) -> "Deck":
        pile = []

        for suit in CardSuit:
            for rank in CardRank:
                card_class = (
                    CARD_REGISTRY.get((rank, suit))
                    or CARD_REGISTRY.get((rank, None))
                    or Card
                )
                pile.append(card_class(suit=suit, rank=rank))

        deck = cls(draw_pile=pile)
        deck.shuffle()
        return deck

    def shuffle(self): ...
