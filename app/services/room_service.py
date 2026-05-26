from sqlalchemy.orm import Session

from app.models import Room
from app.repositories.room_repo import (
    create_room,
    delete_room,
    find_available_waiting_room,
    find_user_waiting_room,
    get_room_by_id,
)


def create_new_room(db: Session, user_id: int) -> Room:
    existing_waiting_room = find_user_waiting_room(db, user_id)

    if existing_waiting_room is not None:
        return existing_waiting_room

    return create_room(db, user_id)


def quick_join_or_create_room(db: Session, user_id: int) -> Room:
    user_waiting_room = find_user_waiting_room(db, user_id)

    if user_waiting_room is not None:
        return user_waiting_room

    available_room = find_available_waiting_room(db, user_id)

    if available_room is None:
        return create_room(db, user_id)

    available_room.black_player_id = user_id
    available_room.status = "active"

    db.commit()
    db.refresh(available_room)

    return available_room


def get_room_for_spectate(db: Session, room_id: int) -> Room:
    room = get_room_by_id(db, room_id)

    if room is None:
        raise ValueError("Room not found")

    return room


def leave_room(db: Session, room_id: int, user_id: int) -> str:
    room = get_room_by_id(db, room_id)

    if room is None:
        raise ValueError("Room not found")

    if room.status != "waiting":
        raise ValueError("Cannot leave active room through room-service")

    if room.white_player_id == user_id:
        room.white_player_id = None
    elif room.black_player_id == user_id:
        room.black_player_id = None
    else:
        raise ValueError("User is not a player in this room")

    if room.white_player_id is None and room.black_player_id is None:
        delete_room(db, room)
        return "Room deleted because it became empty"

    db.commit()
    db.refresh(room)

    return "Left room successfully"


def close_room(db: Session, room_id: int) -> Room:
    room = get_room_by_id(db, room_id)

    if room is None:
        raise ValueError("Room not found")

    room.status = "closed"

    db.commit()
    db.refresh(room)

    return room