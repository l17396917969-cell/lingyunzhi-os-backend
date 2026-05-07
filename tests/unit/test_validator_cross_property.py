# tests/unit/test_validator_cross_property.py
from onto_platform.proto_models import (
    OntologyRegistry, ObjectTypeDefinition, PropertyTypeDefinition,
    EntityValidationConfig, EntityValidationRule, CrossPropertyExpression,
    DataType,
)
from onto_platform.registry.validator import validate


def _obj(expr: str) -> ObjectTypeDefinition:
    return ObjectTypeDefinition(
        rid="ri.obj.aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        api_name="x",
        property_types={
            "start_time": PropertyTypeDefinition(
                rid="ri.prop.bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
                api_name="start_time", data_type=DataType.DT_TIMESTAMP, physical_column="s",
            ),
            "end_time": PropertyTypeDefinition(
                rid="ri.prop.cccccccc-cccc-cccc-cccc-cccccccccccc",
                api_name="end_time", data_type=DataType.DT_TIMESTAMP, physical_column="e",
            ),
        },
        validation=EntityValidationConfig(rules=[
            EntityValidationRule(error_message="end > start", cross_property=CrossPropertyExpression(expression=expr)),
        ]),
    )


def test_resolved_references_pass():
    obj = _obj("{end_time} > {start_time}")
    findings = validate(OntologyRegistry(version="1", object_types={obj.rid: obj}), connection_ids=set())
    cp = [f for f in findings if f.code == "CROSS_PROPERTY_UNRESOLVED"]
    assert cp == []


def test_unresolved_reference_flagged():
    obj = _obj("{end_time} > {missing_field}")
    findings = validate(OntologyRegistry(version="1", object_types={obj.rid: obj}), connection_ids=set())
    cp = [f for f in findings if f.code == "CROSS_PROPERTY_UNRESOLVED"]
    assert len(cp) == 1
    assert "missing_field" in cp[0].message
