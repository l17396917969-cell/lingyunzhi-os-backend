import pytest
from sqlalchemy import text
from onto_platform.db import make_engine, get_sessionmaker

pytestmark = pytest.mark.asyncio


async def test_engine_connects(postgres_url):
    engine = make_engine(postgres_url)
    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT 1"))
        assert result.scalar() == 1
    await engine.dispose()


async def test_sessionmaker_yields_session(postgres_url):
    engine = make_engine(postgres_url)
    Session = get_sessionmaker(engine)
    async with Session() as session:
        result = await session.execute(text("SELECT 2"))
        assert result.scalar() == 2
    await engine.dispose()
