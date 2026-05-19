class PlayerNotFoundError(Exception):
    pass


class RoomIsFullError(Exception):
    pass


class RoomIsEmptyError(Exception):
    pass


class NotEnoughPlayersError(Exception):
    pass


class GameAlreadyStartedError(Exception):
    pass


class GameNotStartedError(Exception):
    pass


class NotPlayersTurnError(Exception):
    pass


class InvalidMoveError(Exception):
    pass
