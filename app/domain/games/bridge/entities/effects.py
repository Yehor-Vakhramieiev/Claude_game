from typing import Literal
from pydantic import BaseModel, Field


class DrawEffect(BaseModel):
    type: Literal["draw"] = "draw"
    amount: int = Field(ge=1, le=5)


class SkipEffect(BaseModel):
    type: Literal["skip"] = "skip"
    amount: int = 1


class ChangeSuitEffect(BaseModel):
    type: Literal["change_suit"] = "change_suit"


class CoverEffect(BaseModel):
    type: Literal["cover"] = "cover"


Effect = DrawEffect | SkipEffect | ChangeSuitEffect | CoverEffect
