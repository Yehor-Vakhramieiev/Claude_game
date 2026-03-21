from pydantic import BaseModel, Field


class DrawEffect(BaseModel):
    amount: int = Field(ge=1, le=5)


class SkipEffect(BaseModel):
    amount: int = 1


class ChangeSuitEffect(BaseModel):
    pass


class CoverEffect(BaseModel):
    pass


Effect = DrawEffect | SkipEffect | ChangeSuitEffect | CoverEffect
