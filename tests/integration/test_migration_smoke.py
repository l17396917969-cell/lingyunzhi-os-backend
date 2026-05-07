import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

pytestmark = pytest.mark.asyncio


async def test_migration_creates_all_tables(postgres_url):
    engine = create_async_engine(postgres_url, future=True)
    async with engine.connect() as conn:
        result = await conn.execute(text(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema='public' ORDER BY table_name"
        ))
        names = [row[0] for row in result]
    await engine.dispose()
    assert {"registries", "api_tokens", "connections", "audit_log"}.issubset(set(names))


async def test_three_registries_rows_seeded(postgres_url):
    engine = create_async_engine(postgres_url, future=True)
    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT env FROM registries ORDER BY env"))
        envs = [row[0] for row in result]
    await engine.dispose()
    assert envs == ["previous_production", "production", "staging"]
