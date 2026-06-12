import json
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.events.subscriber import _handle_message
from app.models import Base, Room

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
    room = Room(
        white_player_id=white_player_id,
        black_player_id=black_player_id,
        status=status,
    )
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


def get_room(room_id: int) -> Room | None:
    db = TestingSessionLocal()
    room = db.query(Room).filter(Room.id == room_id).first()
    db.close()
    return room


# --- game_over ---

def test_game_over_deletes_room():
    room_id = make_room(status="active")
    send_event({"event": "game_over", "game_id": 5, "room_id": room_id, "winner": "white"})  # noqa: E501
    assert get_room(room_id) is None


def test_game_over_missing_room_id_handled_gracefully():
    send_event({"event": "game_over", "game_id": 5, "winner": "white"})


# --- game_abandoned ---

def test_game_abandoned_deletes_active_room():
    room_id = make_room(status="active")
    send_event({"event": "game_abandoned", "game_id": 3, "room_id": room_id})
    assert get_room(room_id) is None


def test_game_abandoned_deletes_waiting_room():
    room_id = make_room(status="waiting", black_player_id=None)
    send_event({"event": "game_abandoned", "game_id": 3, "room_id": room_id})
    assert get_room(room_id) is None


def test_game_abandoned_missing_room_id_handled_gracefully():
    send_event({"event": "game_abandoned", "game_id": 3})


# --- game_created ---

def test_game_created_links_game_id():
    room_id = make_room(status="active")
    send_event({"event": "game_created", "game_id": 7, "room_id": room_id})
    assert get_room(room_id).game_id == 7


def test_game_created_idempotent():
    room_id = make_room(status="active")
    send_event({"event": "game_created", "game_id": 7, "room_id": room_id})
    send_event({"event": "game_created", "game_id": 7, "room_id": room_id})
    assert get_room(room_id).game_id == 7


def test_game_created_unknown_room_handled_gracefully():
    send_event({"event": "game_created", "game_id": 7, "room_id": 9999})


def test_game_created_missing_room_id_handled_gracefully():
    send_event({"event": "game_created", "game_id": 7})


# --- edge cases ---

def test_non_message_type_ignored():
    room_id = make_room(status="active")
    message = {
        "type": "subscribe",
        "data": json.dumps({"event": "game_over", "room_id": room_id}),
    }
    with patch("app.events.subscriber.SessionLocal", TestingSessionLocal):
        _handle_message(message)
    assert get_room(room_id) is not None


def test_unknown_event_ignored():
    room_id = make_room(status="active")
    send_event({"event": "some_other_event", "room_id": room_id})
    assert get_room(room_id) is not None


def test_unknown_room_handled_gracefully():
    send_event({"event": "game_over", "game_id": 5, "room_id": 9999, "winner": "black"})


def test_game_over_second_instance_idempotent():
    """Room already deleted by another instance — second processing is a no-op."""
    room_id = make_room(status="active")
    send_event({"event": "game_over", "game_id": 5, "room_id": room_id, "winner": "white"})  # noqa: E501
    send_event({"event": "game_over", "game_id": 5, "room_id": room_id, "winner": "white"})  # noqa: E501
    assert get_room(room_id) is None


def test_invalid_json_handled_gracefully():
    message = {"type": "message", "data": "not valid json {{{"}
    with patch("app.events.subscriber.SessionLocal", TestingSessionLocal):
        _handle_message(message)
