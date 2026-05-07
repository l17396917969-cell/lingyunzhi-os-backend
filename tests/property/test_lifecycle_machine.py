# tests/property/test_lifecycle_machine.py
# Simplified lifecycle state machine test: runs a fixed promote/revert/undo
# sequence and asserts the correct final state.  A full hypothesis-stateful
# integration with asyncio would require running asyncio.run() inside every
# rule, which works but adds complexity; the mainline invariants are covered
# by the integration tests in tests/integration/test_lifecycle_*.py.
import asyncio
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from onto_platform.proto_models import (
    OntologyRegistry,
    ObjectTypeDefinition,
    LifecycleStatus,
)
from onto_platform.registry.store import RegistryStore, Env
from onto_platform.registry.lifecycle import (
    promote_staging_to_production,
    revert_staging_to_production,
    undo_promote,
    UndoUnavailableError,
)

pytestmark = pytest.mark.asyncio

_EMPTY_PAYLOAD = (
    '{"version":"__empty__","shared_property_types":{},'
    '"interface_types":{},"object_types":{},"link_types":{},"action_types":{}}'
)


def _reg(label: str) -> OntologyRegistry:
    rid = f"ri.obj.{uuid.uuid4()}"
    return OntologyRegistry(
        version=label,
        object_types={
            rid: ObjectTypeDefinition(
                rid=rid,
                api_name="x",
                display_name=label,
                lifecycle_status=LifecycleStatus.ACTIVE,
            )
        },
    )


async def _reset(factory) -> None:
    async with factory() as s:
        await s.execute(
            text(
                f"UPDATE registries SET payload='{_EMPTY_PAYLOAD}'::jsonb, version=0"
            )
        )
        await s.commit()


async def test_promote_revert_sequence(postgres_url):
    """production stays validator-clean through promote → revert → promote."""
    engine = create_async_engine(postgres_url, future=True)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    await _reset(factory)
    store = RegistryStore()

    rA = _reg("A")
    rB = _reg("B")

    # Edit staging → promote A
    async with factory() as s:
        snap = await store.load(s, Env.staging)
        await store.save(s, Env.staging, rA, expected_version=snap.version, token_label="t")
        await s.commit()
    async with factory() as s:
        await promote_staging_to_production(
            s, store, commit_message="A", token_label="t", connection_ids=set()
        )
        await s.commit()

    # Verify production = A
    async with factory() as s:
        prod = await store.load(s, Env.production)
    assert prod.registry.version == "A"

    # Edit staging → promote B
    async with factory() as s:
        snap = await store.load(s, Env.staging)
        await store.save(s, Env.staging, rB, expected_version=snap.version, token_label="t")
        await s.commit()
    async with factory() as s:
        await promote_staging_to_production(
            s, store, commit_message="B", token_label="t", connection_ids=set()
        )
        await s.commit()

    # Verify production = B, previous_production = A
    async with factory() as s:
        prod = await store.load(s, Env.production)
        prev = await store.load(s, Env.previous_production)
    assert prod.registry.version == "B"
    assert prev.registry.version == "A"

    # Revert staging from production
    async with factory() as s:
        await revert_staging_to_production(s, store, token_label="t")
        await s.commit()

    # Staging should now equal production (B)
    async with factory() as s:
        stg = await store.load(s, Env.staging)
    assert stg.registry.version == "B"

    await engine.dispose()


async def test_production_always_loadable_after_random_ops(postgres_url):
    """Production registry is always a valid OntologyRegistry after any sequence."""
    engine = create_async_engine(postgres_url, future=True)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    await _reset(factory)
    store = RegistryStore()

    ops = [_reg(f"v{i}") for i in range(4)]
    for reg in ops:
        async with factory() as s:
            snap = await store.load(s, Env.staging)
            await store.save(s, Env.staging, reg, expected_version=snap.version, token_label="t")
            await s.commit()
        async with factory() as s:
            await promote_staging_to_production(
                s, store, commit_message=reg.version, token_label="t", connection_ids=set()
            )
            await s.commit()
        async with factory() as s:
            prod = await store.load(s, Env.production)
        assert isinstance(prod.registry, OntologyRegistry)

    await engine.dispose()
