# onto_platform/mcp_tools_editor.py
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from onto_platform.auth import RequestPrincipal, Scope
from onto_platform.config import Settings
from onto_platform.connections.store import ConnectionStore
from onto_platform.mcp_server import mcp_tool
from onto_platform.proto_models import (
    ActionTypeDefinition,
    AssetMapping,
    InterfaceTypeDefinition,
    LinkTypeDefinition,
    ObjectTypeDefinition,
    OntologyRegistry,
    SharedPropertyTypeDefinition,
)
from onto_platform.registry.crud import (
    delete_action_type,
    delete_interface_type,
    delete_link_type,
    delete_object_type,
    delete_shared_property_type,
    put_action_type,
    put_interface_type,
    put_link_type,
    put_object_type,
    put_shared_property_type,
    set_asset_mapping,
)
from onto_platform.registry.imports import ImportMode, import_into_registry
from onto_platform.registry.store import Env, RegistryStore
from onto_platform.registry.validator import validate

_DEF_SCHEMA: dict[str, Any] = {"type": "object"}
_RID_SCHEMA: dict[str, Any] = {"type": "string"}
_VER_SCHEMA: dict[str, Any] = {"type": "integer", "minimum": 0}


async def _conn_ids(session: AsyncSession) -> set[str]:
    settings = Settings()
    store = ConnectionStore(secret_key=settings.secret_key)
    rows = await store.list_all(session)
    return {str(c.id) for c in rows}


async def _save(
    session: AsyncSession,
    principal: RequestPrincipal,
    new_reg: OntologyRegistry,
    expected_version: Optional[int],
) -> dict[str, Any]:
    store = RegistryStore()
    snap = await store.load(session, Env.staging)
    new_version = await store.save(
        session,
        Env.staging,
        new_reg,
        expected_version=expected_version if expected_version is not None else snap.version,
        token_label=principal.label,
    )
    return {"staging_version": new_version}


@mcp_tool(
    "validate_staging",
    Scope.editor,
    "Run the validator on persisted staging.",
    schema={"type": "object", "properties": {}, "additionalProperties": False},
)
async def validate_staging(
    *, principal: RequestPrincipal, session: AsyncSession
) -> dict[str, Any]:
    store = RegistryStore()
    snap = await store.load(session, Env.staging)
    findings = validate(snap.registry, connection_ids=await _conn_ids(session))
    return {
        "findings": [
            {
                "severity": f.severity.value,
                "code": f.code,
                "path": f.path,
                "message": f.message,
                "details": f.details,
            }
            for f in findings
        ]
    }


def _put_factory(name: str, kind_cls: Any, putter: Any) -> Any:
    schema: dict[str, Any] = {
        "type": "object",
        "properties": {"definition": _DEF_SCHEMA, "expected_version": _VER_SCHEMA},
        "required": ["definition"],
        "additionalProperties": False,
    }

    @mcp_tool(name, Scope.editor, f"Upsert a {kind_cls.__name__} into staging.", schema=schema)
    async def f(
        *,
        principal: RequestPrincipal,
        session: AsyncSession,
        definition: dict[str, Any],
        expected_version: Optional[int] = None,
    ) -> dict[str, Any]:
        store = RegistryStore()
        snap = await store.load(session, Env.staging)
        defn = kind_cls.model_validate(definition)
        new_reg = putter(snap.registry, defn, connection_ids=await _conn_ids(session))
        return await _save(session, principal, new_reg, expected_version)

    f.__name__ = name
    return f


def _del_factory(name: str, deleter: Any) -> Any:
    schema: dict[str, Any] = {
        "type": "object",
        "properties": {"rid": _RID_SCHEMA, "expected_version": _VER_SCHEMA},
        "required": ["rid"],
        "additionalProperties": False,
    }

    @mcp_tool(
        name,
        Scope.editor,
        "Delete an entity from staging (refuses on inbound references).",
        schema=schema,
    )
    async def f(
        *,
        principal: RequestPrincipal,
        session: AsyncSession,
        rid: str,
        expected_version: Optional[int] = None,
    ) -> dict[str, Any]:
        store = RegistryStore()
        snap = await store.load(session, Env.staging)
        new_reg = deleter(snap.registry, rid)
        return await _save(session, principal, new_reg, expected_version)

    f.__name__ = name
    return f


_put_factory("put_shared_property_type", SharedPropertyTypeDefinition, put_shared_property_type)
_del_factory("delete_shared_property_type", delete_shared_property_type)
_put_factory("put_interface_type", InterfaceTypeDefinition, put_interface_type)
_del_factory("delete_interface_type", delete_interface_type)
_put_factory("put_object_type", ObjectTypeDefinition, put_object_type)
_del_factory("delete_object_type", delete_object_type)
_put_factory("put_link_type", LinkTypeDefinition, put_link_type)
_del_factory("delete_link_type", delete_link_type)
_put_factory("put_action_type", ActionTypeDefinition, put_action_type)
_del_factory("delete_action_type", delete_action_type)


@mcp_tool(
    "import_full_registry_to_staging",
    Scope.editor,
    "Replace or merge staging with a full registry payload.",
    schema={
        "type": "object",
        "properties": {
            "registry": _DEF_SCHEMA,
            "mode": {"type": "string", "enum": ["replace", "merge"]},
            "expected_version": _VER_SCHEMA,
        },
        "required": ["registry", "mode"],
        "additionalProperties": False,
    },
)
async def import_full(
    *,
    principal: RequestPrincipal,
    session: AsyncSession,
    registry: dict[str, Any],
    mode: str,
    expected_version: Optional[int] = None,
) -> dict[str, Any]:
    store = RegistryStore()
    snap = await store.load(session, Env.staging)
    incoming = OntologyRegistry.model_validate(registry)
    new_reg = import_into_registry(
        snap.registry,
        incoming,
        mode=ImportMode(mode),
        connection_ids=await _conn_ids(session),
    )
    return await _save(session, principal, new_reg, expected_version)


@mcp_tool(
    "set_asset_mapping",
    Scope.editor,
    "Bind/unbind a connection on an Object or Link without re-sending the full definition.",
    schema={
        "type": "object",
        "properties": {
            "rid": _RID_SCHEMA,
            "asset_mapping": _DEF_SCHEMA,
            "expected_version": _VER_SCHEMA,
        },
        "required": ["rid", "asset_mapping"],
        "additionalProperties": False,
    },
)
async def mcp_set_asset_mapping(
    *,
    principal: RequestPrincipal,
    session: AsyncSession,
    rid: str,
    asset_mapping: dict[str, Any],
    expected_version: Optional[int] = None,
) -> dict[str, Any]:
    store = RegistryStore()
    snap = await store.load(session, Env.staging)
    am = AssetMapping.model_validate(asset_mapping)
    new_reg = set_asset_mapping(snap.registry, rid, am, connection_ids=await _conn_ids(session))
    return await _save(session, principal, new_reg, expected_version)
