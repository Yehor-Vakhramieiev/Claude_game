from pydantic import BaseModel, Field
from .cards import Card


class Player(BaseModel):
    id: str
    name: str
    hand: list[Card] = Field(default_factory=list)
