# tests/integration/test_mcp_tools_editor.py
import pytest
from cryptography.fernet import Fernet
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from onto_platform.app import create_app
from onto_platform.auth import Scope, generate_token
from onto_platform.token_store import insert_token

pytestmark = pytest.mark.asyncio


SP_RID = "ri.shprop.aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
OBJ_RID = "ri.obj.bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"


@pytest.fixture
async def setup(postgres_url, monkeypatch):
    secret = Fernet.generate_key().decode()
    monkeypatch.setenv("ONTO_DATABASE_URL", postgres_url)
    monkeypatch.setenv("ONTO_SECRET_KEY", secret)
    engine = create_async_engine(postgres_url, future=True)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        await s.execute(text("DELETE FROM api_tokens"))
        await s.execute(text(
            "UPDATE registries SET payload='{\"version\":\"__empty__\","
            "\"shared_property_types\":{},\"interface_types\":{},"
            "\"object_types\":{},\"link_types\":{},\"action_types\":{}}'::jsonb, version=0"
        ))
        await s.commit()
    plain = generate_token()
    async with factory() as s:
        await insert_token(s, plain, Scope.editor, "ed", None)
        await s.commit()
    yield create_app(), plain
    await engine.dispose()


async def _call(c, token, name, args):
    r = await c.post("/mcp",
        headers={"Authorization": f"Bearer {token}"},
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/call",
              "params": {"name": name, "arguments": args}})
    return r.json()


async def test_put_object_type_then_delete(setup):
    app, token = setup
    obj_def = {
        "rid": OBJ_RID, "api_name": "material",
        "lifecycle_status": "ACTIVE", "property_types": {}, "asset_mapping": {},
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r1 = await _call(c, token, "put_object_type", {"definition": obj_def})
        assert "result" in r1, r1
        r2 = await _call(c, token, "delete_object_type", {"rid": OBJ_RID})
        assert "result" in r2, r2


async def test_put_validation_failed(setup):
    app, token = setup
    bad = {"rid": "not-a-rid", "api_name": "UPPER", "lifecycle_status": "ACTIVE"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await _call(c, token, "put_object_type", {"definition": bad})
    assert r["error"]["message"] == "VALIDATION_FAILED"
    codes = {f["code"] for f in r["error"]["data"]["findings"]}
    assert "RID_FORMAT" in codes


async def test_stale_version_rejected(setup):
    app, token = setup
    obj_def = {"rid": OBJ_RID, "api_name": "material", "lifecycle_status": "ACTIVE"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        await _call(c, token, "put_object_type", {"definition": obj_def, "expected_version": 0})
        r = await _call(c, token, "put_object_type",
                        {"definition": obj_def, "expected_version": 0})  # stale!
    assert r["error"]["message"] == "STALE_VERSION"
