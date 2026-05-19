import random
from typing import Any

from pydantic import BaseModel, Field, field_validator

from .card import Card, CardSuit, CardRank, CARD_REGISTRY, restore_from_data


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

    @field_validator("draw_pile", "discard_pile", mode="before")
    @classmethod
    def restore_specific_fields(cls, pile_data: Any) -> list[Card]:
        return restore_from_data(pile_data)

    def shuffle(self, amount_to_save: int = 1) -> None:
        if len(self.discard_pile) <= amount_to_save:
            random.shuffle(self.draw_pile)
            return

        self.draw_pile.extend(self.discard_pile[:-amount_to_save])
        self.discard_pile = self.discard_pile[-amount_to_save:]
        self.flips_count += 1
        self.shuffle(amount_to_save)

    def draw_card(self, amount: int) -> list[Card]:
        amount_to_draw = len(self.draw_pile) if amount > len(self.draw_pile) else amount
        return [self.draw_pile.pop() for _ in range(amount_to_draw)]

    def discard_card(self, cards: list[Card]) -> None:
        self.discard_pile.extend(cards)
