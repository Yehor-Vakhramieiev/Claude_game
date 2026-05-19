# CLAUDE.md — Bridge Card Game Project

## Project overview

Portfolio project for a junior Python developer job search (London).
Multiplayer card game **Bridge** (similar to 101 / Mau-Mau rules), implemented as a FastAPI backend with WebSocket gameplay, JWT auth, PostgreSQL, and Redis for multi-worker state sharing.

**Stack:**
- Python 3.14, FastAPI, Pydantic v2, SQLAlchemy 2 (async), asyncpg
- FastAPI Users 15.0.5 (JWT bearer auth)
- Redis with hiredis (state storage + Pub/Sub)
- pytest (81 tests, all passing)
- uv (package manager)
- Planned: Docker + Nginx, React/Vue frontend

---

## Game rules

- **Deck:** 36 cards (6–A in four suits)
- **Players:** 2–5
- **Deal:** 5 cards each; one card flipped face-up as the starting top card
- **Objective:** empty your hand first; losers accumulate points from remaining cards; first player to reach **150 points loses** (lowest score wins overall)
- **Turn:** play one or more cards of the **same rank** that match the **top card's rank or suit** (or the declared suit if a Jack was played)

### Card effects (all applied **immediately** before turn passes)
| Card | Effect |
|---|---|
| 6 | **Cover** — next player must play a 6 or keep drawing (turn does not advance while `cover_active=True`) |
| 7 | Next player **draws 2 cards + skips** their turn |
| 8 | Next player **draws 1 card** (turn still passes) |
| J (non-♠) | Player **declares a new suit**; next player must match that suit |
| J♠ | Same as J but worth **40 points** |
| K♥ | Next player **draws 5 cards** (worth 50 points) |
| A | Next player **skips** their turn |

### Special win condition
- **Bridge call:** playing 4 cards of the same rank in one turn ends the round immediately (instant win for that round)

### Scoring
- Round winner scores 0 for that round
- All other players score the sum of their remaining hand values:
  - 6, 7, 8, 9 = 0 pts; 10, Q, K = 10 pts; J = 20 pts; A = 15 pts; J♠ = 40 pts; K♥ = 50 pts
- If any player reaches ≥150 points the game ends; lowest total score wins
- **TODO:** 145/245 burn rule not yet implemented (holding exactly 145 pts resets to 245; TODO in scoring)

---

## Project structure

```
Games/
├── main.py                          # FastAPI entry point, lifespan (Redis + DB init)
├── pyproject.toml                   # uv dependencies + pytest config
├── .env                             # (not committed) DATABASE_URL, REDIS_URL, SECRET_KEY
│
├── app/
│   ├── core/
│   │   └── config.py                # pydantic-settings: database_url, redis_url, secret_key, allowed_origins
│   │
│   ├── domain/
│   │   ├── bridge/
│   │   │   ├── entities/
│   │   │   │   ├── card.py          # Card hierarchy, CardRank/CardSuit enums, CARD_REGISTRY, restore_from_data()
│   │   │   │   ├── deck.py          # Deck (draw_pile, discard_pile, shuffle, draw_card, discard_card)
│   │   │   │   ├── effects.py       # DrawEffect, SkipEffect, CoverEffect, ChangeSuitEffect (Pydantic models)
│   │   │   │   ├── player.py        # Player (id, name, hand, add_cards, remove_cards)
│   │   │   │   └── __init__.py      # Re-exports all entities + effects
│   │   │   ├── exceptions.py        # All domain exceptions
│   │   │   ├── game.py              # Game (main orchestrator, play_cards, draw_card, _apply_effects, scoring)
│   │   │   ├── player_manager.py    # PlayerManager (turn order, skips, advance_move)
│   │   │   └── rules.py             # can_play_cards(), is_bridge_call(), score_hand()
│   │   └── room/
│   │       └── room.py              # Room (id, name, host_id, player_ids, game, computed status)
│   │
│   ├── infrastructure/
│   │   ├── db/
│   │   │   ├── models.py            # SQLAlchemy User model (FastAPI Users)
│   │   │   └── session.py           # async engine, session maker, get_async_session, create_db_tables
│   │   ├── redis/
│   │   │   └── client.py            # ConnectionPool, create_pool(), close_pool(), get_redis()
│   │   ├── repositories/
│   │   │   └── room_repo.py         # Async Redis-backed RoomRepository + distributed lock()
│   │   └── ws_manager.py            # WebSocketManager (local WS fan-out via Redis Pub/Sub)
│   │
│   ├── api/
│   │   ├── users.py                 # FastAPI Users setup (UserManager, auth_backend, fastapi_users)
│   │   ├── deps.py                  # get_redis, get_room_repo, get_room (async), current_active_user
│   │   └── routers/
│   │       ├── auth.py              # Mounts FastAPI Users routers under /auth
│   │       └── rooms.py             # Rooms CRUD: create, list, get, join, leave, start, delete
│   │
│   └── schemas/
│       ├── auth.py                  # UserRead, UserCreate, UserUpdate
│       └── room.py                  # RoomCreate, RoomResponse
│
└── tests/
    └── domain/
        └── bridge/
            ├── test_deck.py          # 8 tests
            ├── test_player.py        # 4 tests
            ├── test_player_manager.py# 20 tests
            ├── test_rules.py         # 17 tests
            └── test_game.py          # 27 tests (effects, cover, bridge call, scoring, round end)
```

---

## Key design decisions

### Why Pydantic BaseModel everywhere in the domain
Every domain object (`Card`, `Deck`, `Player`, `PlayerManager`, `Game`, `Room`) extends `pydantic.BaseModel`.
This was intentional from the start: `model_dump_json()` / `model_validate_json()` enables zero-cost Redis round-trip serialisation. No custom serialisers needed.

### Card polymorphism
`card.py` has a `CARD_REGISTRY: dict[tuple[CardRank, CardSuit | None], type[Card]]` that maps `(rank, suit)` → concrete subclass.
`restore_from_data(pile_data)` uses the registry to reconstruct the correct subclass (e.g. `SevenCard`, `KingHeartsCard`) when deserialising from Redis JSON. Specific suit match beats rank-only match.

### Effect immediacy
All effects (`DrawEffect`, `SkipEffect`, `CoverEffect`, `ChangeSuitEffect`) are applied **immediately** inside `Game._apply_effects()` to `next_player_id` **before** `advance_move()` is called. This is the correct game rule.

### Cover mechanic (6)
`Game.cover_active: bool` flag. When `True`:
- `can_play_cards()` only allows rank=SIX
- `draw_card()` does **not** advance the turn — the player keeps drawing until they have a 6 to cover

### Redis architecture (multi-worker)
```
Worker 1 (uvicorn)       Worker 2 (uvicorn)
  Player A, B (WS)  ←→    Player C, D (WS)
         ↕                        ↕
              Redis:
    room:{id}        → JSON (Pydantic Room state)
    rooms:all        → Set of all room IDs
    lock:room:{id}   → Distributed mutex (10s timeout)
    channel:room:{id}→ Pub/Sub event channel
```

**Flow for every mutating operation (join/leave/start/play/draw):**
1. Acquire `lock:room:{id}` (blocking, 5s wait)
2. Load `Room.model_validate_json(redis.get(...))`
3. Apply domain logic
4. `redis.set(room:{id}, room.model_dump_json())`
5. `redis.publish(channel:room:{id}, event_json)`
6. Release lock
7. Each worker's `WebSocketManager` has a background asyncio task subscribed to `channel:room:{id}` and fans out to local WS clients

**`RoomRepository.lock(room_id)`** is an async context manager using `redis.asyncio.Redis.lock()`.

### Authentication
FastAPI Users 15.0.5 with UUID user IDs and JWT bearer token.
- Login: `POST /auth/jwt/login` → returns `access_token`
- Register: `POST /auth/register`
- All rooms endpoints require `Authorization: Bearer <token>`

---

## Redis key schema
| Key | Type | Content |
|---|---|---|
| `room:{id}` | String | `Room.model_dump_json()` |
| `rooms:all` | Set | All room IDs |
| `lock:room:{id}` | String (lock) | Distributed mutex |
| `channel:room:{id}` | Pub/Sub | JSON event payloads |

---

## REST API (implemented)

| Method | Path | Description |
|---|---|---|
| POST | `/auth/register` | Register user |
| POST | `/auth/jwt/login` | Login → JWT token |
| POST | `/rooms` | Create room |
| GET | `/rooms` | List all rooms |
| GET | `/rooms/{id}` | Get room detail |
| POST | `/rooms/{id}/join` | Join room |
| POST | `/rooms/{id}/leave` | Leave room |
| POST | `/rooms/{id}/start` | Start game (host only) |
| DELETE | `/rooms/{id}` | Delete room (host only) |
| GET | `/health` | Health check |

---

## Environment variables (.env file)

```
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/bridge
REDIS_URL=redis://localhost:6379/0
SECRET_KEY=change-me-to-a-long-random-secret
ALLOWED_ORIGINS=["http://localhost:3000","http://localhost:5173"]
```

---

## Running the project

```bash
uv run uvicorn main:app --reload          # dev
uv run pytest                             # tests (81 passing)
```

Requires PostgreSQL and Redis running locally (or via Docker).
Tables are auto-created on startup via `create_db_tables()` (SQLAlchemy `create_all`).
No Alembic migrations yet — `create_all` is fine for development.

---

## What's done ✅

1. Full domain layer — entities, effects, player manager, rules, game orchestrator
2. 81 passing unit tests (domain only, no infra deps)
3. FastAPI Users auth (JWT, PostgreSQL, UUID users)
4. Rooms REST API (create/list/get/join/leave/start/delete)
5. Redis infrastructure layer:
   - Async Redis-backed `RoomRepository` with distributed locking
   - `WebSocketManager` with Redis Pub/Sub fan-out for cross-worker events
   - Connection pool lifecycle in FastAPI lifespan

## What's left 🔜

### Next: WebSocket game endpoints
Add `/ws/rooms/{room_id}` WebSocket endpoint. Suggested message protocol:

```json
// client → server
{"action": "play_cards", "cards": [{"rank": "7", "suit": "hearts"}]}
{"action": "draw_card"}
{"action": "play_cards", "cards": [...], "declared_suit": "clubs"}  // for Jack

// server → all clients in room (via ws_manager.broadcast)
{"event": "game_state", "room": {...}}
{"event": "player_played", "player_id": "...", "cards": [...]}
{"event": "player_drew", "player_id": "...", "count": 1}
{"event": "round_ended", "winner_id": "...", "scores": {...}}
{"event": "game_over", "winner_id": "...", "scores": {...}}
```

The WS handler should:
1. Authenticate via token query param (`?token=<jwt>`)
2. Call `ws_manager.connect(room_id, ws, redis)` on connect
3. Listen for incoming messages in a loop
4. Acquire `repo.lock(room_id)`, load room, call `game.play_cards()` or `game.draw_card()`, save, publish event, release lock
5. Call `ws_manager.disconnect(room_id, ws)` on disconnect/error

### After WebSocket
- Docker + Nginx config (multi-worker uvicorn behind Nginx reverse proxy)
- Alembic migrations (replace `create_all` with proper migrations)
- 145/245 burn rule in `game._end_round()`
- Frontend (React or Vue)

---

## Known gotchas / non-obvious things

- **`advance_move()` skip logic:** The loop in `PlayerManager.advance_move()` skips players by consuming their skip counter one at a time per pass. Do NOT add a second condition to check the original player — it caused double-decrement bugs previously.
- **`remove_player()` index adjustment:** Adjust `current_player_index` **before** the bounds check, not after. The order matters: if removing a player before the current index, decrement first, then clamp to 0 if out of bounds.
- **`top_card` deserialisation:** When loading a `Room` from Redis JSON, `top_card` deserialises as base `Card` (not the subclass), because `Game` declares it as `Card | None`. This is fine — `top_card` is only used for `.rank` and `.suit` comparison in `can_play_cards()`. The subclasses live in the deck piles (restored via `restore_from_data`).
- **Pydantic `frozen=True` on `Card.value`:** The `value` field uses `default_factory` with a lambda that reads `data["rank"]`. This means value is computed once at construction and then frozen.
- **`CardSuit.CLUBS = "clubs"` (not "club"):** Was a bug in an earlier version, already fixed.
- **`rooms:all` set + individual keys:** `RoomRepository.all()` fetches all IDs from the set then pipelines GETs. If a `room:{id}` key expires but the ID is still in the set, `all()` silently skips `None` results. This is intentional — no phantom rooms.
- **Distributed lock scope:** Only `join`, `leave`, and `start` re-read inside the lock (to avoid TOCTOU). `create_room` and `delete_room` don't need it because they operate on a new/existing-exclusively-owned resource.
