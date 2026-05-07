# tests/integration/test_mcp_tools_admin.py
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from cryptography.fernet import Fernet

from onto_platform.app import create_app
from onto_platform.auth import Scope, generate_token
from onto_platform.token_store import insert_token

pytestmark = pytest.mark.asyncio


@pytest.fixture
async def setup(postgres_url, monkeypatch):
    secret = Fernet.generate_key().decode()
    monkeypatch.setenv("ONTO_DATABASE_URL", postgres_url)
    monkeypatch.setenv("ONTO_SECRET_KEY", secret)
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
        await insert_token(s, plain, Scope.admin, "boss", None)
        await s.commit()
    yield create_app(), plain, factory
    await engine.dispose()


async def _call(c, token, name, args=None):
    r = await c.post("/mcp",
        headers={"Authorization": f"Bearer {token}"},
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/call",
              "params": {"name": name, "arguments": args or {}}})
    return r.json()


async def test_mint_then_revoke_then_list(setup):
    app, token, _ = setup
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        m = await _call(c, token, "mint_token", {"scope": "read", "label": "alice"})
        new_token = m["result"]["structuredContent"]["token"]
        new_token_id = m["result"]["structuredContent"]["token_id"]
        assert new_token.startswith("op_")
        listed = (await _call(c, token, "list_tokens"))["result"]["structuredContent"]["items"]
        assert any(t["label"] == "alice" for t in listed)
        await _call(c, token, "revoke_token", {"token_id": new_token_id})


async def test_promote_then_undo(setup):
    app, token, factory = setup
    # Import a registry with a real version string so promote/undo works correctly
    reg_v1 = {
        "version": "v1",
        "shared_property_types": {}, "interface_types": {}, "link_types": {}, "action_types": {},
        "object_types": {
            "ri.obj.aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa": {
                "rid": "ri.obj.aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                "api_name": "x", "lifecycle_status": "ACTIVE",
            }
        },
    }
    reg_v2 = {
        "version": "v2",
        "shared_property_types": {}, "interface_types": {}, "link_types": {}, "action_types": {},
        "object_types": {
            "ri.obj.bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb": {
                "rid": "ri.obj.bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
                "api_name": "y", "lifecycle_status": "ACTIVE",
            }
        },
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        # First promote: staging(v1) -> production, empty -> previous_production
        await _call(c, token, "import_full_registry_to_staging",
                    {"registry": reg_v1, "mode": "replace"})
        r1 = await _call(c, token, "promote_staging_to_production", {"commit_message": "first"})
        assert "result" in r1, r1
        # Second promote: staging(v2) -> production, v1 -> previous_production
        await _call(c, token, "import_full_registry_to_staging",
                    {"registry": reg_v2, "mode": "replace"})
        r2 = await _call(c, token, "promote_staging_to_production", {"commit_message": "second"})
        assert "result" in r2, r2
        # Now previous_production has v1 (non-__empty__) → undo is available
        u = await _call(c, token, "undo_promote", {})
        assert "result" in u, u


async def test_undo_unavailable_when_empty(setup):
    app, token, _ = setup
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await _call(c, token, "undo_promote", {})
    assert r["error"]["message"] == "UNDO_UNAVAILABLE"
