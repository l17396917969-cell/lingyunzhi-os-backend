# tests/integration/test_connection_probe.py
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from cryptography.fernet import Fernet
from testcontainers.mysql import MySqlContainer

from onto_platform.connections.probe import probe, ConnectionProbeError, register_connection
from onto_platform.connections.store import ConnectionStore, ConnectionKind

pytestmark = pytest.mark.asyncio


@pytest.fixture(scope="module")
def mysql_container():
    with MySqlContainer("mysql:8.0") as mc:
        yield mc


@pytest.fixture
def mysql_dsn(mysql_container):
    import re
    raw = mysql_container.get_connection_url()
    # Normalise any mysql:// or mysql+pymysql:// to mysql+aiomysql://
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


async def test_probe_success(mysql_dsn):
    ok, err = await probe(mysql_dsn, ConnectionKind.mysql, timeout_s=5)
    assert ok is True
    assert err is None


async def test_probe_failure_redacts_password():
    dsn = "mysql+aiomysql://user:topsecret@127.0.0.1:1/db"
    ok, err = await probe(dsn, ConnectionKind.mysql, timeout_s=2)
    assert ok is False
    assert err is not None
    assert "topsecret" not in err


async def test_register_runs_probe_first(factory, mysql_dsn):
    store = ConnectionStore(secret_key=Fernet.generate_key().decode())
    async with factory() as s:
        c = await register_connection(
            s, store=store, label="logistics_mysql", kind=ConnectionKind.mysql, dsn=mysql_dsn,
        )
        await s.commit()
    assert c.last_probe_ok_at is not None


async def test_register_failed_probe_does_not_persist(factory):
    store = ConnectionStore(secret_key=Fernet.generate_key().decode())
    async with factory() as s:
        with pytest.raises(ConnectionProbeError):
            await register_connection(
                s, store=store, label="bad", kind=ConnectionKind.mysql,
                dsn="mysql+aiomysql://nope:nope@127.0.0.1:1/x",
            )
        rows = (await s.execute(text("SELECT label FROM connections"))).all()
    assert all(r.label != "bad" for r in rows)
