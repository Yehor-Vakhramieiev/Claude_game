import random

from pydantic import BaseModel, Field

from app.domain.games.bridge.entities.cards import (
    Card,
    CardSuit,
    CardRank,
    CARD_REGISTRY,
)


def create_standard_36() -> list[Card]:
    pile = []

    for suit in CardSuit:
        for rank in CardRank:
            card_class = (
                CARD_REGISTRY.get((rank, suit))
                or CARD_REGISTRY.get((rank, None))
                or Card
            )
            pile.append(card_class(suit=suit, rank=rank))
    return pile


class Deck(BaseModel):
    draw_pile: list[Card] = Field(default_factory=create_standard_36)
    discard_pile: list[Card] = Field(default_factory=list)
    flips_count: int = 0

    def shuffle(self, amount_to_save: int = 1):
        if len(self.discard_pile) <= amount_to_save:
            random.shuffle(self.draw_pile)
            return

        self.draw_pile.extend(self.discard_pile[:-amount_to_save])
        self.discard_pile = self.discard_pile[-amount_to_save:]
        self.flips_count += 1
        self.shuffle(amount_to_save)
