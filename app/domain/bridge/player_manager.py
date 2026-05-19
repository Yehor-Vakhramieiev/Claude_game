import random

from pydantic import BaseModel, Field, model_validator

from app.domain.bridge.entities import Player, Card


class PlayerNotFoundError(Exception):
    pass


class RoomIsFullError(Exception):
    pass


class RoomIsEmptyError(Exception):
    pass


class PlayerManager(BaseModel):
    max_players: int
    players: dict[str, Player] = Field(default_factory=dict)
    turn_order: list[str] = Field(default_factory=list)
    skips: dict[str, int] = Field(default_factory=dict)
    current_player_index: int = 0

    @model_validator(mode="after")
    def validate_players_limit(self) -> "PlayerManager":
        if len(self.players) > self.max_players:
            raise ValueError(
                f"{self.__class__.__name__} cannot have more than {self.max_players} players"
            )
        if len(self.turn_order) > self.max_players:
            raise ValueError(
                f"{self.__class__.__name__} cannot have more than {self.max_players} turn order"
            )
        return self

    @property
    def current_player_id(self) -> str:
        if not self.turn_order:
            raise ValueError(f"{self.__class__.__name__} cannot have no turn order")
        return self.turn_order[self.current_player_index]

    def add_player(self, player: Player) -> None:
        if len(self.players) >= self.max_players:
            raise RoomIsFullError("Room is already full")

        if player.id in self.players:
            raise ValueError(f"Player {player.id} is already registered")

        self.players[player.id] = player
        self.turn_order.append(player.id)

        if len(self.players) == self.max_players:
            random.shuffle(self.turn_order)

    def remove_player(self, player: Player) -> None:
        if player.id not in self.players:
            raise PlayerNotFoundError(f"Player {player.id} is not registered")

        delete_player_index = self.turn_order.index(player.id)

        self.players.pop(player.id)
        self.turn_order.remove(player.id)
        self.skips.pop(player.id, None)

        if not self.turn_order:
            self.current_player_index = 0
            raise RoomIsEmptyError("Room is empty")

        if self.current_player_index >= len(self.turn_order):
            self.current_player_index = 0
            return

        self.current_player_index = (
            self.current_player_index
            if self.current_player_index <= delete_player_index
            else self.current_player_index - 1
        )

    def get_player(self, player_id: str) -> Player:
        if player_id not in self.players:
            raise PlayerNotFoundError(f"Player {player_id} is not registered")
        return self.players[player_id]

    def give_cards_to_player(self, player_id: str, data: list[Card] | Card) -> None:
        player = self.get_player(player_id)
        player.add_cards(data)

    def remove_cards_from_player(self, player_id: str, data: list[Card] | Card) -> None:
        player = self.get_player(player_id)
        player.remove_cards(data)

    def advance_move(self):
        if not self.turn_order:
            raise RoomIsEmptyError("Room is empty")

        current_player_index = self.current_player_index

        while True:
            current_player_index = (
                0
                if current_player_index == len(self.turn_order) - 1
                else current_player_index + 1
            )
            player_id = self.turn_order[current_player_index]

            if self.skips.get(player_id, 0) > 0:
                self.skips[player_id] -= 1

                if self.skips[player_id] == 0:
                    del self.skips[player_id]

                continue

            break

        self.current_player_index = current_player_index
        return current_player_index
