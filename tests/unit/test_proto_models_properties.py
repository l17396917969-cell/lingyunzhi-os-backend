# tests/unit/test_proto_models_properties.py
import pytest
from onto_platform.proto_models import (
    DataType, LifecycleStatus, Sensitivity, MaskingStrategy,
    ComplianceConfig, PropertyValidationConfig,
    SharedPropertyTypeDefinition, PropertyTypeDefinition,
)


def test_shared_property_round_trip():
    sp = SharedPropertyTypeDefinition(
        rid="ri.shprop.aaa",
        api_name="cost_price",
        display_name="Cost Price",
        description="Unit cost",
        lifecycle_status=LifecycleStatus.ACTIVE,
        data_type=DataType.DT_DOUBLE,
        widget={"text": {"multiline": False, "placeholder": ""}},
        compliance=ComplianceConfig(
            sensitivity=Sensitivity.CONFIDENTIAL,
            masking=MaskingStrategy.MASK_REDACT_FULL,
        ),
    )
    j = sp.model_dump_json()
    sp2 = SharedPropertyTypeDefinition.model_validate_json(j)
    assert sp == sp2


def test_property_type_oneof_backing_required():
    # neither physical_column nor virtual_expression set -> still constructible at the
    # pydantic level (proto's `oneof` is enforced by the validator, not the type)
    pt = PropertyTypeDefinition(
        rid="ri.prop.bbb", api_name="x", data_type=DataType.DT_STRING,
    )
    assert pt.physical_column == ""
    assert pt.virtual_expression == ""


def test_property_type_with_physical_column():
    pt = PropertyTypeDefinition(
        rid="ri.prop.ccc", api_name="y",
        data_type=DataType.DT_INTEGER,
        physical_column="qty",
    )
    j = pt.model_dump_json()
    pt2 = PropertyTypeDefinition.model_validate_json(j)
    assert pt2.physical_column == "qty"
