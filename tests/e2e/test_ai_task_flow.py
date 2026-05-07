# tests/e2e/test_ai_task_flow.py
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
    """Apply DDL + seed to the MySQL test container synchronously."""
    sync_url = mysql_container.get_connection_url()
    from sqlalchemy import create_engine
    sync = create_engine(sync_url, future=True)
    # Use the minimal DDL (the full logistics_ddl.sql has very wide tables that
    # exceed MySQL's row-size limit in test containers with default settings).
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
async def app_with_admin(postgres_url, monkeypatch):
    monkeypatch.setenv("ONTO_DATABASE_URL", postgres_url)
    monkeypatch.setenv("ONTO_SECRET_KEY", Fernet.generate_key().decode())
    engine = create_async_engine(postgres_url, future=True)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        await s.execute(text("DELETE FROM api_tokens"))
        await s.execute(text("DELETE FROM connections"))
        await s.execute(text(
            "UPDATE registries SET payload='{\"version\":\"__empty__\","
            "\"shared_property_types\":{},\"interface_types\":{},"
            "\"object_types\":{},\"link_types\":{},\"action_types\":{}}'::jsonb, version=0"
        ))
        await s.commit()
    plain = generate_token()
    async with factory() as s:
        await insert_token(s, plain, Scope.admin, "admin", None)
        await s.commit()
    yield create_app(), plain
    await engine.dispose()


async def _call(c, token, name, args=None):
    r = await c.post("/mcp",
        headers={"Authorization": f"Bearer {token}"},
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/call",
              "params": {"name": name, "arguments": args or {}}})
    return r.json()


async def test_ai_task_flow_headline(app_with_admin, seeded_mysql):
    app, admin = app_with_admin
    fixture = json.loads((FIXTURES / "ontology" / "logistics_registry.json").read_text())

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        # 1) admin registers a MySQL connection
        added = await _call(c, admin, "add_connection",
                            {"label": "logistics_mysql", "kind": "mysql", "dsn": seeded_mysql})
        conn_id = added["result"]["structuredContent"]["id"]

        # 2) substitute the connection_id placeholder in the fixture
        fixture["object_types"]["ri.obj.aaaaaaaa-aaaa-aaaa-aaaa-000000000001"]["asset_mapping"]["read_connection_id"] = conn_id

        # 3) admin imports the fixture into staging
        imported = await _call(c, admin, "import_full_registry_to_staging",
                               {"registry": fixture, "mode": "replace"})
        assert "result" in imported, imported

        # 4) admin promotes
        promoted = await _call(c, admin, "promote_staging_to_production",
                               {"commit_message": "initial logistics seed"})
        assert "result" in promoted, promoted

        # 5) mint a read token, switch principal
        m = await _call(c, admin, "mint_token", {"scope": "read", "label": "ai-reader"})
        read_token = m["result"]["structuredContent"]["token"]

        # 6) read flow — list, describe, query
        listed = (await _call(c, read_token, "list_object_types", {"env": "production"}))["result"]["structuredContent"]
        assert any(it["api_name"] == "material" for it in listed["items"])

        described = (await _call(c, read_token, "describe_bound_asset",
                                 {"env": "production",
                                  "rid": "ri.obj.aaaaaaaa-aaaa-aaaa-aaaa-000000000001"}))["result"]["structuredContent"]
        assert described["asset_path"] == "MD_MATERIAL"
        price_col = next(col for col in described["columns"] if col["api_name"] == "plan_price")
        assert price_col["sensitivity"] == "CONFIDENTIAL"

        # 7) the headline assertion: PLAN_PRICE is masked in query results
        q = await _call(c, read_token, "query_sql",
                        {"connection_id": conn_id,
                         "sql": "SELECT MATERIAL_CODE, MATERIAL_NAME, PLAN_PRICE FROM MD_MATERIAL ORDER BY MATERIAL_CODE LIMIT 5"})
        result = q["result"]["structuredContent"]
        assert "PLAN_PRICE" in result["masked_columns"]
        price_idx = next(i for i, col in enumerate(result["columns"]) if col["name"] == "PLAN_PRICE")
        name_idx = next(i for i, col in enumerate(result["columns"]) if col["name"] == "MATERIAL_NAME")
        assert all(row[price_idx] == "***" for row in result["rows"])
        assert any(row[name_idx] == "Bolt M6" for row in result["rows"])

        # 8) read token cannot edit
        forbidden = await _call(c, read_token, "put_object_type",
                                {"definition": {"rid": "ri.obj.bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
                                                "api_name": "x", "lifecycle_status": "ACTIVE"}})
        assert forbidden["error"]["message"] == "FORBIDDEN"
