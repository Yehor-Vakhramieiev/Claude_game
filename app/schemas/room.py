from pydantic import BaseModel, Field


class RoomCreate(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    max_players: int = Field(default=4, ge=2, le=5)


class RoomResponse(BaseModel):
    id: str
    name: str
    host_id: str
    player_ids: list[str]
    max_players: int
    status: str
