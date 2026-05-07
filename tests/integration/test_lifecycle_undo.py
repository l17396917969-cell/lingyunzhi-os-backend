import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from onto_platform.proto_models import OntologyRegistry, ObjectTypeDefinition
from onto_platform.registry.store import RegistryStore, Env
from onto_platform.registry.lifecycle import (
    promote_staging_to_production, undo_promote, UndoUnavailableError,
)

pytestmark = pytest.mark.asyncio


@pytest.fixture
async def factory(postgres_url):
    engine = create_async_engine(postgres_url, future=True)
    f = async_sessionmaker(engine, expire_on_commit=False)
    async with f() as s:
        await s.execute(text(
            "UPDATE registries SET payload='{\"version\":\"__empty__\","
            "\"shared_property_types\":{},\"interface_types\":{},"
            "\"object_types\":{},\"link_types\":{},\"action_types\":{}}'::jsonb, version=0"
        ))
        await s.commit()
    yield f
    await engine.dispose()


OBJ_RID = "ri.obj.aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"


async def test_undo_unavailable_when_previous_empty(factory):
    store = RegistryStore()
    async with factory() as s:
        with pytest.raises(UndoUnavailableError):
            await undo_promote(s, store, token_label="alice")


async def test_undo_after_promote_restores_old_production(factory):
    store = RegistryStore()
    rA = OntologyRegistry(version="A", object_types={OBJ_RID: ObjectTypeDefinition(rid=OBJ_RID, api_name="x")})
    rB = OntologyRegistry(version="B", object_types={OBJ_RID: ObjectTypeDefinition(rid=OBJ_RID, api_name="x", description="updated")})
    async with factory() as s:
        await store.save(s, Env.staging, rA, expected_version=0, token_label="alice")
        await s.commit()
    async with factory() as s:
        await promote_staging_to_production(s, store, commit_message="A", token_label="alice", connection_ids=set())
        await s.commit()
    async with factory() as s:
        snap = await store.load(s, Env.staging)
        await store.save(s, Env.staging, rB, expected_version=snap.version, token_label="alice")
        await s.commit()
    async with factory() as s:
        await promote_staging_to_production(s, store, commit_message="B", token_label="alice", connection_ids=set())
        await s.commit()
    async with factory() as s:
        await undo_promote(s, store, token_label="alice")
        await s.commit()
    async with factory() as s:
        prod = await store.load(s, Env.production)
        prev = await store.load(s, Env.previous_production)
    assert prod.registry.version == "A"  # restored
    assert prev.registry.version == "__empty__"  # cleared


async def test_undo_twice_returns_unavailable(factory):
    store = RegistryStore()
    rA = OntologyRegistry(version="A", object_types={OBJ_RID: ObjectTypeDefinition(rid=OBJ_RID, api_name="x")})
    async with factory() as s:
        await store.save(s, Env.staging, rA, expected_version=0, token_label="alice")
        await s.commit()
    async with factory() as s:
        await promote_staging_to_production(s, store, commit_message="A", token_label="alice", connection_ids=set())
        await s.commit()
    # Promote loaded an empty prev_production into prev slot, so first undo_promote will report unavailable.
    async with factory() as s:
        with pytest.raises(UndoUnavailableError):
            await undo_promote(s, store, token_label="alice")
