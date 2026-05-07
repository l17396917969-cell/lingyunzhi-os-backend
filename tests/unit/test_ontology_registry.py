# tests/unit/test_ontology_registry.py
import json
from onto_platform.proto_models import (
    OntologyRegistry, EMPTY_REGISTRY_VERSION, empty_registry,
    ObjectTypeDefinition, LifecycleStatus,
)


def test_empty_registry_has_sentinel():
    r = empty_registry()
    assert r.version == EMPTY_REGISTRY_VERSION
    assert r.shared_property_types == {}
    assert r.interface_types == {}
    assert r.object_types == {}
    assert r.link_types == {}
    assert r.action_types == {}


def test_registry_round_trip_with_one_object():
    obj = ObjectTypeDefinition(
        rid="ri.obj.aaa", api_name="thing",
        lifecycle_status=LifecycleStatus.ACTIVE,
    )
    r = OntologyRegistry(version="1.0.0", object_types={obj.rid: obj})
    j = r.model_dump_json()
    r2 = OntologyRegistry.model_validate_json(j)
    assert r == r2


def test_registry_serializes_to_compact_json():
    r = empty_registry()
    j = json.loads(r.model_dump_json())
    assert set(j.keys()) == {
        "version", "shared_property_types", "interface_types",
        "object_types", "link_types", "action_types",
    }
