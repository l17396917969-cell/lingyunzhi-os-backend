import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from onto_platform.proto_models import OntologyRegistry, ObjectTypeDefinition
from onto_platform.registry.store import (
    Env, RegistryStore, StaleVersionError,
)

pytestmark = pytest.mark.asyncio


@pytest.fixture
async def factory(postgres_url):
    engine = create_async_engine(postgres_url, future=True)
    f = async_sessionmaker(engine, expire_on_commit=False)
    # Reset registries to empty for this test
    async with f() as s:
        await s.execute(text(
            "UPDATE registries SET payload='{\"version\":\"__empty__\","
            "\"shared_property_types\":{},\"interface_types\":{},"
            "\"object_types\":{},\"link_types\":{},\"action_types\":{}}'::jsonb, "
            "version=0, last_commit_message=NULL, updated_by_token_label=NULL"
        ))
        await s.commit()
    yield f
    await engine.dispose()


async def test_load_empty_registry(factory):
    store = RegistryStore()
    async with factory() as s:
        snap = await store.load(s, Env.staging)
    assert snap.registry.version == "__empty__"
    assert snap.version == 0


async def test_save_increments_version(factory):
    store = RegistryStore()
    async with factory() as s:
        snap = await store.load(s, Env.staging)
        new_reg = OntologyRegistry(
            version="0.1", object_types={"ri.obj.x": ObjectTypeDefinition(rid="ri.obj.x", api_name="x")}
        )
        new_version = await store.save(
            s, Env.staging, new_reg, expected_version=snap.version, token_label="alice",
        )
        await s.commit()
    assert new_version == snap.version + 1


async def test_save_with_wrong_expected_version_raises(factory):
    store = RegistryStore()
    async with factory() as s:
        snap = await store.load(s, Env.staging)
    new_reg = OntologyRegistry(version="0.1")
    async with factory() as s:
        with pytest.raises(StaleVersionError) as ei:
            await store.save(s, Env.staging, new_reg, expected_version=snap.version + 99, token_label="alice")
        assert ei.value.current_version == snap.version
