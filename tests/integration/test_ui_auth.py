import pytest
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
    monkeypatch.setenv("ONTO_SECRET_KEY", "0" * 44)
    monkeypatch.setenv("ONTO_UI_COOKIE_SECURE", "false")  # for httpx
    engine = create_async_engine(postgres_url, future=True)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        await s.execute(text("DELETE FROM ui_sessions"))
        await s.execute(text("DELETE FROM api_tokens"))
        await s.commit()
    plain = generate_token()
    async with factory() as s:
        await insert_token(s, plain, Scope.editor, "ui-user", None)
        await s.commit()
    yield create_app(), plain, factory
    await engine.dispose()


async def test_login_with_valid_token_sets_cookie(setup):
    app, token, _ = setup
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post("/admin/login", json={"token": token})
    assert r.status_code == 200
    assert "onto_session" in r.cookies


async def test_login_with_invalid_token_returns_401(setup):
    app, _, _ = setup
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post("/admin/login", json={"token": "op_garbage"})
    assert r.status_code == 401


async def test_cookie_grants_access_to_api_whoami(setup):
    app, token, _ = setup
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        await c.post("/admin/login", json={"token": token})
        r = await c.get("/api/whoami")
    assert r.status_code == 200
    assert r.json()["scope"] == "editor"


async def test_logout_revokes_session(setup):
    app, token, _ = setup
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        await c.post("/admin/login", json={"token": token})
        await c.post("/admin/logout")
        r = await c.get("/api/whoami")
    assert r.status_code == 401
