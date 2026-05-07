import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from onto_platform.app import create_app
from onto_platform.auth import Scope, generate_token
from onto_platform.token_store import insert_token
from onto_platform.proto_models import OntologyRegistry, ObjectTypeDefinition, LifecycleStatus

pytestmark = pytest.mark.asyncio


@pytest.fixture
async def setup(postgres_url, monkeypatch):
    monkeypatch.setenv("ONTO_DATABASE_URL", postgres_url)
    monkeypatch.setenv("ONTO_SECRET_KEY", "0" * 44)
    engine = create_async_engine(postgres_url, future=True)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        await s.execute(text("DELETE FROM api_tokens"))
        # seed both envs
        prod_obj = ObjectTypeDefinition(
            rid="ri.obj.aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            api_name="prod_only", lifecycle_status=LifecycleStatus.ACTIVE,
        )
        prod = OntologyRegistry(version="prod-1", object_types={prod_obj.rid: prod_obj})
        stage_obj = ObjectTypeDefinition(
            rid="ri.obj.bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
            api_name="stage_only", lifecycle_status=LifecycleStatus.ACTIVE,
        )
        stage = OntologyRegistry(
            version="stage-1",
            object_types={stage_obj.rid: stage_obj, prod_obj.rid: prod_obj},
        )
        await s.execute(
            text("UPDATE registries SET payload=cast(:p AS jsonb), version=1 WHERE env='production'"),
            {"p": prod.model_dump_json()},
        )
        await s.execute(
            text("UPDATE registries SET payload=cast(:p AS jsonb), version=2 WHERE env='staging'"),
            {"p": stage.model_dump_json()},
        )
        await s.commit()
    plain = generate_token()
    async with factory() as s:
        await insert_token(s, plain, Scope.read, "viewer", None)
        await s.commit()
    yield create_app(), plain
    await engine.dispose()


async def test_summary_endpoint(setup):
    app, token = setup
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/api/registries/production/summary",
                        headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    body = r.json()
    assert body["entity_counts"]["object_types"] == 1
    assert body["version"] == 1


async def test_full_endpoint(setup):
    app, token = setup
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/api/registries/staging/full",
                        headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    payload = r.json()
    assert "ri.obj.bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb" in payload["object_types"]


async def test_diff_endpoint(setup):
    app, token = setup
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/api/registries/diff",
                        headers={"Authorization": f"Bearer {token}"})
    body = r.json()
    assert "ri.obj.bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb" in body["added"]["object_types"]
    assert body["removed"]["object_types"] == {}


async def test_audit_log_recent(setup):
    app, token = setup
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        # cause an audit row by calling whoami via MCP
        await c.post("/mcp",
                     headers={"Authorization": f"Bearer {token}"},
                     json={"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                           "params": {"name": "whoami", "arguments": {}}})
        r = await c.get("/api/audit-log/recent?limit=10",
                        headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    items = r.json()["items"]
    assert any(i["tool"] == "whoami" for i in items)
