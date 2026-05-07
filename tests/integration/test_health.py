# tests/integration/test_health.py
import pytest
from httpx import ASGITransport, AsyncClient
from onto_platform.app import create_app

pytestmark = pytest.mark.asyncio


async def test_healthz(postgres_url, monkeypatch):
    monkeypatch.setenv("ONTO_DATABASE_URL", postgres_url)
    monkeypatch.setenv("ONTO_SECRET_KEY", "0" * 44)
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


async def test_readyz_returns_ok_after_migrations(postgres_url, monkeypatch):
    monkeypatch.setenv("ONTO_DATABASE_URL", postgres_url)
    monkeypatch.setenv("ONTO_SECRET_KEY", "0" * 44)
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/readyz")
    assert r.status_code == 200
