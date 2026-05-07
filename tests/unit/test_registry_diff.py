from onto_platform.proto_models import (
    OntologyRegistry, ObjectTypeDefinition, LifecycleStatus,
)
from onto_platform.registry.diff import compute_diff


OBJ_A = "ri.obj.aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
OBJ_B = "ri.obj.bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"


def _r(**kwargs):
    return OntologyRegistry(version="x", **kwargs)


def test_diff_added_and_removed():
    prod = _r(object_types={OBJ_A: ObjectTypeDefinition(rid=OBJ_A, api_name="a")})
    stag = _r(object_types={OBJ_B: ObjectTypeDefinition(rid=OBJ_B, api_name="b")})
    d = compute_diff(stag, prod)
    assert OBJ_B in d["added"]["object_types"]
    assert OBJ_A in d["removed"]["object_types"]


def test_diff_modified():
    prod = _r(object_types={OBJ_A: ObjectTypeDefinition(rid=OBJ_A, api_name="a", description="orig")})
    stag = _r(object_types={OBJ_A: ObjectTypeDefinition(rid=OBJ_A, api_name="a", description="changed")})
    d = compute_diff(stag, prod)
    assert OBJ_A in d["modified"]["object_types"]


def test_diff_identical_is_empty():
    obj = ObjectTypeDefinition(rid=OBJ_A, api_name="a")
    r = _r(object_types={OBJ_A: obj})
    d = compute_diff(r, r)
    assert all(d[k]["object_types"] == {} for k in ("added", "removed", "modified"))
