# onto_platform/mcp_tools_read.py
import uuid as _uuid
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from onto_platform.auth import RequestPrincipal, Scope
from onto_platform.config import Settings
from onto_platform.connections.pool import ConnectionPool
from onto_platform.connections.store import ConnectionStore
from onto_platform.connections.data_query import describe_bound_asset, query_sql
from onto_platform.mcp_server import mcp_tool
from onto_platform.registry.store import Env, RegistryStore

_ENV_SCHEMA: dict[str, Any] = {"type": "string", "enum": ["staging", "production"]}


def _matches(filter_str: Optional[str], *fields: str) -> bool:
    if not filter_str:
        return True
    needle = filter_str.lower()
    return any(needle in (f or "").lower() for f in fields)


def _list_compact(d: dict[str, Any], filter_str: Optional[str]) -> list[dict[str, Any]]:
    return [
        {
            "rid": v.rid,
            "api_name": v.api_name,
            "display_name": v.display_name,
            "lifecycle_status": v.lifecycle_status.value,
        }
        for v in d.values()
        if _matches(filter_str, v.api_name, v.display_name)
    ]


@mcp_tool(
    "get_registry",
    Scope.read,
    "Return the full OntologyRegistry for the chosen env.",
    schema={
        "type": "object",
        "properties": {"env": _ENV_SCHEMA},
        "required": ["env"],
        "additionalProperties": False,
    },
)
async def get_registry(
    *, principal: RequestPrincipal, session: AsyncSession, env: str
) -> dict[str, Any]:
    store = RegistryStore()
    snap = await store.load(session, Env(env))
    return snap.registry.model_dump()


def _make_lister(field: str, name: str) -> Any:
    @mcp_tool(
        name,
        Scope.read,
        f"List {field} entries for the chosen env.",
        schema={
            "type": "object",
            "properties": {"env": _ENV_SCHEMA, "filter": {"type": "string"}},
            "required": ["env"],
            "additionalProperties": False,
        },
    )
    async def lister(
        *,
        principal: RequestPrincipal,
        session: AsyncSession,
        env: str,
        filter: Optional[str] = None,
    ) -> dict[str, Any]:
        store = RegistryStore()
        snap = await store.load(session, Env(env))
        return {"items": _list_compact(getattr(snap.registry, field), filter)}

    lister.__name__ = name
    return lister


list_object_types = _make_lister("object_types", "list_object_types")
list_link_types = _make_lister("link_types", "list_link_types")
list_interface_types = _make_lister("interface_types", "list_interface_types")
list_shared_property_types = _make_lister("shared_property_types", "list_shared_property_types")
list_action_types = _make_lister("action_types", "list_action_types")


@mcp_tool(
    "get_entity",
    Scope.read,
    "Return one entity definition by RID, regardless of kind.",
    schema={
        "type": "object",
        "properties": {"env": _ENV_SCHEMA, "rid": {"type": "string"}},
        "required": ["env", "rid"],
        "additionalProperties": False,
    },
)
async def get_entity(
    *, principal: RequestPrincipal, session: AsyncSession, env: str, rid: str
) -> dict[str, Any]:
    store = RegistryStore()
    snap = await store.load(session, Env(env))
    for kind_field in (
        "shared_property_types",
        "interface_types",
        "object_types",
        "link_types",
        "action_types",
    ):
        d = getattr(snap.registry, kind_field)
        if rid in d:
            return {"entity": d[rid].model_dump(), "kind": kind_field[:-1]}
    raise KeyError(rid)


@mcp_tool(
    "find_by_api_name",
    Scope.read,
    "Resolve api_name -> entity (any kind, optionally restricted).",
    schema={
        "type": "object",
        "properties": {
            "env": _ENV_SCHEMA,
            "api_name": {"type": "string"},
            "kind": {"type": "string"},
        },
        "required": ["env", "api_name"],
        "additionalProperties": False,
    },
)
async def find_by_api_name(
    *,
    principal: RequestPrincipal,
    session: AsyncSession,
    env: str,
    api_name: str,
    kind: Optional[str] = None,
) -> dict[str, Any]:
    store = RegistryStore()
    snap = await store.load(session, Env(env))
    kinds: tuple[str, ...] = (kind + "s",) if kind else (
        "shared_property_types",
        "interface_types",
        "object_types",
        "link_types",
        "action_types",
    )
    for kf in kinds:
        d = getattr(snap.registry, kf, {})
        for v in d.values():
            if v.api_name == api_name:
                return {"entity": v.model_dump(), "kind": kf[:-1]}
    raise KeyError(api_name)


@mcp_tool(
    "describe_bound_asset",
    Scope.read,
    "Return connection_id, asset_path, and column->property mapping for an entity.",
    schema={
        "type": "object",
        "properties": {"env": _ENV_SCHEMA, "rid": {"type": "string"}},
        "required": ["env", "rid"],
        "additionalProperties": False,
    },
)
async def mcp_describe_bound_asset(
    *, principal: RequestPrincipal, session: AsyncSession, env: str, rid: str
) -> dict[str, Any]:
    store = RegistryStore()
    snap = await store.load(session, Env(env))
    return describe_bound_asset(snap.registry, rid)


@mcp_tool(
    "query_sql",
    Scope.read,
    "Run a SELECT-only statement against a registered connection. "
    "Server enforces read-only at engine level + AST gate, then applies compliance masking.",
    schema={
        "type": "object",
        "properties": {
            "connection_id": {"type": "string"},
            "sql": {"type": "string"},
            "max_rows": {"type": "integer", "minimum": 1},
            "timeout_ms": {"type": "integer", "minimum": 1},
        },
        "required": ["connection_id", "sql"],
        "additionalProperties": False,
    },
)
async def mcp_query_sql(
    *,
    principal: RequestPrincipal,
    session: AsyncSession,
    connection_id: str,
    sql: str,
    max_rows: Optional[int] = None,
    timeout_ms: Optional[int] = None,
) -> dict[str, Any]:
    settings = Settings()
    cap_rows = settings.query_max_rows_cap
    cap_timeout = settings.query_timeout_ms_cap
    eff_rows = min(max_rows or settings.query_default_max_rows, cap_rows)
    eff_timeout = min(timeout_ms or settings.query_default_timeout_ms, cap_timeout)

    cid = _uuid.UUID(connection_id)
    conn_store = ConnectionStore(secret_key=settings.secret_key)
    conn_meta = await conn_store.get_by_id(session, cid)
    pool = ConnectionPool(store=conn_store)
    try:
        reg_store = RegistryStore()
        snap = await reg_store.load(session, Env.production)
        return await query_sql(
            session,
            pool=pool,
            connection_id=cid,
            sql=sql,
            max_rows=eff_rows,
            timeout_ms=eff_timeout,
            registry=snap.registry,
            dialect=conn_meta.kind.value,
        )
    finally:
        await pool.dispose_all()
