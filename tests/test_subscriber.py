import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from unittest.mock import patch

from app.models import Base, Room
from app.events.subscriber import _handle_message


engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(autouse=True)
def reset_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def make_room(status="active", white_player_id=1, black_player_id=2):
    db = TestingSessionLocal()
    room = Room(white_player_id=white_player_id, black_player_id=black_player_id, status=status)
    db.add(room)
    db.commit()
    db.refresh(room)
    room_id = room.id
    db.close()
    return room_id


def send_event(data: dict):
    message = {"type": "message", "data": json.dumps(data)}
    with patch("app.events.subscriber.SessionLocal", TestingSessionLocal):
        _handle_message(message)


def get_room(room_id: int) -> Room:
    db = TestingSessionLocal()
    room = db.query(Room).filter(Room.id == room_id).first()
    db.close()
    return room


# --- game_over ---

def test_game_over_marks_room_finished():
    room_id = make_room(status="active")
    send_event({"event": "game_over", "game_id": 5, "room_id": room_id, "winner": "white"})
    assert get_room(room_id).status == "finished"


def test_game_over_stores_game_id():
    room_id = make_room(status="active")
    send_event({"event": "game_over", "game_id": 5, "room_id": room_id, "winner": "white"})
    assert get_room(room_id).game_id == 5


# --- game_abandoned ---

def test_game_abandoned_marks_room_finished():
    room_id = make_room(status="waiting", black_player_id=None)
    send_event({"event": "game_abandoned", "game_id": 3, "room_id": room_id})
    assert get_room(room_id).status == "finished"


def test_game_abandoned_stores_game_id():
    room_id = make_room(status="waiting", black_player_id=None)
    send_event({"event": "game_abandoned", "game_id": 3, "room_id": room_id})
    assert get_room(room_id).game_id == 3


# --- edge cases ---

def test_non_message_type_ignored():
    room_id = make_room(status="active")
    message = {"type": "subscribe", "data": json.dumps({"event": "game_over", "room_id": room_id})}
    with patch("app.events.subscriber.SessionLocal", TestingSessionLocal):
        _handle_message(message)
    assert get_room(room_id).status == "active"


def test_unknown_event_ignored():
    room_id = make_room(status="active")
    send_event({"event": "some_other_event", "room_id": room_id})
    assert get_room(room_id).status == "active"


def test_unknown_room_handled_gracefully():
    send_event({"event": "game_over", "game_id": 5, "room_id": 9999, "winner": "black"})
