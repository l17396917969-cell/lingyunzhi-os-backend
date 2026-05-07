# tests/integration/test_mcp_mount.py
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from onto_platform.app import create_app
from onto_platform.auth import Scope, generate_token
from onto_platform.token_store import insert_token

pytestmark = pytest.mark.asyncio


@pytest.fixture
async def app_with_token(postgres_url, monkeypatch):
    monkeypatch.setenv("ONTO_DATABASE_URL", postgres_url)
    monkeypatch.setenv("ONTO_SECRET_KEY", "0" * 44)
    engine = create_async_engine(postgres_url, future=True)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        await s.execute(text("DELETE FROM api_tokens"))
        await s.commit()
    plaintext = generate_token()
    async with factory() as s:
        await insert_token(s, plaintext, Scope.read, "tester", None)
        await s.commit()
    app = create_app()
    yield app, plaintext
    await engine.dispose()


async def test_tools_list_returns_only_read_for_read_scope(app_with_token):
    app, token = app_with_token
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        # MCP tools/list over Streamable HTTP via JSON-RPC
        r = await c.post(
            "/mcp",
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
        )
    assert r.status_code == 200
    body = r.json()
    tools = body["result"]["tools"]
    names = {t["name"] for t in tools}
    # whoami is always readable; CRUD names should NOT appear for a read token
    assert "whoami" in names
    assert "put_object_type" not in names
    assert "promote_staging_to_production" not in names


async def test_unauthorized_request_returns_401(app_with_token):
    app, _ = app_with_token
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    assert r.status_code == 401
