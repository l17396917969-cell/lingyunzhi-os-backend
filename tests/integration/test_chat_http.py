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


async def test_chat_upload_returns_upload_id(setup):
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
        assert body["kind"] == "sql"
        assert body["size_bytes"] > 0
        assert "sha256" in body


async def test_chat_upload_unknown_session_returns_404(setup):
    app, token = setup
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post(
            "/chat/sessions/00000000-0000-0000-0000-000000000000/uploads",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": ("x.sql", b"CREATE TABLE T (id INT);", "text/plain")},
        )
        assert r.status_code == 404


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
        # Wait briefly for the worker to write at least the user message
        import asyncio
        for _ in range(20):
            r2 = await c.get(f"/chat/sessions/{sid}", headers={"Authorization": f"Bearer {token}"})
            msgs = r2.json()["messages"]
            if any(m["role"] == "user" for m in msgs):
                break
            await asyncio.sleep(0.1)
        msgs = r2.json()["messages"]
        assert any(m["role"] == "user" for m in msgs)


async def test_post_turns_409_if_one_running(setup):
    app, token = setup
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        sid = (await c.post("/chat/sessions", headers={"Authorization": f"Bearer {token}"})).json()["session_id"]
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


async def test_stream_emits_event(setup):
    """Smoke test: SSE stream emits at least one terminal event before close."""
    app, token = setup
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        sid = (await c.post("/chat/sessions", headers={"Authorization": f"Bearer {token}"})).json()["session_id"]
        tr = await c.post(
            f"/chat/sessions/{sid}/turns",
            headers={"Authorization": f"Bearer {token}"},
            json={"message": "hi", "upload_ids": []},
        )
        turn_id = tr.json()["turn_id"]
        async with c.stream(
            "GET",
            f"/chat/sessions/{sid}/stream?turn_id={turn_id}",
            headers={"Authorization": f"Bearer {token}"},
        ) as resp:
            assert resp.status_code == 200
            saw_terminal = False
            async for line in resp.aiter_lines():
                if line.startswith("event: turn_complete") or line.startswith("event: turn_error"):
                    saw_terminal = True
                    break
            assert saw_terminal


async def test_get_session_with_different_token_returns_404(setup, postgres_url, monkeypatch):
    app, token = setup
    # Create a session with the original (editor) token
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        sid = (await c.post("/chat/sessions", headers={"Authorization": f"Bearer {token}"})).json()["session_id"]

    # Mint a second editor token directly in the DB and hit /chat/sessions/{id} with it
    from cryptography.fernet import Fernet
    monkeypatch.setenv("ONTO_SECRET_KEY", Fernet.generate_key().decode())
    eng = create_async_engine(postgres_url, future=True)
    f = async_sessionmaker(eng, expire_on_commit=False)
    other_plain = generate_token()
    async with f() as s:
        await insert_token(s, other_plain, Scope.editor, "other-editor", None)
        await s.commit()
    await eng.dispose()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get(f"/chat/sessions/{sid}", headers={"Authorization": f"Bearer {other_plain}"})
        assert r.status_code == 404


async def test_create_session_429_when_cap_reached(setup):
    app, token = setup
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        # Default cap is 5; create 5 then expect 429 on the 6th
        for _ in range(5):
            r = await c.post("/chat/sessions", headers={"Authorization": f"Bearer {token}"})
            assert r.status_code == 201
        r = await c.post("/chat/sessions", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 429
        assert r.json()["detail"]["code"] == "TOO_MANY_SESSIONS"
