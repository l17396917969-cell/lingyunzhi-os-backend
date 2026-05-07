# tests/unit/test_describe_bound_asset.py
import pytest
from onto_platform.proto_models import (
    OntologyRegistry, ObjectTypeDefinition, PropertyTypeDefinition,
    AssetMapping, ComplianceConfig, Sensitivity, MaskingStrategy, DataType,
)
from onto_platform.connections.data_query import (
    describe_bound_asset, BoundAssetNotFoundError, AssetUnboundError,
)


def _registry():
    obj = ObjectTypeDefinition(
        rid="ri.obj.aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        api_name="material",
        property_types={
            "code": PropertyTypeDefinition(
                rid="ri.prop.bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
                api_name="code", data_type=DataType.DT_STRING, physical_column="material_code",
            ),
            "cost_price": PropertyTypeDefinition(
                rid="ri.prop.cccccccc-cccc-cccc-cccc-cccccccccccc",
                api_name="cost_price", data_type=DataType.DT_DOUBLE,
                physical_column="cost_price",
                compliance=ComplianceConfig(
                    sensitivity=Sensitivity.CONFIDENTIAL,
                    masking=MaskingStrategy.MASK_REDACT_FULL,
                ),
            ),
        },
        asset_mapping=AssetMapping(read_connection_id="conn-1", read_asset_path="logistics.MD_MATERIAL"),
    )
    return OntologyRegistry(version="1", object_types={obj.rid: obj})


def test_describe_returns_columns():
    r = _registry()
    out = describe_bound_asset(r, "ri.obj.aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    assert out["connection_id"] == "conn-1"
    assert out["asset_path"] == "logistics.MD_MATERIAL"
    cols_by_api = {c["api_name"]: c for c in out["columns"]}
    assert cols_by_api["code"]["physical_column"] == "material_code"
    assert cols_by_api["cost_price"]["sensitivity"] == "CONFIDENTIAL"
    assert cols_by_api["cost_price"]["masking_strategy"] == "MASK_REDACT_FULL"


def test_describe_unknown_rid_raises():
    r = _registry()
    with pytest.raises(BoundAssetNotFoundError):
        describe_bound_asset(r, "ri.obj.deadbeef-dead-beef-dead-beefdeadbeef")


def test_describe_unbound_entity_raises():
    obj = ObjectTypeDefinition(rid="ri.obj.aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", api_name="x")
    r = OntologyRegistry(version="1", object_types={obj.rid: obj})
    with pytest.raises(AssetUnboundError):
        describe_bound_asset(r, obj.rid)
