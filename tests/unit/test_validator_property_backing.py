# tests/unit/test_validator_property_backing.py
from onto_platform.proto_models import (
    OntologyRegistry, ObjectTypeDefinition, PropertyTypeDefinition,
    SharedPropertyTypeDefinition, DataType,
)
from onto_platform.registry.validator import validate


def _obj_with(pt: PropertyTypeDefinition) -> ObjectTypeDefinition:
    return ObjectTypeDefinition(
        rid="ri.obj.aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        api_name="x",
        property_types={"k": pt},
    )


def test_neither_backing_set_is_error():
    pt = PropertyTypeDefinition(
        rid="ri.prop.bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
        api_name="p", data_type=DataType.DT_STRING,
    )
    findings = validate(OntologyRegistry(version="1", object_types={"o": _obj_with(pt)}), connection_ids=set())
    codes = {f.code for f in findings}
    assert "PROPERTY_BACKING_MISSING" in codes


def test_both_backings_set_is_error():
    pt = PropertyTypeDefinition(
        rid="ri.prop.bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
        api_name="p", data_type=DataType.DT_STRING,
        physical_column="x", virtual_expression="y",
    )
    findings = validate(OntologyRegistry(version="1", object_types={"o": _obj_with(pt)}), connection_ids=set())
    codes = {f.code for f in findings}
    assert "PROPERTY_BACKING_BOTH_SET" in codes


def test_inherited_type_must_match():
    sp = SharedPropertyTypeDefinition(
        rid="ri.shprop.cccccccc-cccc-cccc-cccc-cccccccccccc",
        api_name="cost", data_type=DataType.DT_DOUBLE,
    )
    pt = PropertyTypeDefinition(
        rid="ri.prop.bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
        api_name="cost", data_type=DataType.DT_INTEGER,  # mismatched!
        inherit_from_shared_property_type_rid=sp.rid,
        physical_column="cost",
    )
    findings = validate(
        OntologyRegistry(version="1", shared_property_types={sp.rid: sp}, object_types={"o": _obj_with(pt)}),
        connection_ids=set(),
    )
    codes = {f.code for f in findings}
    assert "INHERITED_DATA_TYPE_MISMATCH" in codes
