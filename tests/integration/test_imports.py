import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from onto_platform.proto_models import (
    OntologyRegistry, ObjectTypeDefinition, SharedPropertyTypeDefinition, DataType,
)
from onto_platform.registry.imports import import_into_registry, ImportMode
from onto_platform.registry.crud import ValidationFailedError

pytestmark = pytest.mark.asyncio


SP_RID = "ri.shprop.aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
OBJ_RID_A = "ri.obj.bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
OBJ_RID_B = "ri.obj.cccccccc-cccc-cccc-cccc-cccccccccccc"


def test_replace_mode_overwrites_completely():
    base = OntologyRegistry(
        version="0.1",
        object_types={OBJ_RID_A: ObjectTypeDefinition(rid=OBJ_RID_A, api_name="a")},
    )
    incoming = OntologyRegistry(
        version="0.2",
        object_types={OBJ_RID_B: ObjectTypeDefinition(rid=OBJ_RID_B, api_name="b")},
    )
    out = import_into_registry(base, incoming, mode=ImportMode.replace, connection_ids=set())
    assert OBJ_RID_A not in out.object_types
    assert OBJ_RID_B in out.object_types
    assert out.version == "0.2"


def test_merge_mode_keeps_existing_and_upserts():
    base = OntologyRegistry(
        version="0.1",
        object_types={OBJ_RID_A: ObjectTypeDefinition(rid=OBJ_RID_A, api_name="a")},
    )
    incoming = OntologyRegistry(
        version="0.2",
        object_types={OBJ_RID_B: ObjectTypeDefinition(rid=OBJ_RID_B, api_name="b")},
    )
    out = import_into_registry(base, incoming, mode=ImportMode.merge, connection_ids=set())
    assert OBJ_RID_A in out.object_types
    assert OBJ_RID_B in out.object_types


def test_invalid_incoming_rejected():
    base = OntologyRegistry(version="0.1")
    bad = OntologyRegistry(
        version="bad",
        object_types={"not-a-rid": ObjectTypeDefinition(rid="not-a-rid", api_name="UPPER")},
    )
    with pytest.raises(ValidationFailedError):
        import_into_registry(base, bad, mode=ImportMode.replace, connection_ids=set())
