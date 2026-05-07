# tests/unit/test_masking_resolver.py
from onto_platform.proto_models import (
    OntologyRegistry, ObjectTypeDefinition, PropertyTypeDefinition,
    SharedPropertyTypeDefinition, AssetMapping, ComplianceConfig,
    Sensitivity, MaskingStrategy, DataType,
)
from onto_platform.connections.masking import (
    MaskingResolver, ResolvedColumn,
)


def _registry_with_masked_cost():
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
        asset_mapping=AssetMapping(read_connection_id="conn", read_asset_path="MD_MATERIAL"),
    )
    return OntologyRegistry(version="1", object_types={obj.rid: obj})


def test_direct_select_resolves():
    r = _registry_with_masked_cost()
    res = MaskingResolver(r, dialect="mysql").resolve("SELECT material_code, cost_price FROM MD_MATERIAL")
    assert res[0] == ResolvedColumn(name="material_code", sensitivity=Sensitivity.SENSITIVITY_UNSPECIFIED, masking=MaskingStrategy.MASK_NONE)
    assert res[1].sensitivity is Sensitivity.CONFIDENTIAL
    assert res[1].masking is MaskingStrategy.MASK_REDACT_FULL


def test_aliased_select_still_resolves():
    r = _registry_with_masked_cost()
    res = MaskingResolver(r, dialect="mysql").resolve(
        "SELECT cost_price AS foo FROM MD_MATERIAL"
    )
    assert res[0].name == "foo"
    assert res[0].masking is MaskingStrategy.MASK_REDACT_FULL


def test_derived_expression_inherits_highest_sensitivity():
    r = _registry_with_masked_cost()
    res = MaskingResolver(r, dialect="mysql").resolve(
        "SELECT cost_price * 1.1 AS bar FROM MD_MATERIAL"
    )
    assert res[0].masking is MaskingStrategy.MASK_REDACT_FULL


def test_aggregation_inherits_sensitivity():
    r = _registry_with_masked_cost()
    res = MaskingResolver(r, dialect="mysql").resolve(
        "SELECT MIN(cost_price) AS m, COUNT(*) AS n FROM MD_MATERIAL"
    )
    assert res[0].masking is MaskingStrategy.MASK_REDACT_FULL
    assert res[1].masking is MaskingStrategy.MASK_NONE


def test_unresolved_column_marked():
    r = _registry_with_masked_cost()
    res = MaskingResolver(r, dialect="mysql").resolve(
        "SELECT some_unknown_col FROM MD_MATERIAL"
    )
    assert res[0].is_resolved is False
