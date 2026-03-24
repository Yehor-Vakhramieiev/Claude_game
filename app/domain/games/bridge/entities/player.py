from typing import Any

from pydantic import BaseModel, Field, field_validator
from .cards import Card, restore_from_data


class Player(BaseModel):
    id: str
    name: str
    hand: list[Card] = Field(default_factory=list)

    @field_validator("hand", mode="before")
    @classmethod
    def restore_hand(cls, data: Any) -> list[Card]:
        return restore_from_data(data)
