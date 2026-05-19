from typing import Any

from pydantic import BaseModel, Field, field_validator
from .card import Card, restore_from_data


class CardNotRemovedError(Exception):
    pass


class CardAlreadyInHandError(Exception):
    pass


class Player(BaseModel):
    id: str
    name: str
    hand: list[Card] = Field(default_factory=list)

    @field_validator("hand", mode="before")
    @classmethod
    def restore_hand(cls, data: Any) -> list[Card]:
        return restore_from_data(data)

    def add_cards(self, data: list[Card] | Card) -> None:
        cards = [data] if isinstance(data, Card) else data
        for card in cards:
            if card in self.hand:
                raise CardAlreadyInHandError(f"Card {card} is already in the hand")

        self.hand.extend(cards)

    def remove_cards(self, data: list[Card] | Card) -> None:
        cards = [data] if isinstance(data, Card) else data

        for card in cards:
            if cards.count(card) > self.hand.count(card):
                raise CardNotRemovedError(f"Card {card} not removed")

        for card in cards:
            self.hand.remove(card)
