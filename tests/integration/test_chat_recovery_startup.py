# tests/integration/test_chat_recovery_startup.py
import asyncio
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


async def _run_lifespan_startup_then_shutdown(app) -> None:
    """Fire ASGI lifespan.startup then lifespan.shutdown against a FastAPI app.

    httpx.ASGITransport does NOT send lifespan events, so we do it manually.
    This is the same protocol that uvicorn / starlette TestClient use internally.
    """
    startup_complete = asyncio.Event()
    shutdown_complete = asyncio.Event()
    startup_exc: BaseException | None = None

    # We communicate with the app via these queues
    receive_queue: asyncio.Queue = asyncio.Queue()
    send_queue: asyncio.Queue = asyncio.Queue()

    async def receive():
        return await receive_queue.get()

    async def send(message):
        await send_queue.put(message)

    scope = {"type": "lifespan", "asgi": {"version": "3.0"}, "state": {}}

    async def run_app():
        await app(scope, receive, send)

    task = asyncio.create_task(run_app())
    # Send startup
    await receive_queue.put({"type": "lifespan.startup"})
    msg = await send_queue.get()
    if msg["type"] == "lifespan.startup.failed":
        task.cancel()
        raise RuntimeError(f"Lifespan startup failed: {msg.get('message', '')}")
    # msg should be lifespan.startup.complete
    # Send shutdown
    await receive_queue.put({"type": "lifespan.shutdown"})
    msg = await send_queue.get()
    if msg["type"] == "lifespan.shutdown.failed":
        task.cancel()
        raise RuntimeError(f"Lifespan shutdown failed: {msg.get('message', '')}")
    await task


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

    # Boot the app — fire the ASGI lifespan so startup (sweep) runs
    app = create_app()
    await _run_lifespan_startup_then_shutdown(app)

    # Verify the orphan was rolled back
    async with f() as s:
        r = await s.execute(text("SELECT count(*) FROM chat_sessions WHERE status = 'active'"))
        assert r.scalar_one() == 0
        snap = await RegistryStore().load(s, Env.staging)
        assert "ri.obj.orphan" not in snap.registry.object_types
    await eng.dispose()
