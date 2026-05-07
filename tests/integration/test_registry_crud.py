import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from onto_platform.proto_models import (
    OntologyRegistry, SharedPropertyTypeDefinition, InterfaceTypeDefinition,
    ObjectTypeDefinition, LinkTypeDefinition, ActionTypeDefinition,
    DataType, InterfaceCategory, Cardinality, AssetMapping,
)
from onto_platform.registry.store import RegistryStore, Env
from onto_platform.registry.crud import (
    put_shared_property_type, delete_shared_property_type,
    put_interface_type, delete_interface_type,
    put_object_type, delete_object_type,
    put_link_type, delete_link_type,
    put_action_type, delete_action_type,
    ValidationFailedError, ReferencedError,
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


SP_RID = "ri.shprop.aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
IFACE_RID = "ri.iface.bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
OBJ_RID = "ri.obj.cccccccc-cccc-cccc-cccc-cccccccccccc"
LINK_RID = "ri.link.dddddddd-dddd-dddd-dddd-dddddddddddd"
ACTION_RID = "ri.action.eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee"


async def test_put_shared_property_type_happy(factory):
    store = RegistryStore()
    sp = SharedPropertyTypeDefinition(rid=SP_RID, api_name="cost", data_type=DataType.DT_DOUBLE)
    async with factory() as s:
        snap = await store.load(s, Env.staging)
        new_reg = put_shared_property_type(snap.registry, sp, connection_ids=set())
    assert SP_RID in new_reg.shared_property_types


async def test_put_shared_property_type_validation_fail(factory):
    store = RegistryStore()
    bad = SharedPropertyTypeDefinition(rid="not-a-rid", api_name="UPPER", data_type=DataType.DT_DOUBLE)
    async with factory() as s:
        snap = await store.load(s, Env.staging)
        with pytest.raises(ValidationFailedError) as ei:
            put_shared_property_type(snap.registry, bad, connection_ids=set())
        codes = {f.code for f in ei.value.findings}
        assert "RID_FORMAT" in codes
        assert "API_NAME_FORMAT" in codes


async def test_delete_shared_property_type_referenced(factory):
    store = RegistryStore()
    sp = SharedPropertyTypeDefinition(rid=SP_RID, api_name="cost", data_type=DataType.DT_DOUBLE)
    iface = InterfaceTypeDefinition(
        rid=IFACE_RID, api_name="trackable",
        category=InterfaceCategory.OBJECT_INTERFACE,
        required_shared_property_type_rids=[SP_RID],
    )
    async with factory() as s:
        snap = await store.load(s, Env.staging)
        r2 = put_shared_property_type(snap.registry, sp, connection_ids=set())
        r3 = put_interface_type(r2, iface, connection_ids=set())
        with pytest.raises(ReferencedError) as ei:
            delete_shared_property_type(r3, SP_RID)
        assert any("required_shared_property_type_rids" in r.path for r in ei.value.referrers)
