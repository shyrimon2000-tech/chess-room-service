# Chess Room Service

A room management microservice for a real-time chess web application built with a microservice architecture.

This service handles room creation, quick matchmaking, player join and leave flows, spectator connections, admin room management, and publishing room lifecycle events to Redis so game-service can create and track games.

---

## Badges

Main: [![CI Main](https://github.com/shyrimon2000-tech/chess-room-service/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/shyrimon2000-tech/chess-room-service/actions)

Dev: [![CI Dev](https://github.com/shyrimon2000-tech/chess-room-service/actions/workflows/ci.yml/badge.svg?branch=dev)](https://github.com/shyrimon2000-tech/chess-room-service/actions)

---

## Features

- Room creation with automatic white player assignment
- Quick matchmaking: join an available waiting room or create a new one
- Join a specific room by ID — player or spectator
- Leave a waiting room
- Admin-only room deletion
- Room status lifecycle: `waiting` → `active` → `finished`
- Redis pub/sub: publishes `room_created` and `room_activated`, subscribes to `game_over` and `game_abandoned`
- Automatic room status update when game-service reports a result
- JWT token validation via shared secret
- Role-based access control with `user` and `admin` roles
- MySQL database persistence
- SQLAlchemy ORM
- Alembic database migrations
- Automated tests with pytest

---

## Tech Stack

- Python 3.11
- FastAPI
- Uvicorn
- SQLAlchemy
- Alembic
- MySQL
- PyMySQL
- Redis
- python-jose
- Pydantic Settings
- pytest
- Docker
- Docker Compose

---

## Project Structure

```text
app/
├── routers/
│   └── rooms.py
├── services/
│   ├── room_service.py
│   └── auth_dependencies.py
├── repositories/
│   └── room_repo.py
├── events/
│   ├── publisher.py
│   └── subscriber.py
├── config.py
├── database.py
├── main.py
├── models.py
└── schemas.py

alembic/
├── versions/
└── env.py

tests/
├── test_rooms.py
└── test_subscriber.py
```

---

## HTTP API

### Health Check

```http
GET /health
```

Response:

```json
{ "status": "ok" }
```

---

### List Rooms

```http
GET /rooms
```

Required header:

```http
Authorization: Bearer <access_token>
```

Returns all rooms with status `waiting` or `active`.

Response:

```json
[
  {
    "id": 1,
    "status": "waiting",
    "white_player_id": 7,
    "black_player_id": null,
    "game_id": null,
    "created_at": "2026-06-01T10:00:00"
  }
]
```

---

### Create Room

```http
POST /rooms
```

Required header:

```http
Authorization: Bearer <access_token>
```

Creates a new waiting room. The caller becomes `white_player_id`. If the caller already has a waiting room, that room is returned instead of creating a new one.

Response `201` for a newly created room, `200` if an existing waiting room was returned.

Publishes `room_created` to Redis when a new room is created.

---

### Quick Join or Create

```http
POST /rooms/quick
```

Required header:

```http
Authorization: Bearer <access_token>
```

Finds an available waiting room and joins it. If none is available, creates a new room.

- If the caller already has a waiting room, returns it unchanged.
- If an available room is found, the caller becomes `black_player_id`, status becomes `active`, and `room_activated` is published to Redis.
- If no available room exists, a new room is created and `room_created` is published to Redis.

---

### Get Room

```http
GET /rooms/{room_id}
```

Required header:

```http
Authorization: Bearer <access_token>
```

Response: room object.

---

### Join Room

```http
POST /rooms/{room_id}/join
```

Required header:

```http
Authorization: Bearer <access_token>
```

Joins a specific room by ID.

Response:

```json
{
  "role": "player",
  "status": "active",
  "id": 1,
  "white_player_id": 7,
  "black_player_id": 12,
  ...
}
```

- If the caller is already a player in the room, returns `role: "player"`.
- If the room is `waiting`, the caller becomes `black_player_id`, status becomes `active`, `role: "player"` is returned, and `room_activated` is published to Redis.
- If the room is `active`, the caller joins as a spectator and `role: "spectator"` is returned.
- If the room is `finished`, returns 400.

---

### Leave Room

```http
POST /rooms/{room_id}/leave
```

Required header:

```http
Authorization: Bearer <access_token>
```

Leaves a waiting room. Only allowed when the room status is `waiting`. If the room becomes empty after leaving, it is deleted.

Returns 400 if the room is active or the caller is not a player.

---

### Close Room (Admin Only)

```http
DELETE /rooms/{room_id}
```

Required header:

```http
Authorization: Bearer <access_token>
```

Requires `role: "admin"` in the JWT. Permanently deletes the room from the database.

Response:

```json
{ "message": "Room closed" }
```

---

## Redis Events

### Published: `room_events` channel

```json
{ "event": "room_created", "room_id": 42, "white_player_id": 7 }
```

Published when a new waiting room is created. Game-service subscribes and creates a new game with `white_player_id` set.

```json
{ "event": "room_activated", "room_id": 42, "white_player_id": 7, "black_player_id": 12 }
```

Published when the second player joins the room via HTTP.

### Subscribed: `game_events` channel

```json
{ "event": "game_over", "game_id": 1, "room_id": 42, "winner": "white" }
```

```json
{ "event": "game_abandoned", "game_id": 1, "room_id": 42 }
```

When received, room-service marks the room as `finished` and stores `game_id`.

---

## Room Lifecycle

```text
waiting → active → finished
```

| Status | Meaning |
|---|---|
| `waiting` | Room created, waiting for second player |
| `active` | Both players joined, game in progress |
| `finished` | Game ended — set by Redis event from game-service |

Admin can delete a room at any time — the row is removed from the database.

---

## Environment Variables

Create a `.env` file based on `.env.example`.

Example:

```env
# MySQL container settings
MYSQL_ROOT_PASSWORD=change-root-password
MYSQL_DATABASE=chess_room_db
MYSQL_USER=chess_user
MYSQL_PASSWORD=change-user-password

# Application database connection
DATABASE_URL=mysql+pymysql://chess_user:change-user-password@room-db:3306/chess_room_db

# JWT settings
JWT_SECRET_KEY=change-this-secret-key
JWT_ALGORITHM=HS256

# Redis settings
REDIS_URL=redis://redis:6379/0
```

Important:

- `JWT_SECRET_KEY` and `JWT_ALGORITHM` must match the values used in `chess-auth-service` and `chess-game-service`. If they differ, token validation will fail with 401.
- `DATABASE_URL` uses `room-db` as the MySQL host when running with Docker Compose.
- `.env` contains real secrets and must not be committed.
- `.env.example` is safe to commit as a template.

---

## Run with Docker Compose

Build and start the service:

```bash
docker compose up --build
```

Run in detached mode:

```bash
docker compose up -d --build
```

The API will be available at:

```text
http://127.0.0.1:8001
```

Swagger UI:

```text
http://127.0.0.1:8001/docs
```

Health check:

```text
http://127.0.0.1:8001/health
```

---

## Database Migrations

The application does not create tables automatically on startup. Schema changes are managed through Alembic migrations.

Apply migrations:

```bash
docker compose exec room-service alembic upgrade head
```

Create a new migration:

```bash
docker compose exec room-service alembic revision --autogenerate -m "migration message"
```

Check current version:

```bash
docker compose exec room-service alembic current
```

Current database tables:

```text
alembic_version
rooms
```

---

## Run Locally without Docker

Create a virtual environment:

```bash
python -m venv .venv
```

Activate it.

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

Install dependencies:

```bash
pip install -r requirements-dev.txt
```

Run the service:

```bash
uvicorn app.main:app --reload
```

Notes:

- Requires a running MySQL instance and Redis instance reachable from the local machine.
- `requirements.txt` contains production dependencies only.
- `requirements-dev.txt` includes `requirements.txt` and adds `pytest` for running tests.

---

## Database

### rooms

| Field | Type | Description |
|---|---|---|
| `id` | Integer PK | Internal room ID |
| `status` | String(20) | `waiting`, `active`, or `finished` |
| `white_player_id` | Integer nullable | Creator of the room — plain int, no FK to auth-service |
| `black_player_id` | Integer nullable | Second player — set when they join |
| `game_id` | Integer nullable | Game assigned to this room — set when game-service reports a result |
| `created_at` | DateTime | UTC |

Cross-service foreign keys are intentionally avoided. `white_player_id`, `black_player_id`, and `game_id` are plain integers.

---

## Automated Tests

Run tests:

```bash
pytest tests/ -v
```

Test coverage includes:

- empty room list
- waiting room appears in list
- room creation returns correct fields
- duplicate room creation returns existing room
- get room by ID
- room not found returns 404
- quick join creates a new room when none is available
- quick join joins an existing waiting room
- quick join returns own existing waiting room
- join room as second player activates it
- join own room returns player role
- join active room returns spectator role
- join non-existent room returns 400
- leave waiting room
- leave empties room and deletes it
- leave active room returns 400
- non-player leave returns 400
- admin close room
- admin close room removes it from database
- admin close non-existent room returns 404
- non-admin close room returns 403
- request without token returns 401
- request with invalid token returns 401
- request with expired token returns 401
- `game_over` event marks room as finished
- `game_over` event stores game_id on room
- `game_abandoned` event marks room as finished
- `game_abandoned` event stores game_id on room
- non-message Redis event type ignored
- unknown event type ignored
- unknown room_id handled gracefully

Current test count:

```text
31 passed
```

---

## Development Status

Implemented endpoints:

```text
GET    /health
GET    /rooms
POST   /rooms
POST   /rooms/quick
GET    /rooms/{room_id}
POST   /rooms/{room_id}/join
POST   /rooms/{room_id}/leave
DELETE /rooms/{room_id}
```

Implemented infrastructure:

```text
Dockerfile
docker-compose.yml
MySQL container
Redis (shared with game-service)
Alembic migrations
pytest test suite
Redis pub/sub publisher (room_created, room_activated)
Redis pub/sub subscriber (game_over, game_abandoned)
```

Current automated test status:

```text
31 tests passed
```
