import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from onto_platform.proto_models import OntologyRegistry, ObjectTypeDefinition
from onto_platform.registry.store import RegistryStore, Env
from onto_platform.registry.lifecycle import revert_staging_to_production

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


async def test_revert_overwrites_staging_with_production(factory):
    store = RegistryStore()
    prod_payload = OntologyRegistry(
        version="prod-1",
        object_types={OBJ_RID: ObjectTypeDefinition(rid=OBJ_RID, api_name="prod")},
    )
    staged_payload = OntologyRegistry(
        version="staging-edit",
        object_types={OBJ_RID: ObjectTypeDefinition(rid=OBJ_RID, api_name="edited")},
    )
    async with factory() as s:
        await s.execute(text("UPDATE registries SET payload=CAST(:p AS jsonb), version=1 WHERE env='production'"),
                        {"p": prod_payload.model_dump_json()})
        await s.execute(text("UPDATE registries SET payload=CAST(:p AS jsonb), version=2 WHERE env='staging'"),
                        {"p": staged_payload.model_dump_json()})
        await s.commit()
    async with factory() as s:
        await revert_staging_to_production(s, store, token_label="alice")
        await s.commit()
    async with factory() as s:
        staged = await store.load(s, Env.staging)
        prod = await store.load(s, Env.production)
        prev = await store.load(s, Env.previous_production)
    assert staged.registry.version == "prod-1"
    assert prod.registry.version == "prod-1"
    assert prev.registry.version == "__empty__"  # untouched
