# tests/security/test_masking_bypass.py
import json
import pathlib
import pytest
from cryptography.fernet import Fernet
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from testcontainers.mysql import MySqlContainer

from onto_platform.app import create_app
from onto_platform.auth import Scope, generate_token
from onto_platform.token_store import insert_token

pytestmark = [pytest.mark.asyncio, pytest.mark.e2e]

FIXTURES = pathlib.Path(__file__).resolve().parents[1] / "fixtures"


@pytest.fixture(scope="module")
def mysql_container():
    with MySqlContainer("mysql:8.0", dialect="pymysql") as mc:
        yield mc


@pytest.fixture(scope="module")
def seeded_mysql(mysql_container):
    sync_url = mysql_container.get_connection_url()
    from sqlalchemy import create_engine
    sync = create_engine(sync_url, future=True)
    ddl = (FIXTURES / "sql" / "logistics_minimal_ddl.sql").read_text()
    seed = (FIXTURES / "sql" / "logistics_seed.sql").read_text()
    with sync.begin() as conn:
        for stmt in [s.strip() for s in ddl.split(";") if s.strip()]:
            conn.exec_driver_sql(stmt + ";")
        for stmt in [s.strip() for s in seed.split(";") if s.strip()]:
            conn.exec_driver_sql(stmt + ";")
    sync.dispose()
    return sync_url.replace("mysql+pymysql://", "mysql+aiomysql://")


@pytest.fixture
async def setup(postgres_url, monkeypatch, seeded_mysql):
    monkeypatch.setenv("ONTO_DATABASE_URL", postgres_url)
    monkeypatch.setenv("ONTO_SECRET_KEY", Fernet.generate_key().decode())
    engine = create_async_engine(postgres_url, future=True)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        await s.execute(text("DELETE FROM api_tokens"))
        await s.execute(text("DELETE FROM connections"))
        await s.commit()
    plain = generate_token()
    async with factory() as s:
        await insert_token(s, plain, Scope.admin, "admin", None)
        await s.commit()
    app = create_app()
    fixture = json.loads((FIXTURES / "ontology" / "logistics_registry.json").read_text())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        async def call(name, args=None, tok=plain):
            r = await c.post("/mcp",
                headers={"Authorization": f"Bearer {tok}"},
                json={"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                      "params": {"name": name, "arguments": args or {}}})
            return r.json()
        added = await call("add_connection",
                           {"label": "x", "kind": "mysql", "dsn": seeded_mysql})
        conn_id = added["result"]["structuredContent"]["id"]
        fixture["object_types"]["ri.obj.aaaaaaaa-aaaa-aaaa-aaaa-000000000001"]["asset_mapping"]["read_connection_id"] = conn_id
        await call("import_full_registry_to_staging", {"registry": fixture, "mode": "replace"})
        await call("promote_staging_to_production", {"commit_message": "init"})
        m = await call("mint_token", {"scope": "read", "label": "leak-test"})
        read_token = m["result"]["structuredContent"]["token"]
        yield app, conn_id, plain, read_token, call
    await engine.dispose()


async def test_alias_does_not_bypass_masking(setup):
    app, conn_id, _, read_token, _ = setup
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post("/mcp",
            headers={"Authorization": f"Bearer {read_token}"},
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                  "params": {"name": "query_sql", "arguments": {
                      "connection_id": conn_id,
                      "sql": "SELECT PLAN_PRICE AS leaked FROM MD_MATERIAL"}}})
    sc = r.json()["result"]["structuredContent"]
    assert "leaked" in sc["masked_columns"]
    leaked_idx = next(i for i, col in enumerate(sc["columns"]) if col["name"] == "leaked")
    assert all(row[leaked_idx] == "***" for row in sc["rows"])


async def test_derived_expression_inherits_masking(setup):
    app, conn_id, _, read_token, _ = setup
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post("/mcp",
            headers={"Authorization": f"Bearer {read_token}"},
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                  "params": {"name": "query_sql", "arguments": {
                      "connection_id": conn_id,
                      "sql": "SELECT PLAN_PRICE * 1.1 AS markup FROM MD_MATERIAL"}}})
    sc = r.json()["result"]["structuredContent"]
    assert "markup" in sc["masked_columns"]


async def test_aggregation_inherits_masking(setup):
    app, conn_id, _, read_token, _ = setup
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post("/mcp",
            headers={"Authorization": f"Bearer {read_token}"},
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                  "params": {"name": "query_sql", "arguments": {
                      "connection_id": conn_id,
                      "sql": "SELECT MIN(PLAN_PRICE) AS m, COUNT(*) AS n FROM MD_MATERIAL"}}})
    sc = r.json()["result"]["structuredContent"]
    assert "m" in sc["masked_columns"]
    assert "n" not in sc["masked_columns"]
