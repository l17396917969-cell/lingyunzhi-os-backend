# tests/integration/test_connection_pool.py
import re
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.exc import InternalError, OperationalError, DatabaseError
from cryptography.fernet import Fernet
from testcontainers.mysql import MySqlContainer

from onto_platform.connections.store import ConnectionStore, ConnectionKind
from onto_platform.connections.probe import register_connection
from onto_platform.connections.pool import ConnectionPool

pytestmark = pytest.mark.asyncio


@pytest.fixture(scope="module")
def mysql_container():
    with MySqlContainer("mysql:8.0") as mc:
        yield mc


@pytest.fixture
def mysql_dsn(mysql_container):
    raw = mysql_container.get_connection_url()
    return re.sub(r"^mysql(?:\+\w+)?://", "mysql+aiomysql://", raw)


@pytest.fixture
async def factory(postgres_url):
    engine = create_async_engine(postgres_url, future=True)
    f = async_sessionmaker(engine, expire_on_commit=False)
    async with f() as s:
        await s.execute(text("DELETE FROM connections"))
        await s.commit()
    yield f
    await engine.dispose()


async def test_pool_executes_select(factory, mysql_dsn):
    store = ConnectionStore(secret_key=Fernet.generate_key().decode())
    async with factory() as s:
        c = await register_connection(s, store=store, label="x", kind=ConnectionKind.mysql, dsn=mysql_dsn)
        await s.commit()
    pool = ConnectionPool(store=store)
    async with factory() as s:
        async with pool.session(s, c.id) as conn:
            r = await conn.execute(text("SELECT 1"))
            assert r.scalar() == 1
    await pool.dispose_all()


async def test_pool_rejects_writes(factory, mysql_dsn):
    store = ConnectionStore(secret_key=Fernet.generate_key().decode())
    async with factory() as s:
        c = await register_connection(s, store=store, label="ro", kind=ConnectionKind.mysql, dsn=mysql_dsn)
        await s.commit()
    pool = ConnectionPool(store=store)
    async with factory() as s:
        async with pool.session(s, c.id) as conn:
            # Any write (DDL or DML) must be rejected in a read-only session.
            with pytest.raises((InternalError, OperationalError, DatabaseError)):
                await conn.execute(text("INSERT INTO information_schema.TABLES VALUES (1, 2, 3)"))
    await pool.dispose_all()


async def test_pool_invalidates_on_delete(factory, mysql_dsn):
    store = ConnectionStore(secret_key=Fernet.generate_key().decode())
    async with factory() as s:
        c = await register_connection(s, store=store, label="todrop", kind=ConnectionKind.mysql, dsn=mysql_dsn)
        await s.commit()
    pool = ConnectionPool(store=store)
    async with factory() as s:
        async with pool.session(s, c.id):
            pass
    pool.invalidate(c.id)
    assert c.id not in pool._engines
    await pool.dispose_all()
