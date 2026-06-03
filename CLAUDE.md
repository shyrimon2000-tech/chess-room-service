# CLAUDE.md — chess-room-service

This file guides Claude Code when working in this repository.

## Collaboration Style

The user is learning backend development. Apply these principles in every session:

- When introducing a new concept, pattern, or tool — briefly flag it so it registers ("здесь мы используем X потому что..."). Don't over-explain, one sentence is enough.
- Proactively offer to go deeper on anything non-obvious ("хочешь объясню почему именно так?").
- Before applying any change, explain what it does and where it takes effect — let the user decide.
- Don't make decisions silently. State what you're about to do and why, even for small things.
- The user will ask to go deeper when they want — don't over-explain by default.

## What This Service Is

`chess-room-service` is the room management microservice for a real-time chess web application built with a microservice architecture.

**This service is responsible for:**
- Creating rooms
- Quick matchmaking (join or create)
- Reading room info and spectating
- Leaving a waiting room
- Admin closing a room

**This service is NOT responsible for:**
- Chess move validation or game state
- WebSocket gameplay
- Active game disconnect handling or reconnect timers
- Deciding game results
- Tracking spectators in the database

Those responsibilities belong to the future `chess-game-service`.

### Service Ecosystem

| Service | Status | Role |
|---|---|---|
| `chess-auth-service` | Implemented | Issues JWT tokens, manages users |
| `chess-room-service` | This repo | Room lifecycle and matchmaking |
| `chess-game-service` | Planned | WebSocket gameplay, game results, disconnect logic |
| `presence-service` | Optional future split | Online user tracking (V1: may live inside game-service) |

The services are deployed as separate Docker Compose projects today and will later be deployed to Kubernetes.

---

## Architecture

This service follows a strict 4-layer pattern. Never skip or bypass layers.

```
routers → services → repositories → models
```

### Layer Responsibilities

**`app/routers/`** — HTTP layer only
- Parse path params and inject dependencies
- Call service functions
- Convert `ValueError` from services into `HTTPException`
- No business logic, no direct DB access

**`app/services/`** — Business logic
- Enforce room lifecycle rules
- Implement matchmaking logic
- Own the decision of what a user is allowed to do
- Raise `ValueError` with a message when a rule is violated

**`app/repositories/`** — Database queries only
- Translate service intent into SQLAlchemy queries
- No business rules, no HTTP concerns
- Functions: `create_room`, `get_room_by_id`, `find_user_waiting_room`, `find_available_waiting_room`, `delete_room`

**`app/models.py`** — SQLAlchemy ORM models
- `Room` model maps to the `rooms` table

**`app/schemas.py`** — Pydantic schemas for request/response serialization

---

## Database Model

Single table: `rooms`

| Field | Type | Notes |
|---|---|---|
| `id` | Integer PK | |
| `status` | String(20) | `waiting`, `active`, `closed` |
| `white_player_id` | Integer nullable | Plain int — no FK to auth-service |
| `black_player_id` | Integer nullable | Plain int — no FK to auth-service |
| `game_id` | Integer nullable | Plain int — no FK to game-service |
| `created_at` | DateTime | UTC |

`white_player_id` and `black_player_id` are plain integers. User data belongs to `auth-service`. Cross-service foreign keys are intentionally avoided.

---

## Room Status Lifecycle

```
waiting → active → closed
                 ↘ finished  (planned, not implemented)
```

| Status | Meaning |
|---|---|
| `waiting` | Room created, waiting for second player |
| `active` | Both players joined, game in progress |
| `closed` | Admin closed the room |
| `finished` | Planned — game ended normally (future game-service concern) |

### Lifecycle Rules

1. **Create room** (`POST /rooms`) — user becomes `white_player_id`, status is `waiting`
2. **Quick join** (`POST /rooms/quick`) — finds an available waiting room or creates a new one; joining user becomes `black_player_id`, status becomes `active`
3. **Leave room** (`POST /rooms/{room_id}/leave`) — only allowed for `waiting` rooms; if both player slots become empty the room is deleted immediately
4. **Active room leave** — intentionally blocked in room-service; active game outcomes belong to the future game-service
5. **Admin close** (`DELETE /rooms/{room_id}`) — sets status to `closed`; room management, not gameplay logic

---

## Key Conventions

### Error Flow

Services raise `ValueError` with a plain message. Routers catch it and raise `HTTPException`.

```python
# service
raise ValueError("Room not found")

# router
except ValueError as error:
    raise HTTPException(status_code=404, detail=str(error))
```

### Auth Pattern

All protected endpoints use `get_current_user`. Admin-only endpoints use `require_admin`.

JWT tokens are validated **locally** using the shared `JWT_SECRET_KEY`. Room-service never calls auth-service over HTTP to validate a token.

Token flow:
1. Frontend logs in through auth-service and receives an access token
2. Frontend sends `Authorization: Bearer <token>` to room-service
3. Room-service decodes the token locally and extracts `sub` (user id) and `role`

**Never trust `user_id` or `role` from request body or query params.** Always read them from the decoded JWT via `get_current_user`.

### Cross-Service Boundary

Once a room is `active`, room-service does not decide game outcomes.

Active game disconnects, reconnect timers, and game results are future game-service responsibilities. When game-service is implemented, it will publish a Redis event and room-service will update the room status in response.

---

## Commands

### Run locally (dev)

Requires a running MySQL instance and a valid `.env` file.

```bash
uvicorn app.main:app --reload
```

### Run with Docker Compose

```bash
docker compose up --build
```

Service is available at `http://localhost:8001`. The MySQL container is internal and does not expose port 3306 to the host.

### Apply Alembic migrations

When using Docker Compose, run migrations inside the service container to use Docker's internal network:

```bash
docker compose exec room-service alembic upgrade head
```

The app does **not** run migrations on startup. Migrations are a manual step during development and should be a separate job in future CI/CD and Kubernetes deployments.

### Run tests

```bash
pytest tests/
```

---

## Environment Setup

Copy `.env.example` to `.env` and fill in the values before running.

```bash
cp .env.example .env
```

### Key variables

| Variable | Notes |
|---|---|
| `DATABASE_URL` | Must use `room-db` as hostname when running via Docker Compose |
| `JWT_SECRET_KEY` | Must match the value used in `chess-auth-service` |
| `JWT_ALGORITHM` | Must match — default `HS256` |
| `REDIS_URL` | Can be set even before Redis is actively used |
| `MYSQL_*` | Used by the Docker Compose MySQL container |

`JWT_SECRET_KEY` and `JWT_ALGORITHM` are shared across services. If they differ, token validation in room-service will fail with 401.

---

## In Progress / Not Yet Implemented

| Item | Status |
|---|---|
| `app/events/subscriber.py` | File exists, not implemented. Redis pub/sub listener planned. |
| `tests/test_rooms.py` | File exists, empty. Tests not written yet. |
| Redis pub/sub | Planned. game-service will publish room lifecycle events; room-service will subscribe and update room status. |
| `chess-game-service` | Not implemented. Planned for WebSocket gameplay and game result handling. |
| Room status `finished` | Planned. Will be set by room-service when it receives a game-over event from game-service. |

Do not document Redis as working. Do not assume game-service exists.

---

## What To Avoid

**Layer violations**
- Do not put SQL queries in routers
- Do not put business logic in repositories
- Do not call the database from anywhere except the repository layer

**Auth**
- Do not trust `user_id` or `role` from request body or query params
- Do not call auth-service over HTTP to validate tokens — validate locally with the shared secret

**Cross-service boundaries**
- Do not add Foreign Keys from `rooms` to users or games in other services
- Do not handle active game results or disconnect logic in room-service
- Do not store spectators in the database for V1

**Room lifecycle**
- Do not allow leaving an active room through room-service
- Do not add game result logic to room-service — that belongs to game-service

**Infrastructure**
- Do not run `alembic upgrade head` automatically on app startup
- Do not expose the MySQL container port to the host unnecessarily
