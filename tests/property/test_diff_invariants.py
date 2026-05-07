# tests/property/test_diff_invariants.py
from hypothesis import given, strategies as st, settings
from onto_platform.proto_models import (
    OntologyRegistry, ObjectTypeDefinition, LifecycleStatus,
)
from onto_platform.registry.diff import compute_diff


@st.composite
def random_obj_registry(draw):
    n = draw(st.integers(min_value=0, max_value=5))
    rids = [
        f"ri.obj.{i:08d}-aaaa-aaaa-aaaa-aaaaaaaaaaaa" for i in range(n)
    ]
    types = {rid: ObjectTypeDefinition(rid=rid, api_name=f"obj{i}",
                                        lifecycle_status=LifecycleStatus.ACTIVE)
             for i, rid in enumerate(rids)}
    return OntologyRegistry(version="x", object_types=types)


@settings(max_examples=50)
@given(random_obj_registry())
def test_diff_self_is_empty(reg):
    d = compute_diff(reg, reg)
    for k in d:
        assert all(d[k][kind] == {} for kind in d[k])


@settings(max_examples=50)
@given(random_obj_registry(), random_obj_registry())
def test_diff_swap_added_removed(a, b):
    forward = compute_diff(a, b)
    backward = compute_diff(b, a)
    assert forward["added"]["object_types"].keys() == backward["removed"]["object_types"].keys()
    assert forward["removed"]["object_types"].keys() == backward["added"]["object_types"].keys()


@given(random_obj_registry())
def test_registry_json_round_trip(reg):
    text_payload = reg.model_dump_json()
    reloaded = OntologyRegistry.model_validate_json(text_payload)
    assert reloaded == reg
