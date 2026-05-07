import base64
import pytest
from cryptography.fernet import Fernet
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from onto_platform.app import create_app
from onto_platform.auth import Scope, generate_token
from onto_platform.token_store import insert_token

pytestmark = pytest.mark.asyncio


@pytest.fixture
async def setup(postgres_url, monkeypatch, tmp_path):
    monkeypatch.setenv("ONTO_DATABASE_URL", postgres_url)
    monkeypatch.setenv("ONTO_SECRET_KEY", Fernet.generate_key().decode())
    monkeypatch.setenv("ONTO_INGESTION_DATA_DIR", str(tmp_path))
    engine = create_async_engine(postgres_url, future=True)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        await s.execute(text("DELETE FROM api_tokens"))
        await s.execute(text("DELETE FROM ingestion_uploads"))
        await s.execute(text("DELETE FROM ingestion_jobs"))
        await s.commit()
    plain_admin = generate_token()
    plain_editor = generate_token()
    async with factory() as s:
        await insert_token(s, plain_admin, Scope.admin, "admin", None)
        await insert_token(s, plain_editor, Scope.editor, "editor", None)
        await s.commit()
    yield create_app(), plain_admin, plain_editor
    await engine.dispose()


async def test_register_upload_then_submit(setup):
    app, admin, editor = setup
    payload_b64 = base64.b64encode(b"CREATE TABLE T (id INT);").decode()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post(
            "/mcp",
            headers={"Authorization": f"Bearer {admin}"},
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "register_upload",
                    "arguments": {"filename": "x.sql", "base64_content": payload_b64},
                },
            },
        )
        assert "result" in r.json(), r.text
        upload_id = r.json()["result"]["structuredContent"]["upload_id"]

        r2 = await c.post(
            "/mcp",
            headers={"Authorization": f"Bearer {editor}"},
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "submit_ingestion_job",
                    "arguments": {"upload_ids": [upload_id], "mode": "replace"},
                },
            },
        )
        assert "result" in r2.json(), r2.text
        job_id = r2.json()["result"]["structuredContent"]["job_id"]

        r3 = await c.post(
            "/mcp",
            headers={"Authorization": f"Bearer {editor}"},
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": "get_ingestion_job", "arguments": {"job_id": job_id}},
            },
        )
        assert "result" in r3.json(), r3.text


async def test_register_upload_requires_admin(setup):
    app, _, editor = setup
    payload_b64 = base64.b64encode(b"x").decode()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post(
            "/mcp",
            headers={"Authorization": f"Bearer {editor}"},
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "register_upload",
                    "arguments": {"filename": "x.sql", "base64_content": payload_b64},
                },
            },
        )
    assert r.json()["error"]["message"] == "FORBIDDEN"


async def test_list_ingestion_jobs(setup):
    app, admin, editor = setup
    payload_b64 = base64.b64encode(b"SELECT 1;").decode()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        # register upload
        r = await c.post(
            "/mcp",
            headers={"Authorization": f"Bearer {admin}"},
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "register_upload",
                    "arguments": {"filename": "q.sql", "base64_content": payload_b64},
                },
            },
        )
        upload_id = r.json()["result"]["structuredContent"]["upload_id"]
        # submit
        await c.post(
            "/mcp",
            headers={"Authorization": f"Bearer {editor}"},
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "submit_ingestion_job",
                    "arguments": {"upload_ids": [upload_id], "mode": "replace"},
                },
            },
        )
        # list
        r3 = await c.post(
            "/mcp",
            headers={"Authorization": f"Bearer {editor}"},
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": "list_ingestion_jobs", "arguments": {}},
            },
        )
        items = r3.json()["result"]["structuredContent"]["items"]
    assert len(items) >= 1


async def test_delete_orphan_uploads_requires_admin(setup):
    app, _, editor = setup
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post(
            "/mcp",
            headers={"Authorization": f"Bearer {editor}"},
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "delete_orphan_uploads",
                    "arguments": {"older_than_minutes": 5},
                },
            },
        )
    assert r.json()["error"]["message"] == "FORBIDDEN"
