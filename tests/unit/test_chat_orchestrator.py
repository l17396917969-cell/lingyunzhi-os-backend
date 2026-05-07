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


async def test_cancel_under_stale_staging_raises(factory, token_id):
    orch = ChatSessionOrchestrator(factory, RegistryStore())
    sid = await orch.create_session(token_id=token_id)

    # Bump staging once so the orchestrator's read sees a different version
    rs = RegistryStore()
    async with factory() as s:
        snap = await rs.load(s, Env.staging)
        new = OntologyRegistry(version=str(int(snap.registry.version) + 1))
        await rs.save(s, Env.staging, new, expected_version=snap.version, token_label="t")
        await s.commit()

    # Monkey-patch save to raise StaleVersionError on the rollback attempt
    real_save = orch._rstore.save

    async def flaky_save(session, env, registry, *, expected_version, token_label, commit_message=None):
        from onto_platform.registry.store import StaleVersionError
        raise StaleVersionError(env, expected_version or 0, (expected_version or 0) + 1)

    orch._rstore.save = flaky_save  # type: ignore[method-assign]
    try:
        with pytest.raises(StaleStagingError):
            await orch.cancel_session(sid)
    finally:
        orch._rstore.save = real_save  # type: ignore[method-assign]


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


async def test_start_turn_unknown_session_raises(factory, token_id):
    orch = ChatSessionOrchestrator(factory, RegistryStore())
    with pytest.raises(SessionNotFoundError):
        await orch.start_turn(uuid.uuid4(), user_message="a", upload_ids=[], token_id=token_id)


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

    # Patch _run_one_job to a no-op that just sets status=imported
    async def fake_run(session_factory, job_id, *, llm, settings, cancel=None):
        async with session_factory() as s:
            await s.execute(
                text(
                    "UPDATE ingestion_jobs SET status='imported', finished_at=now() "
                    "WHERE id = :i"
                ),
                {"i": str(job_id)},
            )
            await s.commit()

    monkeypatch.setattr("onto_platform.chat.orchestrator._run_one_job", fake_run)

    received: list[tuple[str, dict]] = []

    async def consume():
        async for e in bus.subscribe(str(turn_id)):
            received.append(e)

    import asyncio
    consumer = asyncio.create_task(consume())
    await asyncio.sleep(0.05)  # let subscriber register
    await orch.run_turn_worker(sid, turn_id, llm=None, settings=None)
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
