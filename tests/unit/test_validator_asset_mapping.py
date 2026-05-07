# tests/unit/test_validator_asset_mapping.py
from onto_platform.proto_models import (
    OntologyRegistry, ObjectTypeDefinition, AssetMapping,
)
from onto_platform.registry.validator import validate, Severity


def _r(obj):
    return OntologyRegistry(version="1", object_types={obj.rid: obj})


def test_unknown_connection_id_flagged():
    obj = ObjectTypeDefinition(
        rid="ri.obj.aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        api_name="x",
        asset_mapping=AssetMapping(read_connection_id="missing", read_asset_path="db.t"),
    )
    findings = validate(_r(obj), connection_ids={"known-conn"})
    codes = {f.code for f in findings}
    assert "ASSET_MAPPING_CONNECTION_NOT_FOUND" in codes


def test_known_connection_id_passes():
    obj = ObjectTypeDefinition(
        rid="ri.obj.aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        api_name="x",
        asset_mapping=AssetMapping(read_connection_id="conn-1", read_asset_path="db.t"),
    )
    findings = validate(_r(obj), connection_ids={"conn-1"})
    codes = {f.code for f in findings}
    assert "ASSET_MAPPING_CONNECTION_NOT_FOUND" not in codes


def test_unbound_object_emits_warning_not_error():
    obj = ObjectTypeDefinition(
        rid="ri.obj.aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", api_name="x",
    )
    findings = validate(_r(obj), connection_ids=set())
    am = [f for f in findings if f.code == "ASSET_MAPPING_EMPTY"]
    assert len(am) == 1
    assert am[0].severity is Severity.WARNING
