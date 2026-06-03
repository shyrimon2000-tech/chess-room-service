from sqlalchemy.orm import Session

from app.models import Room


def create_room(db: Session, user_id: int) -> Room:
    room = Room(
        white_player_id=user_id,
        black_player_id=None,
        status="waiting",
    )

    db.add(room)
    db.commit()
    db.refresh(room)

    return room


def get_room_by_id(db: Session, room_id: int) -> Room | None:
    return db.query(Room).filter(Room.id == room_id).first()


def find_user_waiting_room(db: Session, user_id: int) -> Room | None:
    return (
        db.query(Room)
        .filter(Room.status == "waiting")
        .filter(Room.white_player_id == user_id)
        .filter(Room.black_player_id.is_(None))
        .first()
    )


def find_available_waiting_room(db: Session, user_id: int) -> Room | None:
    return (
        db.query(Room)
        .filter(Room.status == "waiting")
        .filter(Room.black_player_id.is_(None))
        .filter(Room.white_player_id != user_id)
        .first()
    )


def get_all_rooms(db: Session) -> list[Room]:
    return (
        db.query(Room)
        .filter(Room.status.in_(["waiting", "active"]))
        .all()
    )


def delete_room(db: Session, room: Room) -> None:
    db.delete(room)
    db.commit()