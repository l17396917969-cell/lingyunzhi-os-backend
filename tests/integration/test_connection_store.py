# tests/integration/test_connection_store.py
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from cryptography.fernet import Fernet

from onto_platform.connections.store import (
    ConnectionStore, Connection, ConnectionKind, ConnectionAlreadyExists,
)

pytestmark = pytest.mark.asyncio


@pytest.fixture
def fernet_key():
    return Fernet.generate_key().decode()


@pytest.fixture
async def factory(postgres_url):
    engine = create_async_engine(postgres_url, future=True)
    f = async_sessionmaker(engine, expire_on_commit=False)
    async with f() as s:
        await s.execute(text("DELETE FROM connections"))
        await s.commit()
    yield f
    await engine.dispose()


async def test_insert_and_load_round_trips_dsn(factory, fernet_key):
    store = ConnectionStore(secret_key=fernet_key)
    async with factory() as s:
        c = await store.insert(
            s, label="logistics", kind=ConnectionKind.mysql,
            dsn="mysql+aiomysql://user:secret@db:3306/logistics",
        )
        await s.commit()
    async with factory() as s:
        loaded = await store.get_by_id(s, c.id)
        plaintext = await store.decrypt_dsn(s, c.id)
    assert loaded.label == "logistics"
    assert loaded.kind is ConnectionKind.mysql
    assert plaintext == "mysql+aiomysql://user:secret@db:3306/logistics"


async def test_insert_duplicate_label_raises(factory, fernet_key):
    store = ConnectionStore(secret_key=fernet_key)
    async with factory() as s:
        await store.insert(s, label="dup", kind=ConnectionKind.postgres, dsn="postgresql://x")
        await s.commit()
    async with factory() as s:
        with pytest.raises(ConnectionAlreadyExists):
            await store.insert(s, label="dup", kind=ConnectionKind.postgres, dsn="postgresql://y")


async def test_dsn_not_visible_in_db_columns_directly(factory, fernet_key):
    store = ConnectionStore(secret_key=fernet_key)
    async with factory() as s:
        await store.insert(s, label="confid", kind=ConnectionKind.postgres,
                           dsn="postgresql://u:topsecretpw@h/db")
        await s.commit()
        rows = (await s.execute(text("SELECT dsn_encrypted FROM connections"))).all()
    for r in rows:
        assert b"topsecretpw" not in r.dsn_encrypted
