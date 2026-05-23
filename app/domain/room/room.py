import uuid

from pydantic import BaseModel, Field, computed_field

from app.domain.bridge.game import Game


class Room(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    host_id: str
    max_players: int = Field(default=4, ge=2, le=5)
    score_limit: int = Field(default=150)
    player_ids: list[str] = Field(default_factory=list)
    ready_player_ids: list[str] = Field(default_factory=list)
    game: Game | None = None

    @computed_field
    @property
    def status(self) -> str:
        return str(self.game.status) if self.game else "waiting"
