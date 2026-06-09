from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.database import get_db
from app.main import app
from app.models import Base, Room
from app.services.auth_dependencies import CurrentUser, get_current_user

SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


def make_client(user_id: int, role: str = "user") -> TestClient:
    app.dependency_overrides[get_current_user] = (
        lambda: CurrentUser(id=user_id, role=role)
    )
    return TestClient(app)


@pytest.fixture(autouse=True)
def reset_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(autouse=True)
def reset_overrides():
    yield
    app.dependency_overrides.clear()
    app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def mock_publish_room_created():
    with patch("app.services.room_service.publish_room_created"):
        yield


# --- GET /rooms ---

def test_get_rooms_empty():
    r = make_client(1).get("/rooms")
    assert r.status_code == 200
    assert r.json() == []


def test_get_rooms_returns_waiting_room():
    make_client(1).post("/rooms")
    r = make_client(1).get("/rooms")
    assert r.status_code == 200
    assert len(r.json()) == 1
    assert r.json()[0]["status"] == "waiting"


@patch("app.services.room_service.publish_room_activated")
def test_get_rooms_returns_active_room(mock_publish):
    room = make_client(1).post("/rooms").json()
    make_client(2).post(f"/rooms/{room['id']}/join")
    r = make_client(1).get("/rooms")
    assert r.status_code == 200
    assert any(room["status"] == "active" for room in r.json())


def test_get_rooms_excludes_deleted_rooms():
    room_data = make_client(1).post("/rooms").json()
    db = TestingSessionLocal()
    try:
        room = db.query(Room).filter(Room.id == room_data["id"]).first()
        db.delete(room)
        db.commit()
    finally:
        db.close()
    r = make_client(1).get("/rooms")
    assert r.status_code == 200
    assert r.json() == []


# --- POST /rooms ---

def test_create_room_returns_201():
    r = make_client(1).post("/rooms")
    assert r.status_code == 201
    data = r.json()
    assert data["status"] == "waiting"
    assert data["white_player_id"] == 1
    assert data["black_player_id"] is None


def test_create_room_existing_returns_200():
    make_client(1).post("/rooms")
    r = make_client(1).post("/rooms")
    assert r.status_code == 200


@patch("app.services.room_service.publish_room_created")
def test_create_room_publishes_room_created(mock_publish):
    r = make_client(1).post("/rooms")
    data = r.json()
    mock_publish.assert_called_once_with(data["id"], 1)


@patch("app.services.room_service.publish_room_created")
def test_create_room_existing_does_not_publish(mock_publish):
    make_client(1).post("/rooms")
    mock_publish.reset_mock()
    make_client(1).post("/rooms")
    mock_publish.assert_not_called()


# --- GET /rooms/{room_id} ---

def test_get_room_by_id():
    created = make_client(1).post("/rooms").json()
    r = make_client(1).get(f"/rooms/{created['id']}")
    assert r.status_code == 200
    assert r.json()["id"] == created["id"]


def test_get_room_not_found():
    r = make_client(1).get("/rooms/999")
    assert r.status_code == 404


# --- POST /rooms/quick ---

@patch("app.services.room_service.publish_room_activated")
def test_quick_join_creates_room_when_none_available(mock_publish):
    r = make_client(1).post("/rooms/quick")
    assert r.status_code == 200
    assert r.json()["status"] == "waiting"
    mock_publish.assert_not_called()


@patch("app.services.room_service.publish_room_activated")
def test_quick_join_joins_existing_room(mock_publish):
    make_client(1).post("/rooms")
    r = make_client(2).post("/rooms/quick")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "active"
    assert data["black_player_id"] == 2
    mock_publish.assert_called_once()


@patch("app.services.room_service.publish_room_activated")
def test_quick_join_returns_own_waiting_room(mock_publish):
    make_client(1).post("/rooms")
    r = make_client(1).post("/rooms/quick")
    assert r.status_code == 200
    assert r.json()["status"] == "waiting"
    mock_publish.assert_not_called()


@patch("app.services.room_service.publish_room_created")
def test_quick_join_new_room_publishes_room_created(mock_publish):
    r = make_client(1).post("/rooms/quick")
    data = r.json()
    mock_publish.assert_called_once_with(data["id"], 1)


# --- POST /rooms/{room_id}/join ---

@patch("app.services.room_service.publish_room_activated")
def test_join_room_as_player(mock_publish):
    room = make_client(1).post("/rooms").json()
    r = make_client(2).post(f"/rooms/{room['id']}/join")
    assert r.status_code == 200
    data = r.json()
    assert data["role"] == "player"
    assert data["status"] == "active"
    mock_publish.assert_called_once()


@patch("app.services.room_service.publish_room_activated")
def test_join_own_room_returns_player(mock_publish):
    room = make_client(1).post("/rooms").json()
    r = make_client(1).post(f"/rooms/{room['id']}/join")
    assert r.status_code == 200
    assert r.json()["role"] == "player"
    mock_publish.assert_not_called()


@patch("app.services.room_service.publish_room_activated")
def test_join_active_room_as_spectator(mock_publish):
    room = make_client(1).post("/rooms").json()
    make_client(2).post(f"/rooms/{room['id']}/join")
    r = make_client(3).post(f"/rooms/{room['id']}/join")
    assert r.status_code == 200
    assert r.json()["role"] == "spectator"


def test_join_room_not_found():
    r = make_client(1).post("/rooms/999/join")
    assert r.status_code == 400


@patch("app.services.room_service.publish_room_activated")
def test_join_own_active_room_as_black_returns_player(mock_publish):
    room = make_client(1).post("/rooms").json()
    make_client(2).post(f"/rooms/{room['id']}/join")
    r = make_client(2).post(f"/rooms/{room['id']}/join")
    assert r.status_code == 200
    assert r.json()["role"] == "player"


def test_join_unavailable_room_returns_400():
    room_data = make_client(1).post("/rooms").json()
    db = TestingSessionLocal()
    try:
        room = db.query(Room).filter(Room.id == room_data["id"]).first()
        room.status = "finished"
        db.commit()
    finally:
        db.close()
    r = make_client(2).post(f"/rooms/{room_data['id']}/join")
    assert r.status_code == 400


# --- DELETE /rooms/{room_id} ---

def test_admin_close_room():
    room = make_client(1).post("/rooms").json()
    r = make_client(99, role="admin").delete(f"/rooms/{room['id']}")
    assert r.status_code == 200
    assert r.json()["message"] == "Room closed"


def test_admin_close_room_deleted_from_db():
    room = make_client(1).post("/rooms").json()
    make_client(99, role="admin").delete(f"/rooms/{room['id']}")
    r = make_client(1).get(f"/rooms/{room['id']}")
    assert r.status_code == 404


def test_admin_close_room_not_found():
    r = make_client(99, role="admin").delete("/rooms/999")
    assert r.status_code == 404


def test_non_admin_cannot_close_room():
    room = make_client(1).post("/rooms").json()
    r = make_client(2).delete(f"/rooms/{room['id']}")
    assert r.status_code == 403


# --- Auth ---

def test_request_without_token_returns_401():
    client = TestClient(app)
    r = client.get("/rooms")
    assert r.status_code == 401


def test_request_with_invalid_token_returns_401():
    client = TestClient(app)
    r = client.get("/rooms", headers={"Authorization": "Bearer invalid.token.here"})
    assert r.status_code == 401


def test_request_with_expired_token_returns_401():
    import datetime

    from jose import jwt as jose_jwt
    token = jose_jwt.encode(
        {
            "sub": "1",
            "role": "user",
            "exp": datetime.datetime.utcnow() - datetime.timedelta(hours=1),
        },
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    client = TestClient(app)
    r = client.get("/rooms", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401
