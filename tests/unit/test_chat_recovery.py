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
