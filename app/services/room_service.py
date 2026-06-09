from sqlalchemy.orm import Session

from app.events.publisher import publish_room_activated, publish_room_created
from app.models import Room
from app.repositories.room_repo import (
    create_room,
    delete_room,
    find_available_waiting_room,
    find_user_waiting_room,
    get_all_rooms,
    get_room_by_id,
    get_room_by_id_for_update,
)


def get_rooms(db: Session) -> list[Room]:
    return get_all_rooms(db)


def create_new_room(db: Session, user_id: int) -> tuple[Room, bool]:
    existing_waiting_room = find_user_waiting_room(db, user_id)

    if existing_waiting_room is not None:
        return existing_waiting_room, False

    room = create_room(db, user_id)
    assert room.white_player_id is not None
    publish_room_created(room.id, room.white_player_id)
    return room, True


def quick_join_or_create_room(db: Session, user_id: int) -> Room:
    user_waiting_room = find_user_waiting_room(db, user_id)

    if user_waiting_room is not None:
        return user_waiting_room

    available_room = find_available_waiting_room(db, user_id)

    if available_room is None:
        room = create_room(db, user_id)
        assert room.white_player_id is not None
        publish_room_created(room.id, room.white_player_id)
        return room

    available_room.black_player_id = user_id
    available_room.status = "active"

    db.commit()
    db.refresh(available_room)

    assert available_room.white_player_id is not None
    assert available_room.black_player_id is not None
    publish_room_activated(
        available_room.id,
        available_room.white_player_id,
        available_room.black_player_id,
    )

    return available_room


def get_room(db: Session, room_id: int) -> Room:
    room = get_room_by_id(db, room_id)

    if room is None:
        raise ValueError("Room not found")

    return room


def join_room(db: Session, room_id: int, user_id: int) -> tuple[Room, str]:
    room = get_room_by_id_for_update(db, room_id)

    if room is None:
        raise ValueError("Room not found")

    if room.white_player_id == user_id or room.black_player_id == user_id:
        return room, "player"

    if room.status == "waiting":
        room.black_player_id = user_id
        room.status = "active"
        db.commit()
        db.refresh(room)
        assert room.white_player_id is not None
        assert room.black_player_id is not None
        publish_room_activated(room.id, room.white_player_id, room.black_player_id)
        return room, "player"

    if room.status == "active":
        return room, "spectator"

    raise ValueError("Room is not available")



def close_room(db: Session, room_id: int) -> str:
    room = get_room_by_id(db, room_id)

    if room is None:
        raise ValueError("Room not found")

    delete_room(db, room)

    return "Room closed"