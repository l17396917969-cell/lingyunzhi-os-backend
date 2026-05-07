from onto_platform.proto_models import (
    OntologyRegistry, ObjectTypeDefinition, LinkTypeDefinition,
    InterfaceTypeDefinition, SharedPropertyTypeDefinition, PropertyTypeDefinition,
    DataType, InterfaceCategory, Cardinality,
)
from onto_platform.registry.refs_scan import find_referrers


def test_finds_link_pointing_at_object():
    obj_rid = "ri.obj.aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    obj = ObjectTypeDefinition(rid=obj_rid, api_name="o")
    lt = LinkTypeDefinition(
        rid="ri.link.bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
        api_name="l",
        source_object_type_rid=obj_rid,
        target_object_type_rid=obj_rid,
        cardinality=Cardinality.ONE_TO_ONE,
    )
    r = OntologyRegistry(version="1", object_types={obj_rid: obj}, link_types={lt.rid: lt})
    referrers = find_referrers(r, obj_rid)
    paths = {ref.path for ref in referrers}
    assert any("source_object_type_rid" in p for p in paths)
    assert any("target_object_type_rid" in p for p in paths)


def test_finds_interface_implementer():
    iface_rid = "ri.iface.aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    iface = InterfaceTypeDefinition(rid=iface_rid, api_name="i", category=InterfaceCategory.OBJECT_INTERFACE)
    obj = ObjectTypeDefinition(
        rid="ri.obj.bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb", api_name="o",
        implements_interface_type_rids=[iface_rid],
    )
    r = OntologyRegistry(version="1", interface_types={iface_rid: iface}, object_types={obj.rid: obj})
    referrers = find_referrers(r, iface_rid)
    assert any("implements_interface_type_rids" in ref.path for ref in referrers)


def test_finds_property_inheritance():
    sp_rid = "ri.shprop.aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    sp = SharedPropertyTypeDefinition(rid=sp_rid, api_name="cost", data_type=DataType.DT_DOUBLE)
    obj = ObjectTypeDefinition(
        rid="ri.obj.bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb", api_name="o",
        property_types={"p": PropertyTypeDefinition(
            rid="ri.prop.cccccccc-cccc-cccc-cccc-cccccccccccc", api_name="cost",
            data_type=DataType.DT_DOUBLE, inherit_from_shared_property_type_rid=sp_rid,
            physical_column="cost",
        )},
    )
    r = OntologyRegistry(version="1", shared_property_types={sp_rid: sp}, object_types={obj.rid: obj})
    referrers = find_referrers(r, sp_rid)
    assert any("inherit_from_shared_property_type_rid" in ref.path for ref in referrers)


def test_no_referrers_for_isolated_entity():
    obj_rid = "ri.obj.aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    obj = ObjectTypeDefinition(rid=obj_rid, api_name="o")
    r = OntologyRegistry(version="1", object_types={obj_rid: obj})
    assert find_referrers(r, obj_rid) == []
