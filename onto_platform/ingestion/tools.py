from __future__ import annotations

from typing import Any

from onto_platform.proto_models import (
    ActionTypeDefinition,
    AssetMapping,
    InterfaceTypeDefinition,
    LinkTypeDefinition,
    ObjectTypeDefinition,
    OntologyRegistry,
    SharedPropertyTypeDefinition,
)
from onto_platform.registry.imports import ImportMode
from onto_platform.registry.validator import validate
from onto_platform.ingestion import working_ops as wops
from onto_platform.ingestion.working_registry import WorkingRegistry


class AgentToolError(Exception):
    pass


def _tool(name: str, description: str, schema: dict[str, Any]) -> dict[str, Any]:
    """OpenAI-format tool spec (LiteLLM accepts this for all providers)."""
    return {
        "type": "function",
        "function": {"name": name, "description": description, "parameters": schema},
    }


_DEF: dict[str, Any] = {"type": "object"}
_RID: dict[str, Any] = {"type": "string"}


AGENT_TOOLS: list[dict[str, Any]] = [
    _tool(
        "working_put_shared_property_type",
        "Upsert a SharedPropertyType.",
        {"type": "object", "properties": {"definition": _DEF}, "required": ["definition"]},
    ),
    _tool(
        "working_put_interface_type",
        "Upsert an InterfaceType.",
        {"type": "object", "properties": {"definition": _DEF}, "required": ["definition"]},
    ),
    _tool(
        "working_put_object_type",
        "Upsert an ObjectType (with embedded property_types).",
        {"type": "object", "properties": {"definition": _DEF}, "required": ["definition"]},
    ),
    _tool(
        "working_put_link_type",
        "Upsert a LinkType.",
        {"type": "object", "properties": {"definition": _DEF}, "required": ["definition"]},
    ),
    _tool(
        "working_put_action_type",
        "Upsert an ActionType.",
        {"type": "object", "properties": {"definition": _DEF}, "required": ["definition"]},
    ),
    _tool(
        "working_delete_shared_property_type",
        "Delete a SharedPropertyType (refuses if referenced).",
        {"type": "object", "properties": {"rid": _RID}, "required": ["rid"]},
    ),
    _tool(
        "working_delete_interface_type",
        "Delete an InterfaceType (refuses if referenced).",
        {"type": "object", "properties": {"rid": _RID}, "required": ["rid"]},
    ),
    _tool(
        "working_delete_object_type",
        "Delete an ObjectType (refuses if referenced).",
        {"type": "object", "properties": {"rid": _RID}, "required": ["rid"]},
    ),
    _tool(
        "working_delete_link_type",
        "Delete a LinkType (refuses if referenced).",
        {"type": "object", "properties": {"rid": _RID}, "required": ["rid"]},
    ),
    _tool(
        "working_delete_action_type",
        "Delete an ActionType (refuses if referenced).",
        {"type": "object", "properties": {"rid": _RID}, "required": ["rid"]},
    ),
    _tool(
        "working_set_asset_mapping",
        "Bind/unbind a connection on an Object or Link.",
        {
            "type": "object",
            "properties": {"rid": _RID, "asset_mapping": _DEF},
            "required": ["rid", "asset_mapping"],
        },
    ),
    _tool(
        "working_import",
        "Replace or merge the working registry with a full registry payload.",
        {
            "type": "object",
            "properties": {
                "registry": _DEF,
                "mode": {"type": "string", "enum": ["replace", "merge"]},
            },
            "required": ["registry", "mode"],
        },
    ),
    _tool(
        "working_validate",
        "Run the validator on the working registry without writing.",
        {"type": "object", "properties": {}, "additionalProperties": False},
    ),
]


def dispatch_agent_call(
    wr: WorkingRegistry,
    name: str,
    args: dict[str, Any],
    *,
    connection_ids: set[str],
) -> dict[str, Any]:
    if name == "working_put_shared_property_type":
        wops.working_put_shared_property_type(
            wr,
            SharedPropertyTypeDefinition.model_validate(args["definition"]),
            connection_ids=connection_ids,
        )
        return {"ok": True}
    if name == "working_put_interface_type":
        wops.working_put_interface_type(
            wr,
            InterfaceTypeDefinition.model_validate(args["definition"]),
            connection_ids=connection_ids,
        )
        return {"ok": True}
    if name == "working_put_object_type":
        wops.working_put_object_type(
            wr,
            ObjectTypeDefinition.model_validate(args["definition"]),
            connection_ids=connection_ids,
        )
        return {"ok": True}
    if name == "working_put_link_type":
        wops.working_put_link_type(
            wr,
            LinkTypeDefinition.model_validate(args["definition"]),
            connection_ids=connection_ids,
        )
        return {"ok": True}
    if name == "working_put_action_type":
        wops.working_put_action_type(
            wr,
            ActionTypeDefinition.model_validate(args["definition"]),
            connection_ids=connection_ids,
        )
        return {"ok": True}
    if name == "working_delete_shared_property_type":
        wops.working_delete_shared_property_type(wr, args["rid"])
        return {"ok": True}
    if name == "working_delete_interface_type":
        wops.working_delete_interface_type(wr, args["rid"])
        return {"ok": True}
    if name == "working_delete_object_type":
        wops.working_delete_object_type(wr, args["rid"])
        return {"ok": True}
    if name == "working_delete_link_type":
        wops.working_delete_link_type(wr, args["rid"])
        return {"ok": True}
    if name == "working_delete_action_type":
        wops.working_delete_action_type(wr, args["rid"])
        return {"ok": True}
    if name == "working_set_asset_mapping":
        wops.working_set_asset_mapping(
            wr,
            args["rid"],
            AssetMapping.model_validate(args["asset_mapping"]),
            connection_ids=connection_ids,
        )
        return {"ok": True}
    if name == "working_import":
        wops.working_import(
            wr,
            OntologyRegistry.model_validate(args["registry"]),
            mode=ImportMode(args["mode"]),
            connection_ids=connection_ids,
        )
        return {"ok": True}
    if name == "working_validate":
        findings = validate(wr.snapshot(), connection_ids=connection_ids)
        return {
            "findings": [
                {
                    "severity": f.severity.value,
                    "code": f.code,
                    "path": f.path,
                    "message": f.message,
                }
                for f in findings
            ]
        }
    raise AgentToolError(f"Unknown tool {name!r}")
