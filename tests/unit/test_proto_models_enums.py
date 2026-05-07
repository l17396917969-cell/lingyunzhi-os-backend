# tests/unit/test_proto_models_enums.py
import pytest
from onto_platform.proto_models import (
    DataType, LifecycleStatus, Sensitivity, MaskingStrategy,
    InterfaceCategory, Cardinality, ComplianceConfig, AssetMapping,
)


def test_enum_values_match_proto():
    assert DataType.DT_STRING.value == "DT_STRING"
    assert LifecycleStatus.ACTIVE.value == "ACTIVE"
    assert InterfaceCategory.OBJECT_INTERFACE.value == "OBJECT_INTERFACE"
    assert Cardinality.MANY_TO_MANY.value == "MANY_TO_MANY"


def test_compliance_defaults():
    c = ComplianceConfig()
    assert c.sensitivity is Sensitivity.SENSITIVITY_UNSPECIFIED
    assert c.masking is MaskingStrategy.MASK_NONE


def test_asset_mapping_round_trip():
    am = AssetMapping(
        read_connection_id="conn-1",
        read_asset_path="db.schema.table",
    )
    j = am.model_dump_json()
    am2 = AssetMapping.model_validate_json(j)
    assert am == am2
