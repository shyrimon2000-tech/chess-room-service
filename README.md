# Chess Room Service

A room management microservice for a real-time chess web application built with a microservice architecture.

This service handles room creation, quick matchmaking, player and spectator join flows, admin room management, and publishing room lifecycle events to Redis so game-service can create and track games.

---

## Badges

Dev: [![CI Dev](https://github.com/shyrimon2000-tech/chess-room-service/actions/workflows/ci.yml/badge.svg?branch=dev)](https://github.com/shyrimon2000-tech/chess-room-service/actions)

Pull Request: [![CI PR](https://github.com/shyrimon2000-tech/chess-room-service/actions/workflows/ci.yml/badge.svg?event=pull_request)](https://github.com/shyrimon2000-tech/chess-room-service/actions)

---

## Features

- Room creation with automatic white player assignment
- Quick matchmaking: join an available waiting room or create a new one
- Join a specific room by ID — player or spectator
- Admin-only room deletion
- Room status lifecycle: `waiting` → `active` → `[deleted]`
- Redis pub/sub: publishes `room_created` and `room_activated`; subscribes to `game_created`, `game_over`, and `game_abandoned`
- Automatic room deletion when game-service reports a result
- Startup probes with tenacity retry for DB and Redis
- JWT token validation via shared secret
- Role-based access control with `user` and `admin` roles
- MySQL database persistence
- SQLAlchemy ORM
- Alembic database migrations
- Unit tests with pytest (47 tests)
- End-to-end tests with Playwright (34 tests across 9 scenarios)

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
- tenacity
- pytest
- Playwright (e2e)
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

tests/                        # unit tests
├── test_rooms.py
├── test_publisher.py
└── test_subscriber.py

e2e_tests/                    # end-to-end tests (Playwright)
├── chess_test1.py            # T1–T4:   resign flow
├── chess_test2.py            # T5–T8:   disconnect + reconnect within 30 s
├── chess_test3.py            # T9–T12:  disconnect timeout → game abandoned
├── chess_test4.py            # T13–T16: resign button visibility + room cleanup
├── chess_test5.py            # T17–T20: quick join + spectator join
├── chess_test6.py            # T21–T23: auth flows (unauth redirect, bad creds, logout)
├── chess_test7.py            # T24–T27: spectator perspective + board updates
├── chess_test8.py            # T28–T31: board interaction + turn guard
├── chess_test9.py            # T32–T34: return-to-game panel
├── helpers.py
├── cleanup.py
└── debug_ws.py

docker-compose.e2e.yml        # full multi-service stack for e2e
nginx.dev.conf                # nginx reverse-proxy config for e2e frontend
pytest-e2e.ini                # pytest config for e2e suite
requirements-e2e.txt          # playwright + pytest-playwright
e2e_versions.env              # pinned versions of services pulled from GHCR
.env.e2e                      # shared env for all services in e2e stack
```

---

## CI Pipeline

```text
push to dev:
  lint → type-check → unit tests → docker build

pull_request to main  /  tag push (x.y.z):
  lint → type-check → unit tests → docker build → e2e tests

tag push only:
  … → e2e tests → publish to GHCR
```

### Jobs

| Job | Trigger | Description |
|---|---|---|
| `lint` | push dev, PR, tag | ruff check on `app/` and `tests/` |
| `type-check` | push dev, PR, tag | mypy on `app/` |
| `test` | push dev, PR, tag | pytest unit tests |
| `docker-build` | push dev, PR, tag | builds image, saves as artifact |
| `e2e` | PR to main, tag | spins up full stack, runs 34 Playwright tests |
| `publish` | tag only | pushes versioned image to `ghcr.io` after e2e passes |

### E2E stack

The e2e job loads the locally built `chess-room-service` image from the artifact and pulls `chess-auth-service`, `chess-game-service`, and `chess-frontend-service` from GHCR at the versions pinned in `e2e_versions.env`. This means every PR tests the new room-service code against the real deployed versions of the other services.

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
    "white_player_nickname": "alex",
    "black_player_nickname": null,
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
{ "event": "game_created",   "game_id": 1, "room_id": 42 }
{ "event": "game_over",      "game_id": 1, "room_id": 42, "winner": "white" }
{ "event": "game_abandoned", "game_id": 1, "room_id": 42 }
```

`game_created` — room-service stores `game_id` on the room row so clients can navigate to the game.

`game_over` and `game_abandoned` — room-service **deletes the room row** from the database.

---

## Room Lifecycle

```text
waiting → active → [deleted]
```

| Status | Meaning |
|---|---|
| `waiting` | Room created, waiting for second player |
| `active` | Both players joined, game in progress |

Rooms are **deleted from the database** when the game ends — there is no `finished` status. The subscriber handles `game_over` and `game_abandoned` by calling `delete_room()`.

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
- `requirements-dev.txt` includes `requirements.txt` and adds `pytest`, `mypy`, `ruff` for development.

---

## Database

### rooms

| Field | Type | Description |
|---|---|---|
| `id` | Integer PK | Internal room ID |
| `status` | String(20) | `waiting` or `active` |
| `white_player_id` | Integer nullable | Creator of the room — plain int, no FK to auth-service |
| `black_player_id` | Integer nullable | Second player — set when they join |
| `white_player_nickname` | String(50) nullable | Stored at join time so game-service doesn't need to call auth |
| `black_player_nickname` | String(50) nullable | Same as above |
| `game_id` | Integer nullable | Plain int — set when game-service publishes `game_created` |
| `created_at` | DateTime | UTC |

Cross-service foreign keys are intentionally avoided. `white_player_id`, `black_player_id`, and `game_id` are plain integers.

---

## Unit Tests

Run:

```bash
pytest tests/ -v
```

Coverage:

- empty room list
- waiting room appears in list
- room creation returns correct fields
- room creation sets `game_id` to null
- duplicate room creation returns existing room
- get room by ID
- get room returns `game_id` after game is linked
- room not found returns 404
- quick join creates a new room when none is available
- quick join joins an existing waiting room
- quick join returns own existing waiting room
- join room as second player activates it
- join own room returns player role
- join active room returns spectator role
- join non-existent room returns 400
- admin close room
- admin close room removes it from database
- admin close non-existent room returns 404
- non-admin close room returns 403
- request without token returns 401
- request with invalid token returns 401
- request with expired token returns 401
- publisher swallows Redis error on `room_created`
- publisher swallows Redis error on `room_activated`
- `game_created` event stores `game_id` on room
- `game_created` is idempotent
- `game_created` missing room_id handled gracefully
- `game_over` event deletes room
- `game_over` missing room_id handled gracefully
- `game_abandoned` event deletes room
- `game_abandoned` missing room_id handled gracefully
- `game_over` second instance idempotent (room already deleted)
- non-message Redis event type ignored
- unknown event type ignored
- invalid JSON handled gracefully

```text
47 passed
```

---

## E2E Tests

The e2e suite runs against the full multi-service stack via Playwright. It is executed automatically in CI on every PR to main and before every versioned release.

### Run locally

Start the stack:

```bash
cat .env.e2e e2e_versions.env > .env.combined
docker compose -f docker-compose.e2e.yml --env-file .env.combined up -d --wait
```

Install dependencies and run:

```bash
pip install -r requirements-e2e.txt
playwright install chromium --with-deps
python -m pytest -c pytest-e2e.ini -v
```

Tear down:

```bash
docker compose -f docker-compose.e2e.yml --env-file .env.combined down
```

### Scenarios

| Tests | Scenario |
|---|---|
| T1–T4 | Resign flow: game starts, white resigns, both players see correct banners |
| T5–T8 | Disconnect + reconnect within 30 s: banner shown, hidden on reconnect, game resumes |
| T9–T12 | Disconnect timeout: opponent wins, game abandoned, room deleted from list |
| T13–T16 | Resign button visibility: hidden after game over, room absent after cleanup |
| T17–T20 | Quick join: creates room when none available; joins existing; spectator via explicit join |
| T21–T23 | Auth flows: unauthenticated redirect, wrong password error, logout clears session |
| T24–T27 | Spectator: reaches game page, sees white's perspective, no resign button, sees board updates |
| T28–T31 | Board interaction: legal move highlights, turn guard, move updates both boards |
| T32–T34 | Return-to-game panel: intentional navigation shows panel, not auto-redirect |

```text
34 passed
```

### Service versions

Pinned in `e2e_versions.env`. Update the version of a service to test against a new release:

```env
AUTH_SERVICE_VERSION=1.0.0
GAME_SERVICE_VERSION=1.0.0
FRONTEND_VERSION=1.0.0
```

The locally built `chess-room-service` image is always used — it is never pulled from the registry during e2e.

---

## Development Status

**Completed.**

All endpoints implemented and tested. CI pipeline fully configured.

### Endpoints

```text
GET    /health
GET    /rooms
POST   /rooms
POST   /rooms/quick
GET    /rooms/{room_id}
POST   /rooms/{room_id}/join
DELETE /rooms/{room_id}
```

### Infrastructure

```text
Dockerfile
docker-compose.yml              local development stack
docker-compose.e2e.yml          full multi-service e2e stack
MySQL (room-db)
Redis (shared with game-service)
nginx reverse-proxy (e2e)
Alembic migrations
Unit test suite (pytest) — 47 tests
E2E test suite (Playwright) — 34 tests
CI pipeline (GitHub Actions)
    lint → type-check → unit tests → docker build → e2e → publish
Redis pub/sub publisher (room_created, room_activated)
Redis pub/sub subscriber (game_created, game_over, game_abandoned)
Startup probes with tenacity retry for DB and Redis
Docker image published to ghcr.io on versioned tag
```
