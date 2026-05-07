# tests/security/test_leakage.py
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
async def setup(postgres_url, monkeypatch):
    monkeypatch.setenv("ONTO_DATABASE_URL", postgres_url)
    monkeypatch.setenv("ONTO_SECRET_KEY", Fernet.generate_key().decode())
    engine = create_async_engine(postgres_url, future=True)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        await s.execute(text("DELETE FROM api_tokens"))
        await s.execute(text("DELETE FROM audit_log"))
        await s.execute(text("DELETE FROM connections"))
        await s.commit()
    plain = generate_token()
    async with factory() as s:
        await insert_token(s, plain, Scope.admin, "admin", None)
        await s.commit()
    yield create_app(), plain, factory
    await engine.dispose()


async def test_mint_token_plaintext_not_in_audit_log(setup):
    app, admin_token, factory = setup
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post("/mcp",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                  "params": {"name": "mint_token", "arguments": {"scope": "read", "label": "leak-probe"}}})
    new_token = r.json()["result"]["structuredContent"]["token"]
    async with factory() as s:
        rows = (await s.execute(text("SELECT args_summary FROM audit_log"))).all()
    for row in rows:
        assert new_token not in repr(row.args_summary)


async def test_dsn_password_redacted_on_probe_failure(setup):
    app, admin_token, factory = setup
    bad_dsn = "mysql+aiomysql://user:topsecretpw@127.0.0.1:1/db"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post("/mcp",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                  "params": {"name": "add_connection",
                             "arguments": {"label": "bad", "kind": "mysql", "dsn": bad_dsn}}})
    body = r.json()
    assert body["error"]["message"] == "CONNECTION_PROBE_FAILED"
    assert "topsecretpw" not in repr(body)
    async with factory() as s:
        rows = (await s.execute(text("SELECT args_summary FROM audit_log"))).all()
    for row in rows:
        assert "topsecretpw" not in repr(row.args_summary)


async def test_audit_log_truncates_long_sql(setup):
    app, admin_token, factory = setup
    big_sql = "SELECT " + "x" * 1500 + " FROM t"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        await c.post("/mcp",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                  "params": {"name": "query_sql", "arguments": {"connection_id": "00000000-0000-0000-0000-000000000000", "sql": big_sql}}})
    async with factory() as s:
        rows = (await s.execute(text("SELECT args_summary FROM audit_log WHERE tool='query_sql'"))).all()
    assert any(
        len(row.args_summary.get("sql", "")) == 500 and row.args_summary.get("sql_truncated") is True
        for row in rows
    )
