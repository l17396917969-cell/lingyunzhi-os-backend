import pytest
from onto_platform.ingestion.tools import (
    AGENT_TOOLS, dispatch_agent_call, AgentToolError,
)
from onto_platform.ingestion.working_registry import WorkingRegistry


def test_agent_tool_list_includes_editor_surface():
    names = {t["function"]["name"] for t in AGENT_TOOLS}
    expected = {
        "working_put_shared_property_type",
        "working_put_object_type",
        "working_put_link_type",
        "working_put_interface_type",
        "working_put_action_type",
        "working_delete_object_type",
        "working_set_asset_mapping",
        "working_import",
        "working_validate",
    }
    assert expected.issubset(names)


def test_dispatch_unknown_name_raises():
    wr = WorkingRegistry.empty()
    with pytest.raises(AgentToolError):
        dispatch_agent_call(wr, "no_such_tool", {}, connection_ids=set())


def test_dispatch_put_object_type_mutates_working_registry():
    wr = WorkingRegistry.empty()
    obj = {
        "rid": "ri.obj.aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        "api_name": "material",
        "lifecycle_status": "ACTIVE",
    }
    dispatch_agent_call(wr, "working_put_object_type",
                        {"definition": obj}, connection_ids=set())
    assert "ri.obj.aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa" in wr.snapshot().object_types
