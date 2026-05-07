# tests/resilience/test_query_disconnect.py
import asyncio
import pytest
from cryptography.fernet import Fernet
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from testcontainers.mysql import MySqlContainer

from onto_platform.connections.store import ConnectionStore, ConnectionKind
from onto_platform.connections.probe import register_connection
from onto_platform.connections.pool import ConnectionPool
from onto_platform.connections.data_query import query_sql
from onto_platform.proto_models import OntologyRegistry

pytestmark = [pytest.mark.asyncio, pytest.mark.e2e]


@pytest.fixture(scope="module")
def mysql_container():
    with MySqlContainer("mysql:8.0", dialect="pymysql") as mc:
        yield mc


@pytest.fixture
def mysql_dsn(mysql_container):
    return mysql_container.get_connection_url().replace("mysql+pymysql://", "mysql+aiomysql://")


@pytest.fixture
async def factory(postgres_url):
    engine = create_async_engine(postgres_url, future=True)
    f = async_sessionmaker(engine, expire_on_commit=False)
    async with f() as s:
        await s.execute(text("DELETE FROM connections"))
        await s.commit()
    yield f
    await engine.dispose()


async def test_cancel_long_running_query_releases_connection(factory, mysql_dsn):
    store = ConnectionStore(secret_key=Fernet.generate_key().decode())
    pool = ConnectionPool(store=store)
    async with factory() as s:
        c = await register_connection(s, store=store, label="x", kind=ConnectionKind.mysql, dsn=mysql_dsn)
        await s.commit()
    reg = OntologyRegistry(version="x")
    async with factory() as s:
        coro = query_sql(s, pool=pool, connection_id=c.id,
                         sql="SELECT SLEEP(60)", max_rows=1, timeout_ms=2000,
                         registry=reg, dialect="mysql")
        task = asyncio.create_task(coro)
        await asyncio.sleep(0.1)
        task.cancel()
        with pytest.raises((asyncio.CancelledError, Exception)):
            await task
    # The pool's engine should still work after the cancel.
    async with factory() as s:
        async with pool.session(s, c.id) as conn:
            r = await conn.execute(text("SELECT 1"))
            assert r.scalar() == 1
    await pool.dispose_all()
