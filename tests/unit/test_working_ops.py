import pytest
from onto_platform.proto_models import (
    SharedPropertyTypeDefinition, ObjectTypeDefinition, LifecycleStatus, DataType,
)
from onto_platform.ingestion.working_registry import WorkingRegistry
from onto_platform.ingestion.working_ops import (
    working_put_shared_property_type, working_put_object_type, working_delete_object_type,
    working_delete_shared_property_type,
)
from onto_platform.registry.crud import ValidationFailedError, ReferencedError


SP_RID = "ri.shprop.aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
OBJ_RID = "ri.obj.bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"


def test_put_shared_property_type_then_object_type():
    wr = WorkingRegistry.empty()
    sp = SharedPropertyTypeDefinition(rid=SP_RID, api_name="cost", data_type=DataType.DT_DOUBLE)
    working_put_shared_property_type(wr, sp, connection_ids=set())
    assert SP_RID in wr.snapshot().shared_property_types
    obj = ObjectTypeDefinition(rid=OBJ_RID, api_name="material", lifecycle_status=LifecycleStatus.ACTIVE)
    working_put_object_type(wr, obj, connection_ids=set())
    assert OBJ_RID in wr.snapshot().object_types


def test_validation_fail_does_not_mutate():
    wr = WorkingRegistry.empty()
    bad = ObjectTypeDefinition(rid="not-a-rid", api_name="UPPER")
    with pytest.raises(ValidationFailedError):
        working_put_object_type(wr, bad, connection_ids=set())
    assert wr.snapshot().object_types == {}


def test_delete_referenced_raises():
    wr = WorkingRegistry.empty()
    sp = SharedPropertyTypeDefinition(rid=SP_RID, api_name="cost", data_type=DataType.DT_DOUBLE)
    working_put_shared_property_type(wr, sp, connection_ids=set())
    obj = ObjectTypeDefinition(
        rid=OBJ_RID, api_name="material",
        property_types={"p": __import__("onto_platform.proto_models", fromlist=["PropertyTypeDefinition"]).PropertyTypeDefinition(
            rid="ri.prop.cccccccc-cccc-cccc-cccc-cccccccccccc",
            api_name="cost", data_type=DataType.DT_DOUBLE,
            inherit_from_shared_property_type_rid=SP_RID,
            physical_column="cost",
        )},
    )
    working_put_object_type(wr, obj, connection_ids=set())
    # SP_RID is referenced by OBJ_RID's property; deleting it must raise ReferencedError
    with pytest.raises(ReferencedError):
        working_delete_shared_property_type(wr, SP_RID)
        # noop — should not happen
