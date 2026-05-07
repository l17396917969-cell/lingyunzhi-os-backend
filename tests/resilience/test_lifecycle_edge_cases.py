# tests/resilience/test_lifecycle_edge_cases.py
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from onto_platform.proto_models import OntologyRegistry, ObjectTypeDefinition, LifecycleStatus
from onto_platform.registry.store import RegistryStore, Env
from onto_platform.registry.lifecycle import (
    promote_staging_to_production, undo_promote, UndoUnavailableError,
)

pytestmark = pytest.mark.asyncio

_EMPTY_PAYLOAD = (
    '{"version":"__empty__","shared_property_types":{},'
    '"interface_types":{},"object_types":{},"link_types":{},"action_types":{}}'
)


@pytest.fixture
async def factory(postgres_url):
    engine = create_async_engine(postgres_url, future=True)
    f = async_sessionmaker(engine, expire_on_commit=False)
    async with f() as s:
        await s.execute(text(
            f"UPDATE registries SET payload='{_EMPTY_PAYLOAD}'::jsonb, version=0"
        ))
        await s.commit()
    yield f
    await engine.dispose()


def _reg(label: str) -> OntologyRegistry:
    rid = "ri.obj.aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    return OntologyRegistry(
        version=label,
        object_types={rid: ObjectTypeDefinition(
            rid=rid, api_name="x", display_name=label,
            lifecycle_status=LifecycleStatus.ACTIVE,
        )},
    )


async def test_promote_undo_promote_sequence(factory):
    store = RegistryStore()
    rA = _reg("A")
    rB = _reg("B")
    async with factory() as s:
        snap = await store.load(s, Env.staging)
        await store.save(s, Env.staging, rA, expected_version=snap.version, token_label="t")
        await s.commit()
    async with factory() as s:
        await promote_staging_to_production(s, store, commit_message="A", token_label="t", connection_ids=set())
        await s.commit()
    async with factory() as s:
        snap = await store.load(s, Env.staging)
        await store.save(s, Env.staging, rB, expected_version=snap.version, token_label="t")
        await s.commit()
    async with factory() as s:
        await promote_staging_to_production(s, store, commit_message="B", token_label="t", connection_ids=set())
        await s.commit()
    async with factory() as s:
        await undo_promote(s, store, token_label="t")
        await s.commit()
    # After undo: production = A, previous_production = empty
    # A new edit + promote should now repopulate previous_production with the
    # just-restored A.
    rC = _reg("C")
    async with factory() as s:
        snap = await store.load(s, Env.staging)
        await store.save(s, Env.staging, rC, expected_version=snap.version, token_label="t")
        await s.commit()
    async with factory() as s:
        await promote_staging_to_production(s, store, commit_message="C", token_label="t", connection_ids=set())
        await s.commit()
    async with factory() as s:
        prod = await store.load(s, Env.production)
        prev = await store.load(s, Env.previous_production)
    assert prod.registry.version == "C"
    assert prev.registry.version == "A"


async def test_undo_twice_in_a_row_unavailable(factory):
    store = RegistryStore()
    rA = _reg("A")
    async with factory() as s:
        snap = await store.load(s, Env.staging)
        await store.save(s, Env.staging, rA, expected_version=snap.version, token_label="t")
        await s.commit()
    async with factory() as s:
        await promote_staging_to_production(s, store, commit_message="A", token_label="t", connection_ids=set())
        await s.commit()
    # First promote backed up the empty production into prev_production, so
    # the very first undo is already unavailable.
    async with factory() as s:
        with pytest.raises(UndoUnavailableError):
            await undo_promote(s, store, token_label="t")
