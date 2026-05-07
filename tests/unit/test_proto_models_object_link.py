# tests/unit/test_proto_models_object_link.py
from onto_platform.proto_models import (
    DataType, LifecycleStatus, Cardinality,
    PropertyTypeDefinition, AssetMapping,
    ObjectTypeDefinition, LinkTypeDefinition,
    EntityValidationConfig,
)


def test_object_type_with_properties_round_trip():
    obj = ObjectTypeDefinition(
        rid="ri.obj.material",
        api_name="material",
        display_name="Material",
        lifecycle_status=LifecycleStatus.ACTIVE,
        property_types={
            "material_code": PropertyTypeDefinition(
                rid="ri.prop.mc", api_name="material_code",
                data_type=DataType.DT_STRING, physical_column="material_code",
            ),
        },
        implements_interface_type_rids=["ri.iface.trackable"],
        primary_key_property_type_rids=["ri.prop.mc"],
        asset_mapping=AssetMapping(
            read_connection_id="conn-1",
            read_asset_path="logistics.MD_MATERIAL",
        ),
    )
    j = obj.model_dump_json()
    obj2 = ObjectTypeDefinition.model_validate_json(j)
    assert obj == obj2


def test_link_type_round_trip():
    lt = LinkTypeDefinition(
        rid="ri.link.stocked_at",
        api_name="material_stocked_at",
        source_object_type_rid="ri.obj.material",
        target_object_type_rid="ri.obj.warehouse",
        cardinality=Cardinality.MANY_TO_MANY,
    )
    j = lt.model_dump_json()
    lt2 = LinkTypeDefinition.model_validate_json(j)
    assert lt2.source_object_type_rid == "ri.obj.material"
    assert lt2.cardinality == Cardinality.MANY_TO_MANY
