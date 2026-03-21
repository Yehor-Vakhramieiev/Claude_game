from pydantic import BaseModel
from enum import StrEnum


class EffectType(StrEnum):
    DRAW = "draw"
    SKIP = "skip"
    CHANGE_SUIT = "change_suit"


class Effect(BaseModel):
    effect_type: EffectType
    amount: int
