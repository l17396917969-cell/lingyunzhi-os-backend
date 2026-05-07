import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from onto_platform.proto_models import OntologyRegistry, ObjectTypeDefinition
from onto_platform.registry.store import RegistryStore, Env
from onto_platform.registry.lifecycle import promote_staging_to_production
from onto_platform.registry.crud import ValidationFailedError

pytestmark = pytest.mark.asyncio


@pytest.fixture
async def factory(postgres_url):
    engine = create_async_engine(postgres_url, future=True)
    f = async_sessionmaker(engine, expire_on_commit=False)
    async with f() as s:
        await s.execute(text(
            "UPDATE registries SET payload='{\"version\":\"__empty__\","
            "\"shared_property_types\":{},\"interface_types\":{},"
            "\"object_types\":{},\"link_types\":{},\"action_types\":{}}'::jsonb, "
            "version=0, last_commit_message=NULL"
        ))
        await s.commit()
    yield f
    await engine.dispose()


OBJ_RID = "ri.obj.aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"


async def test_promote_copies_staging_to_production(factory):
    store = RegistryStore()
    staged = OntologyRegistry(
        version="1.0",
        object_types={OBJ_RID: ObjectTypeDefinition(rid=OBJ_RID, api_name="x")},
    )
    async with factory() as s:
        await store.save(s, Env.staging, staged, expected_version=0, token_label="alice")
        await s.commit()
    async with factory() as s:
        await promote_staging_to_production(s, store, commit_message="initial", token_label="alice", connection_ids=set())
        await s.commit()
    async with factory() as s:
        prod = await store.load(s, Env.production)
        prev = await store.load(s, Env.previous_production)
    assert OBJ_RID in prod.registry.object_types
    assert prev.registry.version == "__empty__"  # nothing to back up first time


async def test_double_promote_keeps_previous_production_correct(factory):
    store = RegistryStore()
    rA = OntologyRegistry(version="A", object_types={OBJ_RID: ObjectTypeDefinition(rid=OBJ_RID, api_name="x")})
    rB = OntologyRegistry(version="B", object_types={OBJ_RID: ObjectTypeDefinition(rid=OBJ_RID, api_name="x", description="updated")})
    async with factory() as s:
        await store.save(s, Env.staging, rA, expected_version=0, token_label="alice")
        await s.commit()
    async with factory() as s:
        await promote_staging_to_production(s, store, commit_message="first", token_label="alice", connection_ids=set())
        await s.commit()
    async with factory() as s:
        snap_st = await store.load(s, Env.staging)
        await store.save(s, Env.staging, rB, expected_version=snap_st.version, token_label="alice")
        await s.commit()
    async with factory() as s:
        await promote_staging_to_production(s, store, commit_message="second", token_label="alice", connection_ids=set())
        await s.commit()
    async with factory() as s:
        prod = await store.load(s, Env.production)
        prev = await store.load(s, Env.previous_production)
    assert prod.registry.version == "B"
    assert prev.registry.version == "A"


async def test_promote_invalid_staging_rejected(factory):
    store = RegistryStore()
    bad = OntologyRegistry(
        version="bad",
        object_types={"not-a-rid": ObjectTypeDefinition(rid="not-a-rid", api_name="X")},
    )
    async with factory() as s:
        # bypass validator by writing payload directly (simulates a stale registry that became invalid)
        await s.execute(text("UPDATE registries SET payload = CAST(:p AS jsonb), version = 1 WHERE env='staging'"),
                        {"p": bad.model_dump_json()})
        await s.commit()
    async with factory() as s:
        with pytest.raises(ValidationFailedError):
            await promote_staging_to_production(s, store, commit_message="x", token_label="alice", connection_ids=set())
