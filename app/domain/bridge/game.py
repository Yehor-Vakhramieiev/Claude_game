from enum import StrEnum
import uuid

from pydantic import BaseModel, Field

from app.domain.bridge.entities import Card, CardSuit, Deck, Player
from app.domain.bridge.entities.effects import DrawEffect, SkipEffect, CoverEffect, ChangeSuitEffect
from app.domain.bridge.exceptions import (
    GameAlreadyStartedError,
    GameNotStartedError,
    InvalidMoveError,
    NotEnoughPlayersError,
    NotPlayersTurnError,
)
from app.domain.bridge.player_manager import PlayerManager
from app.domain.bridge.rules import can_play_cards, is_bridge_call, score_hand


class GameStatus(StrEnum):
    WAITING = "waiting"
    PLAYING = "playing"
    FINISHED = "finished"


_MAX_PLAYERS = 5
_MIN_PLAYERS = 2
_INITIAL_HAND_SIZE = 5


class Game(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    player_manager: PlayerManager = Field(
        default_factory=lambda: PlayerManager(max_players=_MAX_PLAYERS)
    )
    deck: Deck = Field(default_factory=Deck)
    top_card: Card | None = None
    active_suit: CardSuit | None = None
    cover_active: bool = False
    status: GameStatus = GameStatus.WAITING
    scores: dict[str, int] = Field(default_factory=dict)
    max_points: int = 150

    # ------------------------------------------------------------------ public

    def join(self, player: Player) -> None:
        if self.status == GameStatus.PLAYING:
            raise GameAlreadyStartedError("Cannot join a game in progress")
        self.player_manager.add_player(player)

    def leave(self, player: Player) -> None:
        self.player_manager.remove_player(player)

    def start(self) -> None:
        if self.status == GameStatus.PLAYING:
            raise GameAlreadyStartedError("Game already started")
        if len(self.player_manager.players) < _MIN_PLAYERS:
            raise NotEnoughPlayersError(f"Need at least {_MIN_PLAYERS} players to start")
        self.status = GameStatus.PLAYING
        self._start_round()

    def play_cards(
        self,
        player_id: str,
        cards: list[Card],
        declared_suit: CardSuit | None = None,
    ) -> None:
        self._assert_playing()
        self._assert_current_player(player_id)

        if not can_play_cards(cards, self.top_card, self.active_suit, self.cover_active):
            raise InvalidMoveError("Cannot play these cards on the current top card")

        player = self.player_manager.get_player(player_id)
        for card in cards:
            if cards.count(card) > player.hand.count(card):
                raise InvalidMoveError(f"Card {card} is not in the player's hand")

        self.player_manager.remove_cards_from_player(player_id, cards)
        self.deck.discard_card(cards)
        self.top_card = cards[-1]
        self.active_suit = None
        self.cover_active = False

        # Bridge call: four of the same rank ends the round immediately
        if is_bridge_call(cards):
            self._end_round(winner_id=player_id)
            return

        # Empty hand ends the round
        if not player.hand:
            self._end_round(winner_id=player_id)
            return

        # Apply all effects immediately to the next player before advancing
        next_player_id = self.player_manager.next_player_id
        self._apply_effects(cards, next_player_id, declared_suit)

        self.player_manager.advance_move()

    def draw_card(self, player_id: str) -> list[Card]:
        """
        Draw one card from the deck.

        When cover is active (6 was played), drawing does not advance the turn —
        the player must keep drawing until they can cover with a 6.
        """
        self._assert_playing()
        self._assert_current_player(player_id)

        if not self.deck.draw_pile:
            self.deck.shuffle()

        cards = self.deck.draw_card(1)
        if cards:
            self.player_manager.give_cards_to_player(player_id, cards)

        # When covering a 6, the turn stays with the current player until they cover
        if not self.cover_active:
            self.player_manager.advance_move()

        return cards

    # ----------------------------------------------------------------- private

    def _start_round(self) -> None:
        self.deck = Deck()
        self.deck.shuffle()
        self.active_suit = None
        self.cover_active = False

        for player in self.player_manager.players.values():
            player.hand.clear()

        for player_id in self.player_manager.players:
            dealt = self.deck.draw_card(_INITIAL_HAND_SIZE)
            self.player_manager.give_cards_to_player(player_id, dealt)

        first_card = self.deck.draw_card(1)[0]
        self.deck.discard_card([first_card])
        self.top_card = first_card

    def _apply_effects(
        self,
        cards: list[Card],
        target_player_id: str,
        declared_suit: CardSuit | None,
    ) -> None:
        """Apply all effects from the played cards immediately to target_player_id."""
        for card in cards:
            effects = card.apply_effect()
            if not effects:
                continue
            for effect in effects:
                if isinstance(effect, DrawEffect):
                    if not self.deck.draw_pile:
                        self.deck.shuffle()
                    drawn = self.deck.draw_card(effect.amount)
                    if drawn:
                        self.player_manager.give_cards_to_player(target_player_id, drawn)

                elif isinstance(effect, SkipEffect):
                    self.player_manager.skips[target_player_id] = (
                        self.player_manager.skips.get(target_player_id, 0) + effect.amount
                    )

                elif isinstance(effect, CoverEffect):
                    self.cover_active = True

                elif isinstance(effect, ChangeSuitEffect):
                    if declared_suit is None:
                        raise InvalidMoveError("Must declare a suit when playing a Jack")
                    self.active_suit = declared_suit

    def _end_round(self, winner_id: str) -> None:
        self.scores.setdefault(winner_id, 0)
        burn_threshold = self.max_points - 5  # 145 for 150-limit, 245 for 250-limit
        for player_id, player in self.player_manager.players.items():
            if player_id != winner_id:
                new_score = self.scores.get(player_id, 0) + score_hand(player.hand)
                if new_score == burn_threshold:
                    new_score = 0
                self.scores[player_id] = new_score

        if any(s >= self.max_points for s in self.scores.values()):
            self.status = GameStatus.FINISHED
            return

        self._start_round()

    def _assert_playing(self) -> None:
        if self.status != GameStatus.PLAYING:
            raise GameNotStartedError("Game is not in progress")

    def _assert_current_player(self, player_id: str) -> None:
        if self.player_manager.current_player_id != player_id:
            raise NotPlayersTurnError(f"It is not player {player_id}'s turn")
