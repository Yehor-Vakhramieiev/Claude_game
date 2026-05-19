from typing import Annotated, Literal

from pydantic import BaseModel, Field

from app.domain.bridge.entities import CardRank, CardSuit


class CardData(BaseModel):
    rank: CardRank
    suit: CardSuit


class PlayCardsMessage(BaseModel):
    action: Literal["play_cards"]
    cards: list[CardData] = Field(min_length=1)
    declared_suit: CardSuit | None = None


class DrawCardMessage(BaseModel):
    action: Literal["draw_card"]


IncomingMessage = Annotated[
    PlayCardsMessage | DrawCardMessage,
    Field(discriminator="action"),
]
