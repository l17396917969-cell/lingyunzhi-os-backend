# tests/unit/test_validator_interface_category.py
from onto_platform.proto_models import (
    OntologyRegistry, InterfaceTypeDefinition, InterfaceCategory,
    LinkObjectConstraint, ObjectTypeSpec, ObjectLinkRequirement, Cardinality,
)
from onto_platform.registry.validator import validate


def test_object_interface_with_object_constraint_is_invalid():
    iface = InterfaceTypeDefinition(
        rid="ri.iface.aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        api_name="bad",
        category=InterfaceCategory.OBJECT_INTERFACE,
        object_constraint=LinkObjectConstraint(),
    )
    findings = validate(OntologyRegistry(version="1", interface_types={iface.rid: iface}), connection_ids=set())
    codes = {f.code for f in findings}
    assert "INTERFACE_CATEGORY_MISMATCH" in codes


def test_link_interface_with_link_requirements_is_invalid():
    iface = InterfaceTypeDefinition(
        rid="ri.iface.bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
        api_name="bad",
        category=InterfaceCategory.LINK_INTERFACE,
        link_requirements=[ObjectLinkRequirement(rid="ri.req.x", api_name="r", cardinality=Cardinality.ONE_TO_ONE)],
    )
    findings = validate(OntologyRegistry(version="1", interface_types={iface.rid: iface}), connection_ids=set())
    codes = {f.code for f in findings}
    assert "INTERFACE_CATEGORY_MISMATCH" in codes


def test_extends_across_categories_is_invalid():
    obj_iface = InterfaceTypeDefinition(rid="ri.iface.aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", api_name="o", category=InterfaceCategory.OBJECT_INTERFACE)
    link_iface = InterfaceTypeDefinition(
        rid="ri.iface.bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb", api_name="l",
        category=InterfaceCategory.LINK_INTERFACE,
        extends_interface_type_rids=[obj_iface.rid],
    )
    findings = validate(OntologyRegistry(version="1", interface_types={obj_iface.rid: obj_iface, link_iface.rid: link_iface}), connection_ids=set())
    codes = {f.code for f in findings}
    assert "INTERFACE_EXTENDS_CATEGORY_MISMATCH" in codes


def test_extends_cycle_flagged():
    a = InterfaceTypeDefinition(
        rid="ri.iface.aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", api_name="a",
        category=InterfaceCategory.OBJECT_INTERFACE,
        extends_interface_type_rids=["ri.iface.bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"],
    )
    b = InterfaceTypeDefinition(
        rid="ri.iface.bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb", api_name="b",
        category=InterfaceCategory.OBJECT_INTERFACE,
        extends_interface_type_rids=[a.rid],
    )
    findings = validate(OntologyRegistry(version="1", interface_types={a.rid: a, b.rid: b}), connection_ids=set())
    codes = {f.code for f in findings}
    assert "INTERFACE_EXTENDS_CYCLE" in codes
