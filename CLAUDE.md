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
- Creating rooms and assigning the white player
- Quick matchmaking (join an available room or create a new one)
- Joining a room by ID as a player or spectator
- Leaving a waiting room
- Admin room deletion
- Publishing `room_created` and `room_activated` events to Redis
- Subscribing to `game_over` and `game_abandoned` events to mark rooms as `finished`

**This service is NOT responsible for:**
- Chess move validation or game state
- WebSocket gameplay
- Active game disconnect handling or reconnect timers
- Deciding game results
- Tracking spectators in the database

Those responsibilities belong to `chess-game-service`.

### Service Ecosystem

| Service | Status | Role |
|---|---|---|
| `chess-auth-service` | Implemented | Issues JWT tokens, manages users |
| `chess-room-service` | This repo | Room lifecycle and matchmaking |
| `chess-game-service` | Implemented | WebSocket gameplay, game results, disconnect logic |
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
- Functions: `create_room`, `get_room_by_id`, `save_room`, `find_user_waiting_room`, `find_available_waiting_room`, `get_all_rooms`, `delete_room`

**`app/models.py`** — SQLAlchemy ORM models
- `Room` model maps to the `rooms` table

**`app/schemas.py`** — Pydantic schemas for request/response serialization

**`app/events/`** — Redis pub/sub
- `publisher.py` — publishes `room_created` and `room_activated` to the `room_events` channel
- `subscriber.py` — subscribes to `game_events`; handles `game_over` and `game_abandoned` by marking the room as `finished` and storing `game_id`

---

## Database Model

Single table: `rooms`

| Field | Type | Notes |
|---|---|---|
| `id` | Integer PK | |
| `status` | String(20) | `waiting`, `active`, `finished` |
| `white_player_id` | Integer nullable | Plain int — no FK to auth-service |
| `black_player_id` | Integer nullable | Plain int — no FK to auth-service |
| `game_id` | Integer nullable | Plain int — no FK to game-service; set when game ends |
| `created_at` | DateTime | UTC |

`white_player_id`, `black_player_id`, and `game_id` are plain integers. Cross-service foreign keys are intentionally avoided.

---

## Room Status Lifecycle

```
waiting → active → finished
```

| Status | Meaning |
|---|---|
| `waiting` | Room created, waiting for second player |
| `active` | Both players joined, game in progress |
| `finished` | Game ended — set by Redis event from game-service |

Admin can delete a room at any time — the row is removed from the database entirely.

### Lifecycle Rules

1. **Create room** (`POST /rooms`) — caller becomes `white_player_id`, status is `waiting`; publishes `room_created` to Redis
2. **Quick join** (`POST /rooms/quick`) — finds an available waiting room or creates a new one; joining user becomes `black_player_id`, status becomes `active`, publishes `room_activated`
3. **Join by ID** (`POST /rooms/{id}/join`) — second player activates room and publishes `room_activated`; third+ player joins as spectator
4. **Leave room** (`POST /rooms/{id}/leave`) — only allowed for `waiting` rooms; if both player slots become empty the room is deleted
5. **Active room leave** — intentionally blocked; active game outcomes belong to game-service
6. **Admin close** (`DELETE /rooms/{id}`) — deletes the room row from the database
7. **Game over** (Redis `game_over` or `game_abandoned`) — subscriber marks room as `finished`, stores `game_id`

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

### Redis Events

**Published to `room_events`:**

```json
{ "event": "room_created",   "room_id": 42, "white_player_id": 7 }
{ "event": "room_activated", "room_id": 42, "white_player_id": 7, "black_player_id": 12 }
```

`room_created` fires when a new waiting room is created. Game-service subscribes and creates a new game.

**Subscribed from `game_events`:**

```json
{ "event": "game_over",      "game_id": 1, "room_id": 42, "winner": "white" }
{ "event": "game_abandoned", "game_id": 1, "room_id": 42 }
```

Room-service handles both by setting `room.status = "finished"` and `room.game_id = game_id`.

### Cross-Service Boundary

Once a room is `active`, room-service does not decide game outcomes. Game results, disconnect handling, and reconnect timers belong to game-service. Room-service only reacts to Redis events from game-service.

Room-service never calls game-service over HTTP.

---

## HTTP API

| Method | Path | Description |
|---|---|---|
| `GET` | `/rooms` | List waiting and active rooms |
| `POST` | `/rooms` | Create a new room (or return existing waiting room) |
| `POST` | `/rooms/quick` | Quick join or create |
| `GET` | `/rooms/{room_id}` | Get room by ID |
| `POST` | `/rooms/{room_id}/join` | Join room as player or spectator |
| `POST` | `/rooms/{room_id}/leave` | Leave a waiting room |
| `DELETE` | `/rooms/{room_id}` | Admin-only: delete room |

---

## Commands

### Run locally (dev)

Requires a running MySQL instance, Redis instance, and a valid `.env` file.

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
| `JWT_SECRET_KEY` | Must match the value used in `chess-auth-service` and `chess-game-service` |
| `JWT_ALGORITHM` | Must match — default `HS256` |
| `REDIS_URL` | Required — used by publisher and subscriber |
| `MYSQL_*` | Used by the Docker Compose MySQL container |

`JWT_SECRET_KEY` and `JWT_ALGORITHM` are shared across all services. If they differ, token validation will fail with 401.

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
- Do not handle active game results, disconnect logic, or reconnect timers in room-service
- Do not store spectators in the database
- Do not call game-service over HTTP — use Redis events only

**Room lifecycle**
- Do not allow leaving an active room through room-service
- Do not set `status = "finished"` directly in HTTP handlers — only the Redis subscriber does this

**Infrastructure**
- Do not run `alembic upgrade head` automatically on app startup
- Do not expose the MySQL container port to the host unnecessarily
