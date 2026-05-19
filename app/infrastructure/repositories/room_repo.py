from app.domain.room.room import Room


class RoomRepository:
    def __init__(self) -> None:
        self._rooms: dict[str, Room] = {}

    def get(self, room_id: str) -> Room | None:
        return self._rooms.get(room_id)

    def all(self) -> list[Room]:
        return list(self._rooms.values())

    def save(self, room: Room) -> Room:
        self._rooms[room.id] = room
        return room

    def delete(self, room_id: str) -> None:
        self._rooms.pop(room_id, None)


room_repo = RoomRepository()
