# tests/integration/test_mcp_tools_read.py
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
        await s.commit()
    plain = generate_token()
    async with factory() as s:
        await insert_token(s, plain, Scope.read, "reader", None)
        # seed production with one ObjectType
        obj = ObjectTypeDefinition(
            rid="ri.obj.aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            api_name="material", display_name="Material",
            lifecycle_status=LifecycleStatus.ACTIVE,
        )
        reg = OntologyRegistry(version="prod-1", object_types={obj.rid: obj})
        await s.execute(text(
            "UPDATE registries SET payload = CAST(:p AS jsonb), version = 1 WHERE env = 'production'"
        ), {"p": reg.model_dump_json()})
        await s.commit()
    yield create_app(), plain
    await engine.dispose()


async def _call(c, token, name, args=None):
    r = await c.post("/mcp",
        headers={"Authorization": f"Bearer {token}"},
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/call",
              "params": {"name": name, "arguments": args or {}}})
    return r.json()


async def test_whoami(setup):
    app, token = setup
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        body = await _call(c, token, "whoami")
    assert body["result"]["structuredContent"]["scope"] == "read"


async def test_get_registry_production(setup):
    app, token = setup
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        body = await _call(c, token, "get_registry", {"env": "production"})
    reg = body["result"]["structuredContent"]
    assert "ri.obj.aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa" in reg["object_types"]


async def test_list_object_types_filter(setup):
    app, token = setup
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        body = await _call(c, token, "list_object_types", {"env": "production", "filter": "mat"})
    items = body["result"]["structuredContent"]["items"]
    assert any(i["api_name"] == "material" for i in items)


async def test_get_entity_by_rid(setup):
    app, token = setup
    rid = "ri.obj.aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        body = await _call(c, token, "get_entity", {"env": "production", "rid": rid})
    assert body["result"]["structuredContent"]["entity"]["rid"] == rid


async def test_find_by_api_name(setup):
    app, token = setup
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        body = await _call(c, token, "find_by_api_name",
                           {"env": "production", "api_name": "material"})
    sc = body["result"]["structuredContent"]
    assert sc["entity"]["api_name"] == "material"
    assert sc["kind"] == "object_type"
