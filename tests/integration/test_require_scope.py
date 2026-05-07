# tests/integration/test_require_scope.py
import pytest
from fastapi import FastAPI, Depends
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from onto_platform.auth import Scope, generate_token, require_scope, RequestPrincipal
from onto_platform.token_store import insert_token

pytestmark = pytest.mark.asyncio


@pytest.fixture
async def app_and_factory(postgres_url):
    engine = create_async_engine(postgres_url, future=True)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        await s.execute(text("DELETE FROM api_tokens"))
        await s.commit()
    app = FastAPI()

    async def session_provider():
        async with factory() as s:
            yield s

    @app.get("/read-only")
    async def r(p: RequestPrincipal = Depends(require_scope(Scope.read, session_provider))):
        return {"label": p.label, "scope": p.scope.name}

    @app.get("/admin-only")
    async def a(p: RequestPrincipal = Depends(require_scope(Scope.admin, session_provider))):
        return {"label": p.label, "scope": p.scope.name}

    yield app, factory
    await engine.dispose()


async def test_no_token_returns_401(app_and_factory):
    app, _ = app_and_factory
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/read-only")
    assert r.status_code == 401


async def test_read_token_can_call_read_endpoint(app_and_factory):
    app, factory = app_and_factory
    plaintext = generate_token()
    async with factory() as s:
        await insert_token(s, plaintext, Scope.read, "tester", None)
        await s.commit()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/read-only", headers={"Authorization": f"Bearer {plaintext}"})
    assert r.status_code == 200
    assert r.json()["scope"] == "read"


async def test_read_token_cannot_call_admin_endpoint(app_and_factory):
    app, factory = app_and_factory
    plaintext = generate_token()
    async with factory() as s:
        await insert_token(s, plaintext, Scope.read, "tester", None)
        await s.commit()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/admin-only", headers={"Authorization": f"Bearer {plaintext}"})
    assert r.status_code == 403
