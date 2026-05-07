# tests/unit/test_validator_structural.py
from onto_platform.proto_models import (
    OntologyRegistry, ObjectTypeDefinition, SharedPropertyTypeDefinition,
    LifecycleStatus, DataType,
)
from onto_platform.registry.validator import validate, Severity


def _registry_with_object(obj):
    return OntologyRegistry(version="1", object_types={obj.rid: obj})


def test_valid_rid_and_api_name_passes():
    obj = ObjectTypeDefinition(
        rid="ri.obj.123e4567-e89b-12d3-a456-426614174000",
        api_name="material",
        lifecycle_status=LifecycleStatus.ACTIVE,
    )
    findings = validate(_registry_with_object(obj), connection_ids=set())
    structural = [f for f in findings if f.code in ("RID_FORMAT", "API_NAME_FORMAT")]
    assert structural == []


def test_invalid_rid_prefix_flagged():
    obj = ObjectTypeDefinition(rid="ri.wrong.x", api_name="x")
    findings = validate(_registry_with_object(obj), connection_ids=set())
    codes = {f.code for f in findings}
    assert "RID_FORMAT" in codes


def test_uppercase_api_name_flagged():
    obj = ObjectTypeDefinition(rid="ri.obj.aaa", api_name="BadName")
    findings = validate(_registry_with_object(obj), connection_ids=set())
    codes = {f.code for f in findings}
    assert "API_NAME_FORMAT" in codes


def test_double_underscore_api_name_flagged():
    obj = ObjectTypeDefinition(rid="ri.obj.aaa", api_name="bad__name")
    findings = validate(_registry_with_object(obj), connection_ids=set())
    codes = {f.code for f in findings}
    assert "API_NAME_FORMAT" in codes


def test_shared_property_kind_prefix_check():
    sp = SharedPropertyTypeDefinition(
        rid="ri.obj.aaa",  # wrong prefix for a SharedPropertyType
        api_name="x", data_type=DataType.DT_STRING,
    )
    r = OntologyRegistry(version="1", shared_property_types={sp.rid: sp})
    findings = validate(r, connection_ids=set())
    codes = {f.code for f in findings}
    assert "RID_FORMAT" in codes
