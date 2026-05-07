# tests/property/test_validator_invariants.py
from hypothesis import given, strategies as st
from onto_platform.proto_models import OntologyRegistry
from onto_platform.registry.validator import validate


@st.composite
def random_registry(draw):
    return OntologyRegistry(
        version=draw(st.text(min_size=0, max_size=20)),
        shared_property_types={},
        interface_types={},
        object_types={},
        link_types={},
        action_types={},
    )


@given(random_registry())
def test_validator_never_crashes(reg):
    findings = validate(reg, connection_ids=set())
    assert isinstance(findings, list)


@given(st.text(min_size=0, max_size=200))
def test_validator_handles_arbitrary_version_strings(version_str):
    r = OntologyRegistry(version=version_str)
    findings = validate(r, connection_ids=set())
    assert isinstance(findings, list)
