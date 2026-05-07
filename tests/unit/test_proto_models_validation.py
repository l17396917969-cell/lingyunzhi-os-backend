# tests/unit/test_proto_models_validation.py
from onto_platform.proto_models import (
    PropertyValidationConfig, PropertyValidationRule, NotNullRule,
    RangeRule, LengthRule, PatternRule, EnumRule, EnumValue,
    EntityValidationConfig, EntityValidationRule, CrossPropertyExpression,
)


def test_property_validation_round_trip():
    cfg = PropertyValidationConfig(rules=[
        PropertyValidationRule(error_message="cannot be null", not_null=NotNullRule()),
        PropertyValidationRule(error_message="too short", length=LengthRule(min_length=1)),
    ])
    j = cfg.model_dump_json()
    cfg2 = PropertyValidationConfig.model_validate_json(j)
    assert cfg == cfg2


def test_entity_cross_property_round_trip():
    cfg = EntityValidationConfig(rules=[
        EntityValidationRule(
            error_message="end must be after start",
            cross_property=CrossPropertyExpression(expression="{end_time} > {start_time}"),
        ),
    ])
    j = cfg.model_dump_json()
    cfg2 = EntityValidationConfig.model_validate_json(j)
    assert cfg == cfg2
