# tests/unit/test_validator_scaffold.py
from onto_platform.registry.validator import (
    validate, Finding, Severity,
)
from onto_platform.proto_models import empty_registry


def test_validate_empty_registry_returns_empty_list():
    findings = validate(empty_registry(), connection_ids=set())
    assert findings == []


def test_finding_shape():
    f = Finding(
        severity=Severity.ERROR,
        code="RID_FORMAT",
        path="object_types[ri.obj.bad]",
        message="Invalid RID prefix",
    )
    assert f.severity is Severity.ERROR
    assert f.code == "RID_FORMAT"
    assert f.is_error is True


def test_warning_finding_is_not_error():
    f = Finding(
        severity=Severity.WARNING,
        code="ASSET_MAPPING_EMPTY",
        path="object_types[ri.obj.x]",
        message="No AssetMapping configured",
    )
    assert f.is_error is False
