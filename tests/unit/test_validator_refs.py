# tests/unit/test_validator_refs.py
from onto_platform.proto_models import (
    OntologyRegistry, SharedPropertyTypeDefinition, PropertyTypeDefinition,
    ObjectTypeDefinition, LinkTypeDefinition, InterfaceTypeDefinition,
    DataType, LifecycleStatus, InterfaceCategory, Cardinality,
)
from onto_platform.registry.validator import validate


def _r(**kwargs):
    return OntologyRegistry(version="1", **kwargs)


def test_inherit_from_shared_property_resolves():
    sp = SharedPropertyTypeDefinition(rid="ri.shprop.aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", api_name="cost", data_type=DataType.DT_DOUBLE)
    obj = ObjectTypeDefinition(
        rid="ri.obj.bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
        api_name="material",
        property_types={
            "p": PropertyTypeDefinition(
                rid="ri.prop.cccccccc-cccc-cccc-cccc-cccccccccccc",
                api_name="cost", data_type=DataType.DT_DOUBLE,
                inherit_from_shared_property_type_rid=sp.rid,
                physical_column="cost",
            ),
        },
    )
    findings = validate(_r(shared_property_types={sp.rid: sp}, object_types={obj.rid: obj}), connection_ids=set())
    refs = [f for f in findings if f.code == "REF_NOT_FOUND"]
    assert refs == []


def test_dangling_inherit_from_shared_property_flagged():
    obj = ObjectTypeDefinition(
        rid="ri.obj.bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
        api_name="material",
        property_types={
            "p": PropertyTypeDefinition(
                rid="ri.prop.cccccccc-cccc-cccc-cccc-cccccccccccc",
                api_name="cost", data_type=DataType.DT_DOUBLE,
                inherit_from_shared_property_type_rid="ri.shprop.deadbeef-dead-beef-dead-beefdeadbeef",
                physical_column="cost",
            ),
        },
    )
    findings = validate(_r(object_types={obj.rid: obj}), connection_ids=set())
    refs = [f for f in findings if f.code == "REF_NOT_FOUND"]
    assert any("inherit_from_shared_property_type_rid" in f.path for f in refs)


def test_dangling_link_source_flagged():
    lt = LinkTypeDefinition(
        rid="ri.link.dddddddd-dddd-dddd-dddd-dddddddddddd",
        api_name="rel",
        source_object_type_rid="ri.obj.deadbeef-dead-beef-dead-beefdeadbeef",
        target_object_type_rid="ri.obj.deadbeef-dead-beef-dead-beefdeadbeef",
        cardinality=Cardinality.ONE_TO_ONE,
    )
    findings = validate(_r(link_types={lt.rid: lt}), connection_ids=set())
    refs = [f for f in findings if f.code == "REF_NOT_FOUND"]
    assert any("source_object_type_rid" in f.path for f in refs)
    assert any("target_object_type_rid" in f.path for f in refs)
