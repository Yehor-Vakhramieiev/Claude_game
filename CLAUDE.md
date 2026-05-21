# CLAUDE.md — Bridge Card Game Project

## Project overview

Portfolio project for a junior Python developer job search (London).
Multiplayer card game **Bridge** (similar to 101 / Mau-Mau rules), implemented as a FastAPI backend with WebSocket gameplay, JWT auth, PostgreSQL, and Redis for multi-worker state sharing.

**Stack:**
- Python 3.14, FastAPI, Pydantic v2, SQLAlchemy 2 (async), asyncpg
- FastAPI Users 15.0.5 (JWT bearer auth)
- Redis with hiredis (state storage + Pub/Sub)
- fakeredis, httpx (testing only)
- pytest (148 tests, all passing)
- uv (package manager)
- Planned: Docker + Nginx, React/Vue frontend

---

## Current status

**Everything is implemented and tested. 148/148 tests pass.**

```
tests/domain/bridge/       — 76 tests  (deck, player, player_manager, rules, game)
tests/infrastructure/      — 32 tests  (room_repo: 18, ws_manager: 14)
tests/api/test_rooms.py    — 20 tests  (CRUD, join, leave, start, delete)
tests/api/test_game_ws.py  — 15 tests  (auth guards, game actions, broadcast)
tests/api/test_game_ws.py::test_ws_receives_player_joined_event — last added
```

Run: `uv run pytest` (takes ~1.3 s)

---

## Game rules

- **Deck:** 36 cards (6–A in four suits)
- **Players:** 2–5
- **Deal:** 5 cards each; one card flipped face-up as the starting top card
- **Objective:** empty your hand first; losers accumulate points from remaining cards; first player to reach **150 points loses** (lowest score wins overall)
- **Turn:** play one or more cards of the **same rank** that match the **top card's rank or suit** (or the declared suit if a Jack was played)

### Card effects (applied **immediately** before turn passes)
| Card | Effect |
|---|---|
| 6 | **Cover** — next player must play a 6 or keep drawing (`cover_active=True`) |
| 7 | Next player **draws 2 cards + skips** their turn |
| 8 | Next player **draws 1 card** (turn still passes) |
| J (non-♠) | Player **declares a new suit**; next player must match that suit |
| J♠ | Same as J but worth **40 points** |
| K♥ | Next player **draws 5 cards** (worth 50 points) |
| A | Next player **skips** their turn |

### Special win condition
- **Bridge call:** playing 4 cards of the same rank in one turn ends the round immediately

### Scoring
- Round winner scores 0; others score sum of remaining hand values
- 6, 7, 8, 9 = 0 pts; 10, Q, K = 10 pts; J = 20 pts; A = 15 pts; J♠ = 40 pts; K♥ = 50 pts
- If any player reaches ≥150 points the game ends; lowest total score wins
- **TODO:** 145/245 burn rule not yet implemented

---

## Project structure (all files)

```
Games/
├── main.py
├── pyproject.toml
├── .env                             # not committed
│
├── app/
│   ├── core/config.py               # pydantic-settings: database_url, redis_url, secret_key, allowed_origins
│   │
│   ├── domain/bridge/
│   │   ├── entities/
│   │   │   ├── card.py              # Card, CardRank/CardSuit enums, CARD_REGISTRY, restore_from_data()
│   │   │   ├── deck.py              # Deck: draw_pile, discard_pile, shuffle, draw_card, discard_card
│   │   │   ├── effects.py           # DrawEffect, SkipEffect, CoverEffect, ChangeSuitEffect
│   │   │   ├── player.py            # Player: id, name, hand, add_cards, remove_cards
│   │   │   └── __init__.py          # re-exports all entities + effects
│   │   ├── exceptions.py            # all domain exceptions
│   │   ├── game.py                  # Game: play_cards, draw_card, _apply_effects, scoring, GameStatus
│   │   ├── player_manager.py        # PlayerManager: turn order, skips, advance_move
│   │   └── rules.py                 # can_play_cards(), is_bridge_call(), score_hand()
│   │
│   ├── domain/room/room.py          # Room: id, name, host_id, player_ids, game, computed status
│   │
│   ├── infrastructure/
│   │   ├── db/models.py             # SQLAlchemy User model (FastAPI Users)
│   │   ├── db/session.py            # async engine, get_async_session, create_db_tables
│   │   ├── redis/client.py          # create_pool(), close_pool(), get_redis() → Redis
│   │   ├── repositories/room_repo.py  # RoomRepository + distributed lock
│   │   └── ws_manager.py            # WebSocketManager + module-level ws_manager singleton
│   │
│   ├── api/
│   │   ├── users.py                 # UserManager, auth_backend, fastapi_users, get_jwt_strategy (PUBLIC)
│   │   ├── deps.py                  # get_redis, get_room_repo, get_room, current_active_user, get_ws_user
│   │   └── routers/
│   │       ├── auth.py              # FastAPI Users routers under /auth
│   │       ├── rooms.py             # CRUD + join/leave/start/delete, broadcasts lobby events
│   │       └── game_ws.py           # WebSocket /ws/rooms/{room_id}
│   │
│   └── schemas/
│       ├── auth.py                  # UserRead, UserCreate, UserUpdate
│       ├── room.py                  # RoomCreate, RoomResponse
│       └── ws.py                    # PlayCardsMessage, DrawCardMessage, incoming_message_adapter
│
└── tests/
    ├── domain/bridge/
    │   ├── test_deck.py             # 8 tests
    │   ├── test_player.py           # 4 tests
    │   ├── test_player_manager.py   # 20 tests
    │   ├── test_rules.py            # 17 tests
    │   └── test_game.py             # 27 tests
    ├── infrastructure/
    │   ├── test_room_repo.py        # 18 tests
    │   └── test_ws_manager.py       # 14 tests
    └── api/
        ├── conftest.py              # fixtures: fake_redis, client, reset_ws_manager, switch_user
        ├── test_rooms.py            # 20 tests
        └── test_game_ws.py          # 15 tests
```

---

## Key files — full details

### `main.py`
```python
@asynccontextmanager
async def lifespan(app):
    create_pool()
    await create_db_tables()
    yield
    await close_pool()

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(rooms.router, prefix="/rooms", tags=["rooms"])
app.include_router(game_ws.router, prefix="/ws/rooms", tags=["game-ws"])

@app.get("/health")
async def health(): return {"status": "ok"}
```

### `app/infrastructure/redis/client.py`
```python
_pool: ConnectionPool | None = None

def create_pool() -> ConnectionPool:
    global _pool
    _pool = ConnectionPool.from_url(settings.redis_url, decode_responses=True, max_connections=20)
    return _pool

async def close_pool() -> None:
    if _pool: await _pool.aclose()

def get_redis() -> Redis:
    if _pool is None: raise RuntimeError("Redis pool not initialised")
    return Redis(connection_pool=_pool)
```

### `app/infrastructure/repositories/room_repo.py`
Keys: `room:{id}` (JSON), `rooms:all` (Set), `lock:room:{id}` (mutex token)

**CRITICAL — custom lock (not redis.lock()):**
```python
# redis-py's Lock uses EVALSHA (Lua) — fakeredis doesn't support it without lupa
# Custom SET NX EX + token-based release instead:
async with repo.lock(room_id):
    ...
```
Lock internals:
```python
_LOCK_TIMEOUT = 10   # auto-expire seconds
_LOCK_WAIT = 5.0     # max wait
_LOCK_POLL = 0.05    # polling interval

token = str(uuid.uuid4())
acquired = await self._redis.set(key, token, nx=True, ex=_LOCK_TIMEOUT)
# Release only if we still own it:
current = await self._redis.get(key)
if current == token:
    await self._redis.delete(key)
```
`all()` uses a pipeline to batch-GET all room JSONs; silently skips `None` (expired keys).

### `app/infrastructure/ws_manager.py`
```python
class WebSocketManager:
    _connections: dict[str, set[WebSocket]]   # room_id → local WS set
    _listeners: dict[str, asyncio.Task]        # room_id → Pub/Sub task

async def connect(room_id, ws, redis):
    await ws.accept()
    _connections[room_id].add(ws)
    if room_id not in _listeners:
        _listeners[room_id] = asyncio.create_task(_listen(room_id, redis))

async def disconnect(room_id, ws):
    _connections[room_id].discard(ws)
    if not _connections[room_id]:
        del _connections[room_id]
        task = _listeners.pop(room_id, None)
        if task: task.cancel()

async def broadcast(room_id, redis, payload: dict):
    await redis.publish(f"channel:room:{room_id}", json.dumps(payload))

async def _listen(room_id, redis):
    pubsub = redis.pubsub()
    await pubsub.subscribe(f"channel:room:{room_id}")
    async for message in pubsub.listen():
        if message["type"] == "message":
            await _fan_out(room_id, message["data"])
    # CancelledError caught silently; pubsub unsubscribed in finally

async def _fan_out(room_id, data: str):
    # sends data to all local WS; removes dead connections on exception

ws_manager = WebSocketManager()   # module-level singleton
```

### `app/schemas/ws.py`
**CRITICAL — must use TypeAdapter, not .model_validate_json():**
```python
class PlayCardsMessage(BaseModel):
    action: Literal["play_cards"]
    cards: list[CardData] = Field(min_length=1)
    declared_suit: CardSuit | None = None

class DrawCardMessage(BaseModel):
    action: Literal["draw_card"]

_IncomingUnion = Annotated[PlayCardsMessage | DrawCardMessage, Field(discriminator="action")]
incoming_message_adapter = TypeAdapter(_IncomingUnion)

# Usage in game_ws.py:
msg = incoming_message_adapter.validate_json(raw)
```
`Annotated[...]` type aliases have no `.model_validate_json()` — calling it raises `AttributeError` silently swallowed by `except Exception`.

### `app/api/deps.py`
```python
async def get_ws_user(
    token: str = Query(...),
    session: AsyncSession = Depends(get_async_session),
) -> User | None:
    # JWT via ?token= query param (browsers can't send custom WS headers)
    # Returns None on any error — never raises
    # This signature is essential for app.dependency_overrides in tests
    strategy = get_jwt_strategy()
    user_db = SQLAlchemyUserDatabase(session, User)
    user_manager = UserManager(user_db)
    try:
        user = await strategy.read_token(token, user_manager)
    except Exception:
        return None
    if user is None or not user.is_active:
        return None
    return user
```

### `app/api/users.py`
`get_jwt_strategy` is **public** (no underscore). It's called directly from `deps.get_ws_user`.
Do not rename it back to `_get_jwt_strategy`.

### `app/api/routers/game_ws.py`
Pattern for auth rejection (MUST call accept before close):
```python
if ws_user is None:
    await ws.accept()
    await ws.close(code=4001)
    return
```
Close codes: `4001` unauthenticated, `4003` not a room member, `4004` room not found.

On connect, sends `{"event": "room_snapshot", "room": {...}}` immediately.

`_handle_play` and `_handle_draw` both:
1. Acquire `repo.lock(room_id)` (async context manager)
2. Re-read room from Redis inside lock
3. Apply domain logic
4. `await repo.save(room)`
5. Release lock, then broadcast

### `app/api/routers/rooms.py`
Broadcasts lobby events via `ws_manager.broadcast(room.id, repo.redis, {...})`:
- `join` → `{"event": "player_joined", "player_id": ..., "room": ...}`
- `leave` → `{"event": "player_left", "player_id": ..., "room": ...}`
- `start` → `{"event": "game_started", "room": ...}`

`join`, `leave`, `start` re-read inside lock to avoid TOCTOU.
`create` and `delete` don't need a lock.

---

## REST API

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/auth/register` | No | Register user |
| POST | `/auth/jwt/login` | No | Login → `access_token` |
| POST | `/rooms` | Bearer | Create room |
| GET | `/rooms` | Bearer | List all rooms |
| GET | `/rooms/{id}` | Bearer | Get room detail |
| POST | `/rooms/{id}/join` | Bearer | Join room |
| POST | `/rooms/{id}/leave` | Bearer | Leave room |
| POST | `/rooms/{id}/start` | Bearer | Start game (host only) |
| DELETE | `/rooms/{id}` | Bearer | Delete room (host only) |
| WS | `/ws/rooms/{id}?token=` | Query param | Game WebSocket |
| GET | `/health` | No | Health check |

---

## WebSocket protocol

```json
// client → server
{"action": "play_cards", "cards": [{"rank": "7", "suit": "hearts"}]}
{"action": "play_cards", "cards": [...], "declared_suit": "clubs"}
{"action": "draw_card"}

// server → all clients in room (broadcast)
{"event": "room_snapshot", "room": {...}}
{"event": "player_played", "player_id": "...", "cards": [...], "declared_suit": null, "room": {...}}
{"event": "player_drew",   "player_id": "...", "count": 1, "room": {...}}
{"event": "round_ended",   "winner_id": "...", "scores": {...}, "room": {...}}
{"event": "game_over",     "scores": {...}, "room": {...}}
{"event": "player_joined", "player_id": "...", "room": {...}}
{"event": "player_left",   "player_id": "...", "room": {...}}
{"event": "game_started",  "room": {...}}
{"event": "error",         "detail": "..."}
```

---

## Redis architecture

```
Worker 1 (uvicorn)       Worker 2 (uvicorn)
  Player A, B (WS)  ←→    Player C, D (WS)
         ↕                        ↕
              Redis:
    room:{id}         → JSON (Room.model_dump_json())
    rooms:all         → Set of all room IDs
    lock:room:{id}    → Custom mutex token (SET NX EX)
    channel:room:{id} → Pub/Sub event payloads
```

Flow for every mutating operation:
1. Acquire `lock:room:{id}` (blocking, 5s wait, 10s auto-expire)
2. `Room.model_validate_json(await redis.get(...))`
3. Apply domain logic
4. `await redis.set(room:{id}, room.model_dump_json())`
5. `await redis.publish(channel:room:{id}, json.dumps(event))`
6. Release lock (only if token still matches)
7. Each worker's `ws_manager` background task fans out to local WS clients

---

## Test structure

### `tests/api/conftest.py` — fixtures
```python
USER1 = _make_user(1)   # id = 00000000-0000-0000-0000-000000000001
USER2 = _make_user(2)   # etc.
USER3 = _make_user(3)
USER4 = _make_user(4)
USER1_ID, USER2_ID, USER3_ID, USER4_ID = str(USER1.id), ...

@pytest.fixture
def fake_redis():
    return fakeredis.FakeAsyncRedis(decode_responses=True)

@pytest.fixture(autouse=True)
def reset_ws_manager():
    ws_manager._connections.clear()
    ws_manager._listeners.clear()
    yield
    ws_manager._connections.clear()
    ws_manager._listeners.clear()

@pytest.fixture
def client(fake_redis, monkeypatch):
    monkeypatch.setattr("main.create_db_tables", AsyncMock())  # no real PostgreSQL
    app.dependency_overrides[current_active_user] = lambda: USER1
    app.dependency_overrides[get_ws_user] = lambda: USER1
    app.dependency_overrides[get_redis] = lambda: fake_redis
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()

def switch_user(user):
    app.dependency_overrides[current_active_user] = lambda u=user: u
    app.dependency_overrides[get_ws_user] = lambda u=user: u
```

### Critical test patterns

**WS close code tests** — `WebSocketDisconnect` raised only inside the context on `receive_text()`:
```python
with client.websocket_connect(ws_url(room_id)) as ws:
    with pytest.raises(WebSocketDisconnect) as exc_info:
        ws.receive_text()
assert exc_info.value.code == 4001
```

**WS broadcast tests** — `asyncio.sleep(0)` required after connect to let listener subscribe:
```python
await manager.connect("r1", ws, redis)
await asyncio.sleep(0)            # REQUIRED: let Pub/Sub listener subscribe
await manager.broadcast("r1", redis, payload)
await asyncio.sleep(0.05)         # let fan_out deliver
ws.send_text.assert_called_once()
```

**Infrastructure tests** — all use `asyncio.run()` + inner `async def _()`:
```python
def test_something():
    async def _():
        ...
    asyncio.run(_())
```

**Avoiding "not your turn" errors in API tests** — always detect who goes first:
```python
def get_first_player_id(client, room_id):
    with client.websocket_connect(f"/ws/rooms/{room_id}") as ws:
        snap = ws.receive_json()
    pm = snap["room"]["game"]["player_manager"]
    return pm["turn_order"][pm["current_player_index"]]

# Then switch to that user before taking an action
first_id = get_first_player_id(client, room_id)
switch_user(USER1 if first_id == USER1_ID else USER2)
```

---

## Environment variables

```
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/bridge
REDIS_URL=redis://localhost:6379/0
SECRET_KEY=change-me-to-a-long-random-secret
ALLOWED_ORIGINS=["http://localhost:3000","http://localhost:5173"]
```

---

## Running the project

```bash
uv run uvicorn main:app --reload          # dev server
uv run pytest                             # 148 tests, ~1.3s
uv run pytest tests/domain/               # domain only (no infra)
uv run pytest tests/infrastructure/       # infra only (fakeredis)
uv run pytest tests/api/                  # API + WS (fakeredis, no PostgreSQL)
```

Requires PostgreSQL and Redis locally (or via Docker).
Tables auto-created on startup via `create_db_tables()` (`create_all`). No Alembic yet.

---

## What's done ✅

1. Full domain layer: entities, effects, player_manager, rules, game orchestrator — 76 tests
2. FastAPI Users auth: JWT, PostgreSQL, UUID user IDs
3. Rooms REST API: create/list/get/join/leave/start/delete — 20 tests
4. Redis infrastructure:
   - `RoomRepository`: async CRUD + custom distributed lock — 18 tests
   - `WebSocketManager`: local WS fan-out via Redis Pub/Sub — 14 tests
   - Connection pool lifecycle in FastAPI lifespan
5. WebSocket game endpoint `/ws/rooms/{room_id}`:
   - Auth via `?token=` query param
   - `play_cards` and `draw_card` actions with full game logic
   - Broadcasts: `player_played`, `player_drew`, `round_ended`, `game_over` — 15 tests
6. Lobby WS events: `player_joined`, `player_left`, `game_started` (from rooms.py)

## What's left 🔜

- Docker + Nginx config (multi-worker uvicorn behind Nginx)
- Alembic migrations (replace `create_all`)
- 145/245 burn rule in `game._end_round()`
- Frontend (React or Vue)

---

## Known gotchas / non-obvious things

- **Custom lock, not redis.lock():** `redis-py`'s `Lock` uses Lua scripts (`EVALSHA`) — `fakeredis` doesn't support them without `lupa`. The lock in `room_repo.py` uses `SET NX EX` + `GET/DEL` with a UUID token. **Do NOT replace with `redis.lock()`** — it breaks all tests.

- **TypeAdapter for discriminated unions:** `Annotated[Union, Field(discriminator=...)]` aliases have no `.model_validate_json()`. Calling it raises `AttributeError` silently caught by `except Exception` in the WS loop — all messages would return "Invalid message format". Must use `TypeAdapter(...)` and call `.validate_json(raw)`.

- **`ws.accept()` before `ws.close(code)`:** Starlette requires `accept()` before `close()` for the close code to be delivered to the client. Missing `accept()` means the client never sees the code.

- **`get_jwt_strategy` is public:** Called directly from `deps.get_ws_user`. Was previously `_get_jwt_strategy` (private). Do not rename back.

- **`app.dependency_overrides` are per-request:** Changing `get_ws_user` override after a WS connection is established has no effect — the handler already captured `user_id`. Use `switch_user()` **before** opening the WS connection.

- **fakeredis Pub/Sub needs a tick:** After `ws_manager.connect()`, the background listener task must subscribe before any broadcast arrives. Always `await asyncio.sleep(0)` between connect and broadcast in tests.

- **`advance_move()` skip logic:** The loop consumes skip counters one at a time per pass. Do NOT add a second condition to check the original player — caused double-decrement bugs before.

- **`remove_player()` index adjustment:** Adjust `current_player_index` **before** the bounds check, not after. Wrong order caused off-by-one bugs.

- **`top_card` deserialisation:** Loads as base `Card` (not subclass) because `Game` declares it `Card | None`. Fine — `top_card` is only used for `.rank`/`.suit` in `can_play_cards()`. Subclasses live in deck piles, restored via `restore_from_data()`.

- **`rooms:all` + individual keys:** `all()` pipelines GETs; silently skips `None` results (expired keys). Intentional — no phantom rooms.

- **Lock scope:** Only `join`, `leave`, `start` re-read inside lock (TOCTOU prevention). `create` and `delete` don't need it.

- **`reset_ws_manager` autouse fixture:** Clears `ws_manager._connections` and `ws_manager._listeners` before and after every test. Without it, background listener tasks from one test bleed into the next.
