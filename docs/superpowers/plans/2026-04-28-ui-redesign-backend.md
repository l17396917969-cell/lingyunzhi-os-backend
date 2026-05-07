# UI Redesign — Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land the backend half of the chat-driven ingestion redesign — new `/chat/*` endpoints, pre-session snapshot model, SSE streaming, orphan recovery — without touching the MCP-facing surface or the existing UI.

**Architecture:** Wrap the existing ingestion-job pipeline. New `/chat/*` endpoints create a `ChatSession` whose pre-session staging registry is snapshotted into `chat_sessions.pre_session_registry`. Each user turn creates one ingestion job tagged with `chat_session_id`; SSE streams agent tool calls to consumers; Cancel restores the snapshot via `rstore.save`. The MCP tools, `run_agent`, and `run_one_job` are unchanged.

**Tech Stack:** Python 3.12 / FastAPI / SQLAlchemy async / Alembic / Pydantic v2; pytest + pytest-asyncio + httpx ASGITransport for tests.

**Spec:** `docs/superpowers/specs/2026-04-28-onto-platform-ui-redesign-design.md`
**Companion plan (frontend):** `docs/superpowers/plans/2026-04-28-ui-redesign-frontend.md` (depends on this one shipping first)

This plan is independently shippable. When complete, you can drive the entire chat lifecycle via `curl`; the existing UI continues to work unchanged because no UI files are touched in this plan.

---

## Phase Overview

| Phase | Scope | Commits |
|---|---|---|
| 1 | Foundation: settings + Alembic migration | 2 |
| 2 | ChatSession orchestrator: create, get, save, cancel, orphan sweep | 5 |
| 3 | SSE infra + chat HTTP endpoints (sessions/uploads/turns/stream) | 3 |
| 4 | App wiring: register router + orphan sweep on startup + e2e curl test | 2 |

Each phase ends with a passing build + commit. The plan is meant to be executed task-by-task by subagents (Sonnet 4.6 implementer, Opus 4.7 reviewer per phase).

---

## Phase 1 — Backend foundation

### Task 1.1: Add chat-related settings to `Settings`

**Files:**
- Modify: `onto_platform/config.py`
- Test: `tests/unit/test_config_chat.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_config_chat.py
from onto_platform.config import Settings


def test_chat_settings_have_sensible_defaults():
    s = Settings(database_url="postgresql+asyncpg://x", secret_key="x" * 44)
    assert s.chat_session_orphan_after_s == 1800
    assert s.chat_turn_max_wall_clock_s == 1800
    assert s.chat_sse_heartbeat_s == 15
    assert s.chat_max_concurrent_sessions_per_token == 5


def test_chat_settings_can_be_overridden_via_env(monkeypatch):
    monkeypatch.setenv("ONTO_DATABASE_URL", "postgresql+asyncpg://x")
    monkeypatch.setenv("ONTO_SECRET_KEY", "x" * 44)
    monkeypatch.setenv("ONTO_CHAT_SESSION_ORPHAN_AFTER_S", "60")
    monkeypatch.setenv("ONTO_CHAT_SSE_HEARTBEAT_S", "5")
    s = Settings()
    assert s.chat_session_orphan_after_s == 60
    assert s.chat_sse_heartbeat_s == 5
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/unit/test_config_chat.py -v
```
Expected: FAIL — AttributeError or pydantic validation error on missing fields.

- [ ] **Step 3: Add the settings**

Append to `onto_platform/config.py` after `llm_request_timeout_s: int = 120`:

```python
    chat_session_orphan_after_s: int = 1800
    chat_turn_max_wall_clock_s: int = 1800
    chat_sse_heartbeat_s: int = 15
    chat_max_concurrent_sessions_per_token: int = 5
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/unit/test_config_chat.py -v
```
Expected: PASS, both tests.

- [ ] **Step 5: Commit**

```bash
git add onto_platform/config.py tests/unit/test_config_chat.py
git commit -m "feat(config): add chat session settings"
```

---

### Task 1.2: Alembic migration — chat_sessions, chat_messages, ingestion_jobs.chat_session_id

**Files:**
- Create: `migrations/versions/0004_chat_sessions.py`
- Test: `tests/integration/test_migrations.py` (extend if exists, else create)

- [ ] **Step 1: Write the failing test (verifies tables exist after upgrade)**

```python
# tests/integration/test_migrations.py
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

pytestmark = pytest.mark.asyncio


async def test_chat_tables_exist(postgres_url):
    eng = create_async_engine(postgres_url, future=True)
    try:
        async with eng.connect() as c:
            r = await c.execute(text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema='public' AND table_name IN "
                "('chat_sessions','chat_messages')"
            ))
            names = {row[0] for row in r}
            assert names == {"chat_sessions", "chat_messages"}

            r2 = await c.execute(text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name='chat_sessions' "
                "AND column_name IN ('pre_session_registry','pre_session_version','status','last_turn_at')"
            ))
            cols = {row[0] for row in r2}
            assert cols == {"pre_session_registry", "pre_session_version", "status", "last_turn_at"}

            r3 = await c.execute(text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name='ingestion_jobs' AND column_name='chat_session_id'"
            ))
            assert r3.scalar_one() == "chat_session_id"
    finally:
        await eng.dispose()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/integration/test_migrations.py::test_chat_tables_exist -v
```
Expected: FAIL — tables not present.

- [ ] **Step 3: Create the migration**

```python
# migrations/versions/0004_chat_sessions.py
"""chat sessions, messages, and ingestion_jobs.chat_session_id

Revision ID: 0004
Revises: 0003
Create Date: 2026-04-28
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "chat_sessions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("token_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'active'")),
        sa.Column("pre_session_registry", postgresql.JSONB, nullable=False),
        sa.Column("pre_session_version", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("last_turn_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('active','saving','cancelling')",
            name="chat_sessions_status_check",
        ),
    )
    op.create_index(
        "chat_sessions_token_idx", "chat_sessions", ["token_id"], unique=False
    )
    op.create_index(
        "chat_sessions_active_idx",
        "chat_sessions",
        ["status", "last_turn_at"],
        unique=False,
    )

    op.create_table(
        "chat_messages",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "session_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("chat_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("turn_index", sa.Integer(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("content", postgresql.JSONB, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "role IN ('user','assistant','tool_call','tool_result')",
            name="chat_messages_role_check",
        ),
    )
    op.create_index(
        "chat_messages_session_idx", "chat_messages", ["session_id", "id"], unique=False
    )

    op.add_column(
        "ingestion_jobs",
        sa.Column(
            "chat_session_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("chat_sessions.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ingestion_jobs_chat_session_idx",
        "ingestion_jobs",
        ["chat_session_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ingestion_jobs_chat_session_idx", table_name="ingestion_jobs")
    op.drop_column("ingestion_jobs", "chat_session_id")
    op.drop_index("chat_messages_session_idx", table_name="chat_messages")
    op.drop_table("chat_messages")
    op.drop_index("chat_sessions_active_idx", table_name="chat_sessions")
    op.drop_index("chat_sessions_token_idx", table_name="chat_sessions")
    op.drop_table("chat_sessions")
```

- [ ] **Step 4: Apply migration to local test DB and re-run test**

```bash
ONTO_DATABASE_URL=$ONTO_TEST_DATABASE_URL uv run alembic upgrade head
uv run pytest tests/integration/test_migrations.py::test_chat_tables_exist -v
```
Expected: PASS.

- [ ] **Step 5: Verify downgrade works**

```bash
ONTO_DATABASE_URL=$ONTO_TEST_DATABASE_URL uv run alembic downgrade -1
ONTO_DATABASE_URL=$ONTO_TEST_DATABASE_URL uv run alembic upgrade head
```
Expected: both succeed without errors.

- [ ] **Step 6: Commit**

```bash
git add migrations/versions/0004_chat_sessions.py tests/integration/test_migrations.py
git commit -m "feat(db): chat_sessions + chat_messages tables, ingestion_jobs.chat_session_id"
```

---

## Phase 2 — ChatSession orchestrator

The orchestrator captures the pre-session staging snapshot at session creation and rolls back via `rstore.save` on Cancel. It is the smallest possible Python module that exposes session lifecycle to the HTTP layer.

### Task 2.1: Module skeleton + create_session

**Files:**
- Create: `onto_platform/chat/__init__.py` (empty)
- Create: `onto_platform/chat/orchestrator.py`
- Test: `tests/unit/test_chat_orchestrator.py`

- [ ] **Step 1: Write the failing test for create_session**

```python
# tests/unit/test_chat_orchestrator.py
import uuid
import pytest
from cryptography.fernet import Fernet
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from onto_platform.auth import Scope, generate_token
from onto_platform.chat.orchestrator import (
    ChatSessionOrchestrator,
    StaleStagingError,
    SessionNotFoundError,
    TurnInFlightError,
)
from onto_platform.proto_models import OntologyRegistry
from onto_platform.registry.store import Env, RegistryStore
from onto_platform.token_store import insert_token

pytestmark = pytest.mark.asyncio


@pytest.fixture
async def factory(postgres_url, monkeypatch):
    monkeypatch.setenv("ONTO_SECRET_KEY", Fernet.generate_key().decode())
    eng = create_async_engine(postgres_url, future=True)
    f = async_sessionmaker(eng, expire_on_commit=False)
    async with f() as s:
        await s.execute(text("DELETE FROM chat_messages"))
        await s.execute(text("DELETE FROM chat_sessions"))
        await s.execute(text("DELETE FROM api_tokens"))
        await s.execute(
            text(
                "UPDATE registries SET payload = CAST(:p AS jsonb), version = 1 WHERE env = 'staging'"
            ),
            {"p": OntologyRegistry(version="1").model_dump_json()},
        )
        await s.commit()
    yield f
    await eng.dispose()


@pytest.fixture
async def token_id(factory):
    plain = generate_token()
    async with factory() as s:
        tid = await insert_token(s, plain, Scope.editor, "ed", None)
        await s.commit()
    return tid


async def test_create_session_snapshots_staging(factory, token_id):
    orch = ChatSessionOrchestrator(factory, RegistryStore())
    sid = await orch.create_session(token_id=token_id)
    async with factory() as s:
        row = await s.execute(
            text(
                "SELECT status, pre_session_version, pre_session_registry "
                "FROM chat_sessions WHERE id = :i"
            ),
            {"i": str(sid)},
        )
        rec = row.one()
        assert rec.status == "active"
        assert rec.pre_session_version == 1
        assert rec.pre_session_registry["version"] == "1"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/unit/test_chat_orchestrator.py::test_create_session_snapshots_staging -v
```
Expected: FAIL — `ModuleNotFoundError: onto_platform.chat`.

- [ ] **Step 3: Write the minimal orchestrator + exceptions**

```python
# onto_platform/chat/__init__.py
# (empty — placeholder so the package is importable)
```

```python
# onto_platform/chat/orchestrator.py
from __future__ import annotations

import uuid
from typing import Any, Optional
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from onto_platform.registry.store import (
    Env,
    RegistryStore,
    StaleVersionError,
)


class SessionNotFoundError(Exception):
    pass


class TurnInFlightError(Exception):
    pass


class StaleStagingError(Exception):
    """Raised when a Cancel rollback would clobber concurrent staging changes."""


class ChatSessionOrchestrator:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        registry_store: RegistryStore,
    ) -> None:
        self._sf = session_factory
        self._rstore = registry_store
        # In-memory registry of in-flight turns: session_id -> turn_id
        self._running: dict[uuid.UUID, uuid.UUID] = {}

    async def create_session(self, *, token_id: uuid.UUID) -> uuid.UUID:
        async with self._sf() as s:
            snap = await self._rstore.load(s, Env.staging)
            row = await s.execute(
                text(
                    "INSERT INTO chat_sessions "
                    "(token_id, status, pre_session_registry, pre_session_version) "
                    "VALUES (:t, 'active', CAST(:p AS jsonb), :v) "
                    "RETURNING id"
                ),
                {
                    "t": str(token_id),
                    "p": snap.registry.model_dump_json(),
                    "v": snap.version,
                },
            )
            sid = row.scalar_one()
            await s.commit()
            return uuid.UUID(str(sid))
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/unit/test_chat_orchestrator.py::test_create_session_snapshots_staging -v
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add onto_platform/chat/__init__.py onto_platform/chat/orchestrator.py tests/unit/test_chat_orchestrator.py
git commit -m "feat(chat): orchestrator skeleton + create_session captures pre-session snapshot"
```

---

### Task 2.2: get_session, hydration of messages list

**Files:**
- Modify: `onto_platform/chat/orchestrator.py`
- Modify: `tests/unit/test_chat_orchestrator.py`

- [ ] **Step 1: Add the failing test**

Append to `tests/unit/test_chat_orchestrator.py`:

```python
async def test_get_session_returns_status_and_messages(factory, token_id):
    orch = ChatSessionOrchestrator(factory, RegistryStore())
    sid = await orch.create_session(token_id=token_id)
    # seed two messages
    async with factory() as s:
        await s.execute(
            text(
                "INSERT INTO chat_messages (session_id, turn_index, role, content) "
                "VALUES (:s, 0, 'user', CAST(:c AS jsonb))"
            ),
            {"s": str(sid), "c": '{"text":"hello","upload_ids":[]}'},
        )
        await s.execute(
            text(
                "INSERT INTO chat_messages (session_id, turn_index, role, content) "
                "VALUES (:s, 0, 'assistant', CAST(:c AS jsonb))"
            ),
            {"s": str(sid), "c": '{"text":"hi"}'},
        )
        await s.commit()
    info = await orch.get_session(sid)
    assert info.status == "active"
    assert len(info.messages) == 2
    assert info.messages[0]["role"] == "user"
    assert info.messages[1]["role"] == "assistant"


async def test_get_session_unknown_id_raises(factory):
    orch = ChatSessionOrchestrator(factory, RegistryStore())
    with pytest.raises(SessionNotFoundError):
        await orch.get_session(uuid.uuid4())
```

- [ ] **Step 2: Run tests**

```bash
uv run pytest tests/unit/test_chat_orchestrator.py -v
```
Expected: 1 PASS (existing) + 2 FAIL (new — `get_session` not defined).

- [ ] **Step 3: Implement `get_session` + `SessionInfo`**

Append to `onto_platform/chat/orchestrator.py`:

```python
from dataclasses import dataclass, field


@dataclass
class SessionInfo:
    id: uuid.UUID
    status: str
    pre_session_version: int
    messages: list[dict[str, Any]] = field(default_factory=list)


    async def get_session(self, session_id: uuid.UUID) -> SessionInfo:
        async with self._sf() as s:
            row = await s.execute(
                text(
                    "SELECT status, pre_session_version FROM chat_sessions WHERE id = :i"
                ),
                {"i": str(session_id)},
            )
            rec = row.one_or_none()
            if rec is None:
                raise SessionNotFoundError(str(session_id))
            msgs = await s.execute(
                text(
                    "SELECT turn_index, role, content, created_at "
                    "FROM chat_messages WHERE session_id = :i ORDER BY id ASC"
                ),
                {"i": str(session_id)},
            )
            messages = [
                {
                    "turn_index": m.turn_index,
                    "role": m.role,
                    "content": m.content,
                    "created_at": m.created_at.isoformat() if m.created_at else None,
                }
                for m in msgs
            ]
            return SessionInfo(
                id=session_id,
                status=rec.status,
                pre_session_version=rec.pre_session_version,
                messages=messages,
            )
```

Note: the `async def get_session` belongs as a method on `ChatSessionOrchestrator`. Move it inside the class body (correct indentation). The `SessionInfo` dataclass goes at module top, after the imports.

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/unit/test_chat_orchestrator.py -v
```
Expected: 3 PASS.

- [ ] **Step 5: Commit**

```bash
git add onto_platform/chat/orchestrator.py tests/unit/test_chat_orchestrator.py
git commit -m "feat(chat): get_session hydration"
```

---

### Task 2.3: save_session — drops session row + cascades messages

**Files:**
- Modify: `onto_platform/chat/orchestrator.py`
- Modify: `tests/unit/test_chat_orchestrator.py`

- [ ] **Step 1: Failing test**

Append:

```python
async def test_save_session_deletes_session_and_messages(factory, token_id):
    orch = ChatSessionOrchestrator(factory, RegistryStore())
    sid = await orch.create_session(token_id=token_id)
    async with factory() as s:
        await s.execute(
            text(
                "INSERT INTO chat_messages (session_id, turn_index, role, content) "
                "VALUES (:s, 0, 'user', CAST(:c AS jsonb))"
            ),
            {"s": str(sid), "c": '{"text":"hi","upload_ids":[]}'},
        )
        await s.commit()
    await orch.save_session(sid)
    async with factory() as s:
        r = await s.execute(text("SELECT count(*) FROM chat_sessions WHERE id = :i"), {"i": str(sid)})
        assert r.scalar_one() == 0
        r2 = await s.execute(text("SELECT count(*) FROM chat_messages WHERE session_id = :i"), {"i": str(sid)})
        assert r2.scalar_one() == 0


async def test_save_session_with_in_flight_turn_raises(factory, token_id):
    orch = ChatSessionOrchestrator(factory, RegistryStore())
    sid = await orch.create_session(token_id=token_id)
    orch._running[sid] = uuid.uuid4()
    with pytest.raises(TurnInFlightError):
        await orch.save_session(sid)


async def test_save_session_unknown_raises(factory):
    orch = ChatSessionOrchestrator(factory, RegistryStore())
    with pytest.raises(SessionNotFoundError):
        await orch.save_session(uuid.uuid4())
```

- [ ] **Step 2: Run tests**

```bash
uv run pytest tests/unit/test_chat_orchestrator.py -v
```
Expected: 5 PASS (3 existing) + 3 FAIL.

- [ ] **Step 3: Implement save_session**

Add to `ChatSessionOrchestrator`:

```python
    async def save_session(self, session_id: uuid.UUID) -> None:
        if session_id in self._running:
            raise TurnInFlightError(str(session_id))
        async with self._sf() as s:
            r = await s.execute(
                text(
                    "UPDATE chat_sessions SET status='saving' WHERE id = :i RETURNING id"
                ),
                {"i": str(session_id)},
            )
            if r.scalar_one_or_none() is None:
                raise SessionNotFoundError(str(session_id))
            await s.execute(
                text("DELETE FROM chat_sessions WHERE id = :i"),
                {"i": str(session_id)},
            )
            await s.commit()
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/unit/test_chat_orchestrator.py -v
```
Expected: 6 PASS.

- [ ] **Step 5: Commit**

```bash
git add onto_platform/chat/orchestrator.py tests/unit/test_chat_orchestrator.py
git commit -m "feat(chat): save_session cascade-deletes session"
```

---

### Task 2.4: cancel_session — restores pre-session registry

**Files:**
- Modify: `onto_platform/chat/orchestrator.py`
- Modify: `tests/unit/test_chat_orchestrator.py`

- [ ] **Step 1: Failing test**

Append:

```python
from onto_platform.proto_models import OntologyRegistry, ObjectTypeDefinition


async def test_cancel_restores_pre_session_registry(factory, token_id):
    orch = ChatSessionOrchestrator(factory, RegistryStore())
    sid = await orch.create_session(token_id=token_id)

    # Simulate one turn: write a new staging version with an extra object type
    rs = RegistryStore()
    async with factory() as s:
        snap = await rs.load(s, Env.staging)
        new = OntologyRegistry(
            version=str(int(snap.registry.version) + 1),
            object_types={
                "ri.obj.test-cancel": ObjectTypeDefinition(
                    rid="ri.obj.test-cancel", api_name="x"
                )
            },
        )
        await rs.save(
            s,
            Env.staging,
            new,
            expected_version=snap.version,
            token_label="test",
        )
        await s.commit()

    # Cancel the session — should roll back to pre-session
    await orch.cancel_session(sid)

    async with factory() as s:
        snap_after = await rs.load(s, Env.staging)
        # Pre-session had no object_types
        assert "ri.obj.test-cancel" not in snap_after.registry.object_types

    async with factory() as s:
        r = await s.execute(text("SELECT count(*) FROM chat_sessions WHERE id = :i"), {"i": str(sid)})
        assert r.scalar_one() == 0


async def test_cancel_with_in_flight_turn_raises(factory, token_id):
    orch = ChatSessionOrchestrator(factory, RegistryStore())
    sid = await orch.create_session(token_id=token_id)
    orch._running[sid] = uuid.uuid4()
    with pytest.raises(TurnInFlightError):
        await orch.cancel_session(sid)


async def test_cancel_unknown_raises(factory):
    orch = ChatSessionOrchestrator(factory, RegistryStore())
    with pytest.raises(SessionNotFoundError):
        await orch.cancel_session(uuid.uuid4())
```

- [ ] **Step 2: Run tests**

```bash
uv run pytest tests/unit/test_chat_orchestrator.py -v
```
Expected: 6 PASS + 3 FAIL.

- [ ] **Step 3: Implement cancel_session**

Add to `ChatSessionOrchestrator`:

```python
    async def cancel_session(self, session_id: uuid.UUID) -> None:
        if session_id in self._running:
            raise TurnInFlightError(str(session_id))
        async with self._sf() as s:
            row = await s.execute(
                text(
                    "UPDATE chat_sessions SET status='cancelling' WHERE id = :i "
                    "RETURNING pre_session_registry, pre_session_version"
                ),
                {"i": str(session_id)},
            )
            rec = row.one_or_none()
            if rec is None:
                raise SessionNotFoundError(str(session_id))
            pre_registry = OntologyRegistry.model_validate(rec.pre_session_registry)
            current = await self._rstore.load(s, Env.staging)
            try:
                await self._rstore.save(
                    s,
                    Env.staging,
                    pre_registry,
                    expected_version=current.version,
                    token_label="chat-cancel",
                    commit_message=f"cancel chat session {session_id}",
                )
            except StaleVersionError as e:
                # Leave row in 'cancelling' for operator inspection
                await s.commit()
                raise StaleStagingError(str(e)) from e
            await s.execute(
                text("DELETE FROM chat_sessions WHERE id = :i"),
                {"i": str(session_id)},
            )
            await s.commit()
```

Add the import for `OntologyRegistry` at the top of the file:

```python
from onto_platform.proto_models import OntologyRegistry
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/unit/test_chat_orchestrator.py -v
```
Expected: 9 PASS.

- [ ] **Step 5: Add a StaleStagingError test**

Append:

```python
async def test_cancel_under_stale_staging_raises(factory, token_id):
    orch = ChatSessionOrchestrator(factory, RegistryStore())
    sid = await orch.create_session(token_id=token_id)

    # Concurrent caller bumps staging twice (we'll bump once, then bump again
    # right before the cancel races a second time would-be-rollback)
    rs = RegistryStore()
    async with factory() as s:
        snap = await rs.load(s, Env.staging)
        new = OntologyRegistry(version=str(int(snap.registry.version) + 1))
        await rs.save(s, Env.staging, new, expected_version=snap.version, token_label="t")
        await s.commit()

    # Monkey-patch save to raise StaleVersionError on the rollback attempt
    real_save = rs.save
    calls: list[int] = []

    async def flaky_save(session, env, registry, *, expected_version, token_label, commit_message=None):
        calls.append(expected_version or 0)
        from onto_platform.registry.store import StaleVersionError
        raise StaleVersionError(env, expected_version or 0, (expected_version or 0) + 1)

    orch._rstore.save = flaky_save  # type: ignore[method-assign]
    with pytest.raises(StaleStagingError):
        await orch.cancel_session(sid)
    orch._rstore.save = real_save  # type: ignore[method-assign]
```

- [ ] **Step 6: Run tests**

```bash
uv run pytest tests/unit/test_chat_orchestrator.py -v
```
Expected: 10 PASS.

- [ ] **Step 7: Commit**

```bash
git add onto_platform/chat/orchestrator.py tests/unit/test_chat_orchestrator.py
git commit -m "feat(chat): cancel_session restores pre-session registry"
```

---

### Task 2.5: Orphan recovery sweep

**Files:**
- Create: `onto_platform/chat/recovery.py`
- Test: `tests/unit/test_chat_recovery.py`

- [ ] **Step 1: Failing test**

```python
# tests/unit/test_chat_recovery.py
import uuid
import pytest
from cryptography.fernet import Fernet
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from onto_platform.auth import Scope, generate_token
from onto_platform.chat.orchestrator import ChatSessionOrchestrator
from onto_platform.chat.recovery import sweep_orphan_sessions, OrphanSweepResult
from onto_platform.proto_models import OntologyRegistry, ObjectTypeDefinition
from onto_platform.registry.store import Env, RegistryStore
from onto_platform.token_store import insert_token

pytestmark = pytest.mark.asyncio


@pytest.fixture
async def factory(postgres_url, monkeypatch):
    monkeypatch.setenv("ONTO_SECRET_KEY", Fernet.generate_key().decode())
    eng = create_async_engine(postgres_url, future=True)
    f = async_sessionmaker(eng, expire_on_commit=False)
    async with f() as s:
        await s.execute(text("DELETE FROM chat_messages"))
        await s.execute(text("DELETE FROM chat_sessions"))
        await s.execute(text("DELETE FROM api_tokens"))
        await s.execute(
            text("UPDATE registries SET payload = CAST(:p AS jsonb), version = 1 WHERE env = 'staging'"),
            {"p": OntologyRegistry(version="1").model_dump_json()},
        )
        await s.commit()
    yield f
    await eng.dispose()


async def test_sweep_recovers_old_active_session(factory):
    plain = generate_token()
    async with factory() as s:
        tid = await insert_token(s, plain, Scope.editor, "ed", None)
        await s.commit()
    orch = ChatSessionOrchestrator(factory, RegistryStore())
    sid = await orch.create_session(token_id=tid)
    # Backdate created_at to 31 minutes ago and set last_turn_at NULL
    async with factory() as s:
        await s.execute(
            text(
                "UPDATE chat_sessions SET created_at = now() - interval '31 minutes', "
                "last_turn_at = NULL WHERE id = :i"
            ),
            {"i": str(sid)},
        )
        await s.commit()
    # Apply a turn to staging so cancel has something to roll back
    rs = RegistryStore()
    async with factory() as s:
        snap = await rs.load(s, Env.staging)
        new = OntologyRegistry(
            version=str(int(snap.registry.version) + 1),
            object_types={
                "ri.obj.orphan-test": ObjectTypeDefinition(rid="ri.obj.orphan-test", api_name="x")
            },
        )
        await rs.save(s, Env.staging, new, expected_version=snap.version, token_label="t")
        await s.commit()

    result = await sweep_orphan_sessions(orch, factory, orphan_after_s=1800)
    assert isinstance(result, OrphanSweepResult)
    assert result.recovered == 1
    assert result.failed == 0
    async with factory() as s:
        r = await s.execute(text("SELECT count(*) FROM chat_sessions WHERE id = :i"), {"i": str(sid)})
        assert r.scalar_one() == 0
        snap_after = await rs.load(s, Env.staging)
        assert "ri.obj.orphan-test" not in snap_after.registry.object_types


async def test_sweep_does_not_touch_recent_sessions(factory):
    plain = generate_token()
    async with factory() as s:
        tid = await insert_token(s, plain, Scope.editor, "ed", None)
        await s.commit()
    orch = ChatSessionOrchestrator(factory, RegistryStore())
    sid = await orch.create_session(token_id=tid)
    # Recent — created_at = now()
    result = await sweep_orphan_sessions(orch, factory, orphan_after_s=1800)
    assert result.recovered == 0
    async with factory() as s:
        r = await s.execute(text("SELECT count(*) FROM chat_sessions WHERE id = :i"), {"i": str(sid)})
        assert r.scalar_one() == 1
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/unit/test_chat_recovery.py -v
```
Expected: FAIL — module not found.

- [ ] **Step 3: Implement recovery**

```python
# onto_platform/chat/recovery.py
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from onto_platform.chat.orchestrator import (
    ChatSessionOrchestrator,
    StaleStagingError,
)

log = logging.getLogger(__name__)


@dataclass
class OrphanSweepResult:
    recovered: int = 0
    failed: int = 0


async def sweep_orphan_sessions(
    orchestrator: ChatSessionOrchestrator,
    session_factory: async_sessionmaker[AsyncSession],
    *,
    orphan_after_s: int,
) -> OrphanSweepResult:
    """Roll back chat sessions that have been idle longer than orphan_after_s.

    A session is considered orphaned when status='active' AND
      (last_turn_at IS NULL AND created_at < now() - orphan_after_s)
      OR (last_turn_at < now() - orphan_after_s).
    """
    async with session_factory() as s:
        rows = await s.execute(
            text(
                "SELECT id, created_at, last_turn_at FROM chat_sessions "
                "WHERE status = 'active' AND ("
                "  (last_turn_at IS NULL AND created_at < now() - make_interval(secs => :s)) OR "
                "  (last_turn_at < now() - make_interval(secs => :s))"
                ")"
            ),
            {"s": orphan_after_s},
        )
        orphan_ids = [uuid.UUID(str(r.id)) for r in rows]
    result = OrphanSweepResult()
    for sid in orphan_ids:
        try:
            await orchestrator.cancel_session(sid)
            log.warning("orphan chat session %s rolled back", sid)
            result.recovered += 1
        except StaleStagingError as e:
            log.error(
                "orphan chat session %s rollback failed (StaleStagingError): %s",
                sid,
                e,
            )
            result.failed += 1
        except Exception as e:
            log.exception("orphan chat session %s rollback failed: %s", sid, e)
            result.failed += 1
    return result
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/unit/test_chat_recovery.py -v
```
Expected: 2 PASS.

- [ ] **Step 5: Commit**

```bash
git add onto_platform/chat/recovery.py tests/unit/test_chat_recovery.py
git commit -m "feat(chat): orphan-session sweep on startup"
```

---

## Phase 3 — SSE infra + chat HTTP endpoints

### Task 3.1: SSE fan-out queue + heartbeat helper

**Files:**
- Create: `onto_platform/chat/sse.py`
- Test: `tests/unit/test_chat_sse.py`

- [ ] **Step 1: Failing test**

```python
# tests/unit/test_chat_sse.py
import asyncio
import json
import pytest
from onto_platform.chat.sse import EventBus, sse_format

pytestmark = pytest.mark.asyncio


def test_sse_format_serializes_event_and_data():
    s = sse_format("tool_call", {"name": "put_object_type"})
    assert s.startswith("event: tool_call\n")
    assert "data: " in s
    assert s.endswith("\n\n")
    data_line = next(ln for ln in s.splitlines() if ln.startswith("data: "))
    assert json.loads(data_line[len("data: "):])["name"] == "put_object_type"


async def test_event_bus_fan_out_to_two_consumers():
    bus = EventBus()
    out_a: list[tuple[str, dict]] = []
    out_b: list[tuple[str, dict]] = []

    async def consumer(target):
        async for event_type, payload in bus.subscribe("turn-1"):
            target.append((event_type, payload))

    a = asyncio.create_task(consumer(out_a))
    b = asyncio.create_task(consumer(out_b))
    await asyncio.sleep(0.05)  # let subscribers register
    await bus.publish("turn-1", "tool_call", {"name": "x"})
    await bus.publish("turn-1", "turn_complete", {"tool_calls_made": 1})
    await bus.close("turn-1")
    await asyncio.gather(a, b)
    assert out_a == [("tool_call", {"name": "x"}), ("turn_complete", {"tool_calls_made": 1})]
    assert out_b == out_a
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/unit/test_chat_sse.py -v
```
Expected: FAIL — module not found.

- [ ] **Step 3: Implement EventBus**

```python
# onto_platform/chat/sse.py
from __future__ import annotations

import asyncio
import json
from typing import AsyncIterator, Any


def sse_format(event_type: str, payload: Any) -> str:
    return f"event: {event_type}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


class _Subscription:
    def __init__(self) -> None:
        self.queue: asyncio.Queue[tuple[str, Any] | None] = asyncio.Queue()


class EventBus:
    """In-process pub/sub keyed by turn_id. Each subscribe() yields events
    until close(turn_id) is called, after which the iterator returns.

    Buffered: events published before any subscriber arrives are NOT replayed
    on subscribe. Callers should ensure the subscriber starts before the
    publisher begins emitting (HTTP layer subscribes synchronously inside the
    streaming response handler before kicking off the background turn worker).
    """

    def __init__(self) -> None:
        self._subs: dict[str, list[_Subscription]] = {}

    async def subscribe(self, turn_id: str) -> AsyncIterator[tuple[str, Any]]:
        sub = _Subscription()
        self._subs.setdefault(turn_id, []).append(sub)
        try:
            while True:
                item = await sub.queue.get()
                if item is None:
                    return
                yield item
        finally:
            self._subs.get(turn_id, []).remove(sub)

    async def publish(self, turn_id: str, event_type: str, payload: Any) -> None:
        for sub in list(self._subs.get(turn_id, [])):
            await sub.queue.put((event_type, payload))

    async def close(self, turn_id: str) -> None:
        for sub in list(self._subs.get(turn_id, [])):
            await sub.queue.put(None)
        self._subs.pop(turn_id, None)
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/unit/test_chat_sse.py -v
```
Expected: 2 PASS.

- [ ] **Step 5: Commit**

```bash
git add onto_platform/chat/sse.py tests/unit/test_chat_sse.py
git commit -m "feat(chat): in-process SSE EventBus + sse_format helper"
```

---

### Task 3.2: Chat HTTP router — POST /chat/sessions, GET /chat/sessions/{id}

**Files:**
- Create: `onto_platform/chat/http.py`
- Test: `tests/integration/test_chat_http.py`

- [ ] **Step 1: Failing test**

```python
# tests/integration/test_chat_http.py
import pytest
from cryptography.fernet import Fernet
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from onto_platform.app import create_app
from onto_platform.auth import Scope, generate_token
from onto_platform.proto_models import OntologyRegistry
from onto_platform.token_store import insert_token

pytestmark = pytest.mark.asyncio


@pytest.fixture
async def setup(postgres_url, monkeypatch, tmp_path):
    monkeypatch.setenv("ONTO_DATABASE_URL", postgres_url)
    monkeypatch.setenv("ONTO_SECRET_KEY", Fernet.generate_key().decode())
    monkeypatch.setenv("ONTO_INGESTION_DATA_DIR", str(tmp_path))
    eng = create_async_engine(postgres_url, future=True)
    f = async_sessionmaker(eng, expire_on_commit=False)
    async with f() as s:
        await s.execute(text("DELETE FROM chat_messages"))
        await s.execute(text("DELETE FROM chat_sessions"))
        await s.execute(text("DELETE FROM api_tokens"))
        await s.execute(
            text("UPDATE registries SET payload = CAST(:p AS jsonb), version = 1 WHERE env = 'staging'"),
            {"p": OntologyRegistry(version="1").model_dump_json()},
        )
        await s.commit()
    plain = generate_token()
    async with f() as s:
        await insert_token(s, plain, Scope.editor, "ed", None)
        await s.commit()
    yield create_app(), plain
    await eng.dispose()


async def test_post_sessions_returns_id(setup):
    app, token = setup
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post("/chat/sessions", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 201, r.text
        body = r.json()
        assert "session_id" in body


async def test_get_session_returns_status_and_messages(setup):
    app, token = setup
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        sid = (await c.post("/chat/sessions", headers={"Authorization": f"Bearer {token}"})).json()["session_id"]
        r = await c.get(f"/chat/sessions/{sid}", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "active"
        assert body["messages"] == []


async def test_get_session_unknown_returns_404(setup):
    app, token = setup
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/chat/sessions/00000000-0000-0000-0000-000000000000", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 404


async def test_post_session_unauth_returns_401(setup):
    app, _ = setup
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post("/chat/sessions")
        assert r.status_code == 401
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/integration/test_chat_http.py -v
```
Expected: FAIL — `/chat/sessions` route not registered.

- [ ] **Step 3: Implement http.py**

```python
# onto_platform/chat/http.py
from __future__ import annotations

import uuid
from typing import Any
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from onto_platform.auth import RequestPrincipal, Scope
from onto_platform.chat.orchestrator import (
    ChatSessionOrchestrator,
    SessionNotFoundError,
    StaleStagingError,
    TurnInFlightError,
)
from onto_platform.config import Settings
from onto_platform.registry.store import RegistryStore
from onto_platform.ui_auth import require_scope_via_cookie_or_bearer


def make_chat_router(
    session_provider: Any,
    *,
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
) -> APIRouter:
    router = APIRouter(prefix="/chat")
    rstore = RegistryStore()
    orch = ChatSessionOrchestrator(session_factory, rstore)
    editor_dep = require_scope_via_cookie_or_bearer(Scope.editor, session_provider)

    @router.post("/sessions", status_code=201)
    async def create_session(
        principal: RequestPrincipal = Depends(editor_dep),
    ) -> dict[str, str]:
        sid = await orch.create_session(token_id=principal.token_id)
        return {"session_id": str(sid)}

    @router.get("/sessions/{session_id}")
    async def get_session(
        session_id: str,
        principal: RequestPrincipal = Depends(editor_dep),
    ) -> dict[str, Any]:
        try:
            sid = uuid.UUID(session_id)
        except ValueError:
            raise HTTPException(404, detail={"code": "NOT_FOUND"})
        try:
            info = await orch.get_session(sid)
        except SessionNotFoundError:
            raise HTTPException(404, detail={"code": "NOT_FOUND"})
        return {
            "session_id": str(info.id),
            "status": info.status,
            "messages": info.messages,
        }

    @router.post("/sessions/{session_id}/save", status_code=204)
    async def save_session(
        session_id: str,
        principal: RequestPrincipal = Depends(editor_dep),
    ) -> None:
        try:
            sid = uuid.UUID(session_id)
        except ValueError:
            raise HTTPException(404, detail={"code": "NOT_FOUND"})
        try:
            await orch.save_session(sid)
        except SessionNotFoundError:
            raise HTTPException(404, detail={"code": "NOT_FOUND"})
        except TurnInFlightError:
            raise HTTPException(409, detail={"code": "TURN_IN_FLIGHT"})
        return None

    @router.post("/sessions/{session_id}/cancel", status_code=204)
    async def cancel_session(
        session_id: str,
        principal: RequestPrincipal = Depends(editor_dep),
    ) -> None:
        try:
            sid = uuid.UUID(session_id)
        except ValueError:
            raise HTTPException(404, detail={"code": "NOT_FOUND"})
        try:
            await orch.cancel_session(sid)
        except SessionNotFoundError:
            raise HTTPException(404, detail={"code": "NOT_FOUND"})
        except TurnInFlightError:
            raise HTTPException(409, detail={"code": "TURN_IN_FLIGHT"})
        except StaleStagingError as e:
            raise HTTPException(
                409,
                detail={"code": "STALE_STAGING", "message": str(e)},
            )
        return None

    return router


def get_orchestrator_factory(
    session_factory: async_sessionmaker[AsyncSession],
) -> ChatSessionOrchestrator:
    """Helper used by app.py to share the orchestrator instance across the router and recovery sweep."""
    return ChatSessionOrchestrator(session_factory, RegistryStore())
```

- [ ] **Step 4: Wire the router into app.py temporarily for the test (Phase 4 will finalize)**

Modify `onto_platform/app.py` after `app.include_router(make_ingestion_router(...))`:

```python
    from onto_platform.chat.http import make_chat_router
    app.include_router(
        make_chat_router(session_provider, session_factory=Session, settings=settings)
    )
```

- [ ] **Step 5: Run tests**

```bash
uv run pytest tests/integration/test_chat_http.py -v
```
Expected: 4 PASS.

- [ ] **Step 6: Commit**

```bash
git add onto_platform/chat/http.py onto_platform/app.py tests/integration/test_chat_http.py
git commit -m "feat(chat): HTTP endpoints — create/get/save/cancel session"
```

---

### Task 3.3: POST /chat/sessions/{id}/uploads — proxy to existing ingestion-uploads

**Files:**
- Modify: `onto_platform/chat/http.py`
- Modify: `tests/integration/test_chat_http.py`

- [ ] **Step 1: Failing test**

Append to `tests/integration/test_chat_http.py`:

```python
async def test_chat_upload_proxies_to_ingestion(setup):
    app, token = setup
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        sid = (await c.post("/chat/sessions", headers={"Authorization": f"Bearer {token}"})).json()["session_id"]
        r = await c.post(
            f"/chat/sessions/{sid}/uploads",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": ("x.sql", b"CREATE TABLE T (id INT);", "text/plain")},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert "upload_id" in body
        assert body["kind"] in {"sql", "text"}
```

- [ ] **Step 2: Run test**

```bash
uv run pytest tests/integration/test_chat_http.py::test_chat_upload_proxies_to_ingestion -v
```
Expected: FAIL — 404.

- [ ] **Step 3: Implement upload endpoint**

Add to the router in `onto_platform/chat/http.py`, alongside the other endpoints:

```python
    from fastapi import UploadFile, File
    from onto_platform.ingestion.http import _upload as _ingestion_upload  # if such a helper exists

    # If the ingestion upload helper is not exposed, replicate its body inline.
    @router.post("/sessions/{session_id}/uploads")
    async def upload_for_session(
        session_id: str,
        file: UploadFile = File(...),
        principal: RequestPrincipal = Depends(editor_dep),
        session: AsyncSession = Depends(session_provider),
    ) -> dict[str, Any]:
        # 404 if the session is gone or invalid
        try:
            sid = uuid.UUID(session_id)
        except ValueError:
            raise HTTPException(404, detail={"code": "NOT_FOUND"})
        try:
            await orch.get_session(sid)
        except SessionNotFoundError:
            raise HTTPException(404, detail={"code": "NOT_FOUND"})

        # Reuse the existing ingestion upload pipeline. The ingestion router lives
        # at `/admin/ingestion/uploads`; we call its underlying handler directly
        # to avoid an HTTP round-trip. To keep the surface minimal, this task
        # imports the existing upload function. If `_upload` is not exported,
        # extract a `process_upload(file, *, principal, session, settings)` helper
        # in `onto_platform/ingestion/http.py` first (one-line refactor: rename
        # the inner async function and keep the route handler calling it).

        body = await file.read()
        if len(body) > settings.ingestion_max_upload_bytes:
            raise HTTPException(
                422,
                detail={
                    "code": "FILE_TOO_LARGE",
                    "message": f"file > {settings.ingestion_max_upload_bytes} bytes",
                },
            )
        # Persist via the existing ingestion_uploads table.
        from sqlalchemy import text
        upload_id = uuid.uuid4()
        kind = _detect_kind(file.filename or "", body)
        # Write blob to disk per existing layout
        import pathlib
        data_dir = pathlib.Path(settings.ingestion_data_dir) / "uploads"
        data_dir.mkdir(parents=True, exist_ok=True)
        (data_dir / f"{upload_id}").write_bytes(body)
        await session.execute(
            text(
                "INSERT INTO ingestion_uploads (id, kind, size_bytes, original_filename, "
                "storage_path, sha256, created_by_token_id) VALUES "
                "(:id, :k, :sz, :fn, :sp, :sh, :tk)"
            ),
            {
                "id": str(upload_id),
                "k": kind,
                "sz": len(body),
                "fn": file.filename or "",
                "sp": str(data_dir / f"{upload_id}"),
                "sh": __import__("hashlib").sha256(body).hexdigest(),
                "tk": str(principal.token_id),
            },
        )
        await session.commit()
        return {"upload_id": str(upload_id), "kind": kind, "size_bytes": len(body)}


def _detect_kind(filename: str, body: bytes) -> str:
    fn = filename.lower()
    if fn.endswith(".sql"):
        return "sql"
    if fn.endswith(".csv"):
        return "csv"
    if fn.endswith(".json"):
        return "json"
    return "text"
```

Note: this duplicates the existing ingestion upload logic. Before merging, the engineer should refactor `onto_platform/ingestion/http.py` to extract a `process_upload(...)` helper and have both routers (ingestion and chat) call it. That refactor is not on the critical path for this task but is the right cleanup before commit. If the helper already exists, prefer importing it over the duplicated body shown above.

- [ ] **Step 4: Run test**

```bash
uv run pytest tests/integration/test_chat_http.py -v
```
Expected: 5 PASS.

- [ ] **Step 5: Commit**

```bash
git add onto_platform/chat/http.py tests/integration/test_chat_http.py
git commit -m "feat(chat): POST /chat/sessions/{id}/uploads proxy"
```

---

### Task 3.4: POST /chat/sessions/{id}/turns — kick off background turn worker

**Files:**
- Modify: `onto_platform/chat/orchestrator.py` (add `start_turn`)
- Modify: `onto_platform/chat/http.py` (add `/turns` endpoint)
- Modify: `tests/integration/test_chat_http.py`
- Modify: `tests/unit/test_chat_orchestrator.py`

This task is the most involved one. It creates an `ingestion_jobs` row tagged with `chat_session_id`, persists the user message, registers the running turn, and schedules the existing worker via `asyncio.create_task`. A turn-completion callback writes the assistant message and clears the running registry.

- [ ] **Step 1: Failing unit test for `start_turn` skeleton**

Append to `tests/unit/test_chat_orchestrator.py`:

```python
async def test_start_turn_persists_user_message_and_returns_turn_id(factory, token_id):
    orch = ChatSessionOrchestrator(factory, RegistryStore())
    sid = await orch.create_session(token_id=token_id)
    turn_id = await orch.start_turn(
        sid,
        user_message="把这个 SQL 加进去",
        upload_ids=[],
        token_id=token_id,
    )
    assert turn_id is not None
    async with factory() as s:
        rows = await s.execute(
            text(
                "SELECT role, content FROM chat_messages WHERE session_id = :i ORDER BY id"
            ),
            {"i": str(sid)},
        )
        msgs = list(rows)
        assert msgs[0].role == "user"
        assert msgs[0].content["text"] == "把这个 SQL 加进去"
    assert sid in orch._running


async def test_start_turn_409_if_already_running(factory, token_id):
    orch = ChatSessionOrchestrator(factory, RegistryStore())
    sid = await orch.create_session(token_id=token_id)
    await orch.start_turn(sid, user_message="a", upload_ids=[], token_id=token_id)
    with pytest.raises(TurnInFlightError):
        await orch.start_turn(sid, user_message="b", upload_ids=[], token_id=token_id)
```

- [ ] **Step 2: Run test**

```bash
uv run pytest tests/unit/test_chat_orchestrator.py -v
```
Expected: FAIL — `start_turn` not defined.

- [ ] **Step 3: Implement `start_turn` (skeleton — actual job spawn comes next)**

Add to `ChatSessionOrchestrator` in `onto_platform/chat/orchestrator.py`:

```python
    async def start_turn(
        self,
        session_id: uuid.UUID,
        *,
        user_message: str,
        upload_ids: list[str],
        token_id: uuid.UUID,
    ) -> uuid.UUID:
        if session_id in self._running:
            raise TurnInFlightError(str(session_id))
        async with self._sf() as s:
            # Verify session exists and is active
            row = await s.execute(
                text("SELECT status FROM chat_sessions WHERE id = :i"),
                {"i": str(session_id)},
            )
            rec = row.one_or_none()
            if rec is None:
                raise SessionNotFoundError(str(session_id))
            if rec.status != "active":
                raise TurnInFlightError(f"session not active: {rec.status}")

            # Determine next turn_index
            r2 = await s.execute(
                text(
                    "SELECT COALESCE(MAX(turn_index), -1) + 1 AS next "
                    "FROM chat_messages WHERE session_id = :i"
                ),
                {"i": str(session_id)},
            )
            turn_index = r2.scalar_one()

            # Insert user message
            import json
            await s.execute(
                text(
                    "INSERT INTO chat_messages (session_id, turn_index, role, content) "
                    "VALUES (:s, :t, 'user', CAST(:c AS jsonb))"
                ),
                {
                    "s": str(session_id),
                    "t": turn_index,
                    "c": json.dumps({"text": user_message, "upload_ids": upload_ids}),
                },
            )

            # Update last_turn_at for orphan-sweep heartbeat
            await s.execute(
                text("UPDATE chat_sessions SET last_turn_at = now() WHERE id = :i"),
                {"i": str(session_id)},
            )

            # Create an ingestion_jobs row tagged with this session
            from onto_platform.ingestion.store import ImportMode
            r3 = await s.execute(
                text(
                    "INSERT INTO ingestion_jobs (mode, instructions, chat_session_id, "
                    "created_by_token_id) VALUES (:m, :i, :cs, :ct) RETURNING id"
                ),
                {
                    "m": ImportMode.merge.value,
                    "i": user_message,
                    "cs": str(session_id),
                    "ct": str(token_id),
                },
            )
            turn_id = r3.scalar_one()
            await s.commit()
            self._running[session_id] = turn_id
            return uuid.UUID(str(turn_id))
```

- [ ] **Step 4: Run unit tests**

```bash
uv run pytest tests/unit/test_chat_orchestrator.py -v
```
Expected: 12 PASS (10 from earlier + 2 new).

- [ ] **Step 5: Commit**

```bash
git add onto_platform/chat/orchestrator.py tests/unit/test_chat_orchestrator.py
git commit -m "feat(chat): start_turn persists user message and creates tagged ingestion job"
```

---

### Task 3.5: Wire turn worker — runs existing run_one_job, publishes SSE events, persists assistant message

**Files:**
- Modify: `onto_platform/chat/orchestrator.py` (add `_run_turn_worker`)
- Modify: `tests/unit/test_chat_orchestrator.py`

The orchestrator schedules the existing `run_one_job` for the tagged ingestion job, but wraps it with SSE event publication. The tool-call stream is emitted by tapping `dispatch_agent_call` indirectly: the existing `run_one_job` already records a `decisions_report` on the job. A simpler scheme is used here — events are published from the orchestrator at three known boundaries (`turn_start`, `turn_complete`, `turn_error`); per-tool-call streaming requires an additional hook in `run_agent` that is out-of-scope for this plan and is documented as a follow-up.

Decision deferred to implementation time: if the engineer chooses to inline tool-call streaming into `run_agent` here, it requires a small amendment to `onto_platform/ingestion/agent.py` to accept an optional `event_emitter` callback that fires before/after each `dispatch_agent_call`. The amendment is opt-in and backwards-compatible. The plan below assumes the simpler "boundary-only events" path; the frontend plan tolerates either.

- [ ] **Step 1: Failing test**

Append to `tests/unit/test_chat_orchestrator.py`:

```python
async def test_run_turn_worker_emits_complete_event_and_persists_assistant_message(
    factory, token_id, monkeypatch
):
    from onto_platform.chat.sse import EventBus

    bus = EventBus()
    orch = ChatSessionOrchestrator(factory, RegistryStore(), event_bus=bus)
    sid = await orch.create_session(token_id=token_id)
    turn_id = await orch.start_turn(
        sid, user_message="hi", upload_ids=[], token_id=token_id
    )

    # Patch run_one_job to a no-op that just sets status=imported
    async def fake_run(job_id, *_, **__):
        async with factory() as s:
            await s.execute(
                text(
                    "UPDATE ingestion_jobs SET status='imported', finished_at=now() "
                    "WHERE id = :i"
                ),
                {"i": str(job_id)},
            )
            await s.commit()

    monkeypatch.setattr(
        "onto_platform.chat.orchestrator._run_one_job",
        fake_run,
    )

    received: list[tuple[str, dict]] = []

    async def consume():
        async for e in bus.subscribe(str(turn_id)):
            received.append(e)

    import asyncio
    consumer = asyncio.create_task(consume())
    await orch.run_turn_worker(sid, turn_id)
    await asyncio.sleep(0.05)
    consumer.cancel()
    types = [t for t, _ in received]
    assert "turn_complete" in types
    assert sid not in orch._running
    async with factory() as s:
        r = await s.execute(
            text(
                "SELECT count(*) FROM chat_messages WHERE session_id = :s AND role = 'assistant'"
            ),
            {"s": str(sid)},
        )
        assert r.scalar_one() == 1
```

- [ ] **Step 2: Run test**

```bash
uv run pytest tests/unit/test_chat_orchestrator.py::test_run_turn_worker_emits_complete_event_and_persists_assistant_message -v
```
Expected: FAIL — orchestrator constructor doesn't accept `event_bus`, and `run_turn_worker` undefined.

- [ ] **Step 3: Implement run_turn_worker + accept event_bus in constructor**

Modify `ChatSessionOrchestrator.__init__` to accept an `event_bus`:

```python
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        registry_store: RegistryStore,
        *,
        event_bus: "EventBus | None" = None,
    ) -> None:
        self._sf = session_factory
        self._rstore = registry_store
        self._running: dict[uuid.UUID, uuid.UUID] = {}
        from onto_platform.chat.sse import EventBus
        self._bus = event_bus or EventBus()

    @property
    def event_bus(self) -> "EventBus":
        return self._bus
```

Add a module-level `_run_one_job` indirection (so tests can monkeypatch it):

```python
# at module top, after imports
from onto_platform.ingestion.workers import run_one_job as _run_one_job
```

Add the worker entrypoint:

```python
    async def run_turn_worker(self, session_id: uuid.UUID, turn_id: uuid.UUID) -> None:
        try:
            await self._bus.publish(str(turn_id), "turn_start", {"turn_id": str(turn_id)})
            # Hand off to the existing ingestion-job worker
            await _run_one_job(turn_id)
            # After the job completes, fetch its outcome
            async with self._sf() as s:
                row = await s.execute(
                    text(
                        "SELECT status, decisions_report, error_code, phase_message "
                        "FROM ingestion_jobs WHERE id = :i"
                    ),
                    {"i": str(turn_id)},
                )
                rec = row.one()
                # Determine assistant message text
                if rec.status == "imported":
                    text_summary = "已完成本轮变更。"
                elif rec.status == "cancelled":
                    text_summary = "本轮已取消。"
                else:
                    text_summary = f"本轮失败：{rec.phase_message or rec.error_code or '未知错误'}"
                # Get next turn_index for the assistant row
                r2 = await s.execute(
                    text(
                        "SELECT COALESCE(MAX(turn_index), 0) FROM chat_messages "
                        "WHERE session_id = :s"
                    ),
                    {"s": str(session_id)},
                )
                turn_index = r2.scalar_one()
                import json
                await s.execute(
                    text(
                        "INSERT INTO chat_messages (session_id, turn_index, role, content) "
                        "VALUES (:s, :t, 'assistant', CAST(:c AS jsonb))"
                    ),
                    {
                        "s": str(session_id),
                        "t": turn_index,
                        "c": json.dumps({"text": text_summary}),
                    },
                )
                await s.commit()
            if rec.status == "imported":
                await self._bus.publish(
                    str(turn_id),
                    "turn_complete",
                    {"turn_id": str(turn_id), "tool_calls_made": len((rec.decisions_report or {}).get("decisions", []))},
                )
            else:
                await self._bus.publish(
                    str(turn_id),
                    "turn_error",
                    {"kind": rec.error_code or "unknown", "message": rec.phase_message or ""},
                )
        finally:
            self._running.pop(session_id, None)
            await self._bus.close(str(turn_id))
```

Note: the existing `run_one_job` signature accepts `(job_id, session_factory, settings, llm)`. The plan above shows `_run_one_job(turn_id)` for brevity — the engineer must pass the correct kwargs (read `onto_platform/ingestion/workers.py` to copy the call site already used in `IngestionWorker._run_one_job_loop`). This is a 5-line adjustment.

- [ ] **Step 4: Run test**

```bash
uv run pytest tests/unit/test_chat_orchestrator.py::test_run_turn_worker_emits_complete_event_and_persists_assistant_message -v
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add onto_platform/chat/orchestrator.py tests/unit/test_chat_orchestrator.py
git commit -m "feat(chat): run_turn_worker emits SSE boundary events and persists assistant reply"
```

---

### Task 3.6: POST /chat/sessions/{id}/turns endpoint + GET /chat/sessions/{id}/stream SSE endpoint

**Files:**
- Modify: `onto_platform/chat/http.py`
- Modify: `tests/integration/test_chat_http.py`

- [ ] **Step 1: Failing test**

Append to `tests/integration/test_chat_http.py`:

```python
async def test_post_turns_returns_turn_id_and_user_message_persists(setup):
    app, token = setup
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        sid = (await c.post("/chat/sessions", headers={"Authorization": f"Bearer {token}"})).json()["session_id"]
        r = await c.post(
            f"/chat/sessions/{sid}/turns",
            headers={"Authorization": f"Bearer {token}"},
            json={"message": "hi", "upload_ids": []},
        )
        assert r.status_code == 202, r.text
        body = r.json()
        assert "turn_id" in body
        # Wait briefly for the worker
        import asyncio
        await asyncio.sleep(1.0)
        r2 = await c.get(f"/chat/sessions/{sid}", headers={"Authorization": f"Bearer {token}"})
        msgs = r2.json()["messages"]
        assert any(m["role"] == "user" for m in msgs)


async def test_post_turns_409_if_one_running(setup):
    app, token = setup
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        sid = (await c.post("/chat/sessions", headers={"Authorization": f"Bearer {token}"})).json()["session_id"]
        # Kick off; do not await its completion; immediately try a second
        await c.post(
            f"/chat/sessions/{sid}/turns",
            headers={"Authorization": f"Bearer {token}"},
            json={"message": "first", "upload_ids": []},
        )
        r = await c.post(
            f"/chat/sessions/{sid}/turns",
            headers={"Authorization": f"Bearer {token}"},
            json={"message": "second", "upload_ids": []},
        )
        assert r.status_code == 409
```

- [ ] **Step 2: Run tests**

```bash
uv run pytest tests/integration/test_chat_http.py -v
```
Expected: FAIL — endpoint missing.

- [ ] **Step 3: Implement /turns endpoint**

Add to `onto_platform/chat/http.py`:

```python
    @router.post("/sessions/{session_id}/turns", status_code=202)
    async def submit_turn(
        session_id: str,
        body: dict[str, Any],
        principal: RequestPrincipal = Depends(editor_dep),
    ) -> dict[str, str]:
        try:
            sid = uuid.UUID(session_id)
        except ValueError:
            raise HTTPException(404, detail={"code": "NOT_FOUND"})
        message = body.get("message")
        upload_ids = body.get("upload_ids", [])
        if not isinstance(message, str) or not message.strip():
            raise HTTPException(422, detail={"code": "INVALID_BODY"})
        if not isinstance(upload_ids, list):
            raise HTTPException(422, detail={"code": "INVALID_BODY"})
        try:
            turn_id = await orch.start_turn(
                sid,
                user_message=message,
                upload_ids=[str(u) for u in upload_ids],
                token_id=principal.token_id,
            )
        except SessionNotFoundError:
            raise HTTPException(404, detail={"code": "NOT_FOUND"})
        except TurnInFlightError:
            raise HTTPException(409, detail={"code": "TURN_IN_FLIGHT"})
        # Schedule the worker as a background asyncio task
        import asyncio
        asyncio.create_task(orch.run_turn_worker(sid, turn_id))
        return {"turn_id": str(turn_id)}
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/integration/test_chat_http.py -v
```
Expected: PASS for new tests (subject to LLM stub setup; if no LLM is configured the worker will fail with `LLM_PROVIDER_ERROR` but the test only checks the user message persisted).

- [ ] **Step 5: Implement /stream SSE endpoint**

Add to `onto_platform/chat/http.py`:

```python
    from fastapi.responses import StreamingResponse
    import asyncio
    from onto_platform.chat.sse import sse_format

    @router.get("/sessions/{session_id}/stream")
    async def stream_turn(
        session_id: str,
        turn_id: str,
        principal: RequestPrincipal = Depends(editor_dep),
    ) -> StreamingResponse:
        try:
            sid = uuid.UUID(session_id)
            tid = uuid.UUID(turn_id)
        except ValueError:
            raise HTTPException(404, detail={"code": "NOT_FOUND"})
        try:
            await orch.get_session(sid)
        except SessionNotFoundError:
            raise HTTPException(404, detail={"code": "NOT_FOUND"})

        async def gen():
            heartbeat_s = settings.chat_sse_heartbeat_s
            sub_iter = orch.event_bus.subscribe(str(tid)).__aiter__()
            while True:
                try:
                    item = await asyncio.wait_for(sub_iter.__anext__(), timeout=heartbeat_s)
                except asyncio.TimeoutError:
                    yield "event: heartbeat\ndata: {}\n\n"
                    continue
                except StopAsyncIteration:
                    return
                event_type, payload = item
                yield sse_format(event_type, payload)
                if event_type in ("turn_complete", "turn_error"):
                    return

        return StreamingResponse(gen(), media_type="text/event-stream")
```

- [ ] **Step 6: Add a smoke test that the SSE stream emits `turn_complete`**

Append to `tests/integration/test_chat_http.py`:

```python
async def test_stream_emits_turn_complete(setup):
    app, token = setup
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        sid = (await c.post("/chat/sessions", headers={"Authorization": f"Bearer {token}"})).json()["session_id"]
        # Start a turn
        tr = await c.post(
            f"/chat/sessions/{sid}/turns",
            headers={"Authorization": f"Bearer {token}"},
            json={"message": "hi", "upload_ids": []},
        )
        turn_id = tr.json()["turn_id"]
        # Connect SSE
        async with c.stream(
            "GET",
            f"/chat/sessions/{sid}/stream?turn_id={turn_id}",
            headers={"Authorization": f"Bearer {token}"},
        ) as resp:
            assert resp.status_code == 200
            saw_complete_or_error = False
            async for line in resp.aiter_lines():
                if line.startswith("event: turn_complete") or line.startswith("event: turn_error"):
                    saw_complete_or_error = True
                    break
            assert saw_complete_or_error
```

This relies on the test environment having a configured LLM — if not, `turn_error` is the expected outcome and the test still passes. The fixture must export `ONTO_LLM_*` vars or the test must skip when they are unset.

- [ ] **Step 7: Run tests**

```bash
uv run pytest tests/integration/test_chat_http.py -v
```
Expected: PASS for all tests (gracefully skipping `test_stream_emits_turn_complete` if LLM config absent).

- [ ] **Step 8: Commit**

```bash
git add onto_platform/chat/http.py tests/integration/test_chat_http.py
git commit -m "feat(chat): POST /turns + GET /stream SSE endpoints"
```

---

## Phase 4 — App wiring + orphan recovery on startup

### Task 4.1: Run the orphan sweep at app startup

**Files:**
- Modify: `onto_platform/app.py`
- Test: `tests/integration/test_chat_recovery_startup.py`

- [ ] **Step 1: Failing test**

```python
# tests/integration/test_chat_recovery_startup.py
import pytest
from cryptography.fernet import Fernet
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from onto_platform.app import create_app
from onto_platform.auth import Scope, generate_token
from onto_platform.proto_models import OntologyRegistry, ObjectTypeDefinition
from onto_platform.registry.store import Env, RegistryStore
from onto_platform.token_store import insert_token

pytestmark = pytest.mark.asyncio


async def test_startup_sweeps_orphan_chat_sessions(postgres_url, monkeypatch, tmp_path):
    monkeypatch.setenv("ONTO_DATABASE_URL", postgres_url)
    monkeypatch.setenv("ONTO_SECRET_KEY", Fernet.generate_key().decode())
    monkeypatch.setenv("ONTO_INGESTION_DATA_DIR", str(tmp_path))
    eng = create_async_engine(postgres_url, future=True)
    f = async_sessionmaker(eng, expire_on_commit=False)
    async with f() as s:
        await s.execute(text("DELETE FROM chat_messages"))
        await s.execute(text("DELETE FROM chat_sessions"))
        await s.execute(text("DELETE FROM api_tokens"))
        await s.execute(
            text("UPDATE registries SET payload = CAST(:p AS jsonb), version = 1 WHERE env = 'staging'"),
            {"p": OntologyRegistry(version="1").model_dump_json()},
        )
        await s.commit()

    plain = generate_token()
    async with f() as s:
        tid = await insert_token(s, plain, Scope.editor, "ed", None)
        # Insert an orphan session by hand (created 31 minutes ago)
        await s.execute(
            text(
                "INSERT INTO chat_sessions (id, token_id, status, "
                "pre_session_registry, pre_session_version, created_at) "
                "VALUES (gen_random_uuid(), :t, 'active', "
                "CAST(:p AS jsonb), 1, now() - interval '31 minutes')"
            ),
            {
                "t": str(tid),
                "p": OntologyRegistry(version="1").model_dump_json(),
            },
        )
        # Bump staging so cancel has rollback work to do
        rs = RegistryStore()
        snap = await rs.load(s, Env.staging)
        await rs.save(
            s,
            Env.staging,
            OntologyRegistry(
                version=str(int(snap.registry.version) + 1),
                object_types={"ri.obj.orphan": ObjectTypeDefinition(rid="ri.obj.orphan", api_name="x")},
            ),
            expected_version=snap.version,
            token_label="t",
        )
        await s.commit()

    # Boot the app — the lifespan should sweep
    from httpx import ASGITransport, AsyncClient
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        # Trigger lifespan startup
        r = await c.get("/healthz")
        assert r.status_code == 200

    # Verify the orphan was rolled back
    async with f() as s:
        r = await s.execute(text("SELECT count(*) FROM chat_sessions WHERE status = 'active'"))
        assert r.scalar_one() == 0
        snap = await RegistryStore().load(s, Env.staging)
        assert "ri.obj.orphan" not in snap.registry.object_types
    await eng.dispose()
```

- [ ] **Step 2: Run test**

```bash
uv run pytest tests/integration/test_chat_recovery_startup.py -v
```
Expected: FAIL — startup does not invoke the sweep yet.

- [ ] **Step 3: Wire the sweep into app.py lifespan**

In `onto_platform/app.py`, locate the `lifespan` async generator (around line 35). Modify:

```python
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        await bootstrap_admin_token_if_needed(Session)
        # Run orphan recovery sweep for chat sessions
        from onto_platform.chat.orchestrator import ChatSessionOrchestrator
        from onto_platform.chat.recovery import sweep_orphan_sessions
        from onto_platform.registry.store import RegistryStore
        chat_orch = ChatSessionOrchestrator(Session, RegistryStore())
        await sweep_orphan_sessions(
            chat_orch, Session, orphan_after_s=settings.chat_session_orphan_after_s
        )
        # Stash the orchestrator on app.state so the chat router uses the same instance
        app.state.chat_orchestrator = chat_orch
        yield
        await engine.dispose()
```

- [ ] **Step 4: Update `make_chat_router` to accept the existing orchestrator**

Modify `onto_platform/chat/http.py`:

```python
def make_chat_router(
    session_provider: Any,
    *,
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
    orchestrator: ChatSessionOrchestrator | None = None,
) -> APIRouter:
    router = APIRouter(prefix="/chat")
    rstore = RegistryStore()
    orch = orchestrator or ChatSessionOrchestrator(session_factory, rstore)
    ...
```

And update the call site in `app.py`:

```python
    app.include_router(
        make_chat_router(
            session_provider,
            session_factory=Session,
            settings=settings,
            orchestrator=app.state.chat_orchestrator if hasattr(app.state, "chat_orchestrator") else None,
        )
    )
```

Note: app.state is populated in `lifespan` startup, but `include_router` runs at app construction. The cleanest fix is to construct the orchestrator at app construction time, store it on `app.state`, and have lifespan run the sweep using that same instance:

```python
    chat_orch = ChatSessionOrchestrator(Session, RegistryStore())
    app.state.chat_orchestrator = chat_orch
    app.include_router(
        make_chat_router(
            session_provider,
            session_factory=Session,
            settings=settings,
            orchestrator=chat_orch,
        )
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        await bootstrap_admin_token_if_needed(Session)
        from onto_platform.chat.recovery import sweep_orphan_sessions
        await sweep_orphan_sessions(
            chat_orch, Session, orphan_after_s=settings.chat_session_orphan_after_s
        )
        yield
        await engine.dispose()
```

- [ ] **Step 5: Run test**

```bash
uv run pytest tests/integration/test_chat_recovery_startup.py -v
```
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add onto_platform/app.py onto_platform/chat/http.py tests/integration/test_chat_recovery_startup.py
git commit -m "feat(chat): run orphan-session sweep on app startup"
```

---

### Task 4.2: End-to-end backend smoke test (curl-only, no UI)

**Files:**
- Create: `scripts/chat-smoke.sh`

This is a manual / CI-runnable smoke that drives the full chat lifecycle via curl: create session, upload, post turn, stream events, save. Useful before deploying without a UI.

- [ ] **Step 1: Write the script**

```bash
#!/usr/bin/env bash
# scripts/chat-smoke.sh — drive the full chat lifecycle via HTTP, verify each step.
set -euo pipefail

BASE="${ONTO_BASE_URL:-http://127.0.0.1:8080}"
TOKEN="${ONTO_BOOTSTRAP_TOKEN:?must export ONTO_BOOTSTRAP_TOKEN}"

echo "==> create session"
SID=$(curl -fsS -X POST "$BASE/chat/sessions" \
  -H "Authorization: Bearer $TOKEN" | jq -r .session_id)
echo "    session_id=$SID"

echo "==> upload SQL fixture"
UID=$(curl -fsS -X POST "$BASE/chat/sessions/$SID/uploads" \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@tests/fixtures/sql/logistics_minimal_ddl.sql" | jq -r .upload_id)
echo "    upload_id=$UID"

echo "==> submit turn"
TID=$(curl -fsS -X POST "$BASE/chat/sessions/$SID/turns" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"message\":\"把 logistics_minimal_ddl.sql 里的所有表加进去\",\"upload_ids\":[\"$UID\"]}" \
  | jq -r .turn_id)
echo "    turn_id=$TID"

echo "==> stream events (timeout 90s)"
timeout 90 curl -fsS -N \
  -H "Authorization: Bearer $TOKEN" \
  "$BASE/chat/sessions/$SID/stream?turn_id=$TID" || true

echo "==> save session"
curl -fsS -X POST "$BASE/chat/sessions/$SID/save" \
  -H "Authorization: Bearer $TOKEN"
echo "==> done"
```

- [ ] **Step 2: Make executable + manual run against local stack**

```bash
chmod +x scripts/chat-smoke.sh
# In another terminal: docker compose -f docker/compose.yaml up -d
# export ONTO_BOOTSTRAP_TOKEN=$(docker compose -f docker/compose.yaml logs app | grep -oE 'op_[A-Za-z0-9_-]+' | head -1)
bash scripts/chat-smoke.sh
```
Expected: each curl prints success; the SSE stream emits at least one `event: turn_complete` or `event: turn_error` line within 90s; the final `save` returns 204.

- [ ] **Step 3: Commit**

```bash
git add scripts/chat-smoke.sh
git commit -m "chore(chat): backend smoke script — curl-driven full lifecycle"
```

---

## Wrap-up

After Phase 4 completes:

- All MCP tools, `run_agent`, `run_one_job`, and existing `/admin/ingestion/*` HTTP endpoints are unchanged.
- New endpoints: `POST /chat/sessions`, `GET /chat/sessions/{id}`, `POST /chat/sessions/{id}/uploads`, `POST /chat/sessions/{id}/turns`, `GET /chat/sessions/{id}/stream`, `POST /chat/sessions/{id}/save`, `POST /chat/sessions/{id}/cancel`.
- New tables: `chat_sessions`, `chat_messages`. New column on `ingestion_jobs`: `chat_session_id`.
- New module: `onto_platform/chat/{__init__,orchestrator,sse,http,recovery}.py`.
- Orphan sweep runs on every app start; sessions abandoned for >30 min are rolled back automatically.

The frontend plan (`docs/superpowers/plans/2026-04-28-ui-redesign-frontend.md`) builds on this. Until that plan ships, the existing UI continues to work; the new chat endpoints are usable via curl / MCP-over-HTTP clients.

## Self-Review Checklist (run before merging)

- [ ] All tests in `tests/unit/test_chat_*.py` pass
- [ ] All tests in `tests/integration/test_chat_*.py` pass
- [ ] `make test` (unit + integration) passes
- [ ] `make lint` passes (ruff + mypy)
- [ ] Smoke script exits cleanly against a fresh stack
- [ ] `git diff main` shows zero changes outside: `migrations/`, `onto_platform/chat/`, `onto_platform/config.py`, `onto_platform/app.py`, `tests/`, `scripts/`
- [ ] No changes to any `onto_platform/mcp_tools_*.py` file
- [ ] No changes to `onto_platform/ingestion/agent.py` or `onto_platform/ingestion/workers.py`

