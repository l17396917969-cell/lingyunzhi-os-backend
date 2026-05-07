import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

pytestmark = pytest.mark.asyncio


async def test_chat_tables_exist(postgres_url):
    eng = create_async_engine(postgres_url, future=True)
    try:
        async with eng.connect() as c:
            r = await c.execute(text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema='public' AND table_name IN "
                "('chat_sessions','chat_messages')"
            ))
            names = {row[0] for row in r}
            assert names == {"chat_sessions", "chat_messages"}

            r2 = await c.execute(text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name='chat_sessions' "
                "AND column_name IN ('pre_session_registry','pre_session_version','status','last_turn_at')"
            ))
            cols = {row[0] for row in r2}
            assert cols == {"pre_session_registry", "pre_session_version", "status", "last_turn_at"}

            r3 = await c.execute(text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name='ingestion_jobs' AND column_name='chat_session_id'"
            ))
            assert r3.scalar_one() == "chat_session_id"
    finally:
        await eng.dispose()
