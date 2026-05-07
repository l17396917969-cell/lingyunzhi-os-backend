import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

pytestmark = pytest.mark.asyncio


async def test_ingestion_tables_present(postgres_url):
    engine = create_async_engine(postgres_url, future=True)
    async with engine.connect() as conn:
        rows = await conn.execute(text(
            "SELECT table_name FROM information_schema.tables WHERE table_schema='public'"
        ))
        names = {r[0] for r in rows}
    await engine.dispose()
    assert {"ingestion_uploads", "ingestion_jobs"}.issubset(names)
