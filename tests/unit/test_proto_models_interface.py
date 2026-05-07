# tests/unit/test_proto_models_interface.py
from onto_platform.proto_models import (
    InterfaceCategory, Cardinality, LifecycleStatus,
    ObjectTypeSpec, ObjectLinkRequirement, LinkObjectConstraint,
    InterfaceTypeDefinition,
)


def test_object_type_spec_self():
    s = ObjectTypeSpec(reference_type=ObjectTypeSpec.ReferenceType.SELF)
    j = s.model_dump_json()
    s2 = ObjectTypeSpec.model_validate_json(j)
    assert s == s2


def test_object_interface_with_link_requirement():
    iface = InterfaceTypeDefinition(
        rid="ri.iface.aaa",
        api_name="trackable",
        display_name="Trackable",
        lifecycle_status=LifecycleStatus.ACTIVE,
        category=InterfaceCategory.OBJECT_INTERFACE,
        required_shared_property_type_rids=["ri.shprop.code"],
        link_requirements=[
            ObjectLinkRequirement(
                rid="ri.req.l1",
                api_name="located_at",
                display_name="Located At",
                cardinality=Cardinality.MANY_TO_MANY,
                source_object=ObjectTypeSpec(reference_type=ObjectTypeSpec.ReferenceType.SELF),
                target_object=ObjectTypeSpec(
                    reference_type=ObjectTypeSpec.ReferenceType.EXPLICIT_OBJECT,
                    object_type_rid="ri.obj.warehouse",
                ),
            ),
        ],
    )
    j = iface.model_dump_json()
    iface2 = InterfaceTypeDefinition.model_validate_json(j)
    assert iface == iface2


def test_link_interface_with_constraint():
    iface = InterfaceTypeDefinition(
        rid="ri.iface.bbb",
        api_name="contains",
        category=InterfaceCategory.LINK_INTERFACE,
        object_constraint=LinkObjectConstraint(
            source_object=ObjectTypeSpec(
                reference_type=ObjectTypeSpec.ReferenceType.EXPLICIT_OBJECT,
                object_type_rid="ri.obj.box",
            ),
            target_object=ObjectTypeSpec(
                reference_type=ObjectTypeSpec.ReferenceType.EXPLICIT_OBJECT,
                object_type_rid="ri.obj.item",
            ),
        ),
    )
    j = iface.model_dump_json()
    iface2 = InterfaceTypeDefinition.model_validate_json(j)
    assert iface == iface2
