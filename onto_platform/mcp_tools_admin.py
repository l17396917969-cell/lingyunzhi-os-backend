# onto_platform/mcp_tools_admin.py
import uuid as _uuid
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from onto_platform.auth import RequestPrincipal, Scope, generate_token
from onto_platform.config import Settings
from onto_platform.connections.probe import register_connection
from onto_platform.connections.store import ConnectionKind, ConnectionStore
from onto_platform.mcp_server import mcp_tool
from onto_platform.registry.lifecycle import (
    promote_staging_to_production,
    revert_staging_to_production,
    undo_promote,
)
from onto_platform.registry.store import Env, RegistryStore
from onto_platform.token_store import (
    insert_token,
    list_tokens,
    revoke_token,
)


@mcp_tool(
    "promote_staging_to_production",
    Scope.admin,
    "Atomic: previous_production <- production; production <- staging.",
    schema={
        "type": "object",
        "properties": {"commit_message": {"type": "string"}},
        "required": ["commit_message"],
        "additionalProperties": False,
    },
)
async def mcp_promote(
    *, principal: RequestPrincipal, session: AsyncSession, commit_message: str
) -> dict[str, Any]:
    settings = Settings()
    cs = ConnectionStore(secret_key=settings.secret_key)
    conn_ids = {str(c.id) for c in await cs.list_all(session)}
    store = RegistryStore()
    await promote_staging_to_production(
        session,
        store,
        commit_message=commit_message,
        token_label=principal.label,
        connection_ids=conn_ids,
    )
    return {"ok": True}


@mcp_tool(
    "revert_staging_to_production",
    Scope.admin,
    "Overwrite staging with current production. Discards staging edits.",
    schema={"type": "object", "properties": {}, "additionalProperties": False},
)
async def mcp_revert(
    *, principal: RequestPrincipal, session: AsyncSession
) -> dict[str, Any]:
    store = RegistryStore()
    await revert_staging_to_production(session, store, token_label=principal.label)
    return {"ok": True}


@mcp_tool(
    "undo_promote",
    Scope.admin,
    "One-shot: restore previous_production -> production, then clear the slot.",
    schema={"type": "object", "properties": {}, "additionalProperties": False},
)
async def mcp_undo(
    *, principal: RequestPrincipal, session: AsyncSession
) -> dict[str, Any]:
    store = RegistryStore()
    await undo_promote(session, store, token_label=principal.label)
    return {"ok": True}


@mcp_tool(
    "mint_token",
    Scope.admin,
    "Mint a new bearer token with the chosen scope. Plaintext shown once.",
    schema={
        "type": "object",
        "properties": {
            "scope": {"type": "string", "enum": ["read", "editor", "admin"]},
            "label": {"type": "string"},
        },
        "required": ["scope", "label"],
        "additionalProperties": False,
    },
)
async def mcp_mint(
    *, principal: RequestPrincipal, session: AsyncSession, scope: str, label: str
) -> dict[str, Any]:
    plaintext = generate_token()
    tid = await insert_token(session, plaintext, Scope[scope], label, principal.token_id)
    return {"token": plaintext, "token_id": str(tid)}


@mcp_tool(
    "revoke_token",
    Scope.admin,
    "Revoke a token by id (subsequent uses fail with UNAUTHORIZED).",
    schema={
        "type": "object",
        "properties": {"token_id": {"type": "string"}},
        "required": ["token_id"],
        "additionalProperties": False,
    },
)
async def mcp_revoke(
    *, principal: RequestPrincipal, session: AsyncSession, token_id: str
) -> dict[str, Any]:
    ok = await revoke_token(session, _uuid.UUID(token_id))
    return {"revoked": ok}


@mcp_tool(
    "list_tokens",
    Scope.admin,
    "List token metadata (no plaintext, no hashes).",
    schema={"type": "object", "properties": {}, "additionalProperties": False},
)
async def mcp_list_tokens(
    *, principal: RequestPrincipal, session: AsyncSession
) -> dict[str, Any]:
    rows = await list_tokens(session)
    return {
        "items": [
            {
                "id": str(r.token_id),
                "scope": r.scope.name,
                "label": r.label,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "revoked_at": r.revoked_at.isoformat() if r.revoked_at else None,
            }
            for r in rows
        ]
    }


@mcp_tool(
    "add_connection",
    Scope.admin,
    "Probe `SELECT 1` then persist a Fernet-encrypted DSN.",
    schema={
        "type": "object",
        "properties": {
            "label": {"type": "string"},
            "kind": {"type": "string", "enum": ["postgres", "mysql", "sqlite"]},
            "dsn": {"type": "string"},
        },
        "required": ["label", "kind", "dsn"],
        "additionalProperties": False,
    },
)
async def mcp_add_connection(
    *,
    principal: RequestPrincipal,
    session: AsyncSession,
    label: str,
    kind: str,
    dsn: str,
) -> dict[str, Any]:
    settings = Settings()
    store = ConnectionStore(secret_key=settings.secret_key)
    c = await register_connection(
        session, store=store, label=label, kind=ConnectionKind(kind), dsn=dsn
    )
    return {
        "id": str(c.id),
        "label": c.label,
        "kind": c.kind.value,
        "last_probe_ok_at": c.last_probe_ok_at.isoformat() if c.last_probe_ok_at else None,
    }


@mcp_tool(
    "delete_connection",
    Scope.admin,
    "Delete a connection. Refuses if any AssetMapping in either env still references it.",
    schema={
        "type": "object",
        "properties": {"connection_id": {"type": "string"}},
        "required": ["connection_id"],
        "additionalProperties": False,
    },
)
async def mcp_delete_connection(
    *, principal: RequestPrincipal, session: AsyncSession, connection_id: str
) -> dict[str, Any]:
    settings = Settings()
    cs = ConnectionStore(secret_key=settings.secret_key)
    rs = RegistryStore()
    for env in (Env.staging, Env.production):
        snap = await rs.load(session, env)
        for kf in ("object_types", "link_types"):
            for rid, e in getattr(snap.registry, kf).items():
                if e.asset_mapping.read_connection_id == connection_id:
                    raise ValueError(
                        f"Connection {connection_id} is referenced by {kf[:-1]} {rid}"
                    )
    await cs.delete(session, _uuid.UUID(connection_id))
    return {"deleted": True}


@mcp_tool(
    "list_connections",
    Scope.admin,
    "List connections (no DSN material returned).",
    schema={"type": "object", "properties": {}, "additionalProperties": False},
)
async def mcp_list_connections(
    *, principal: RequestPrincipal, session: AsyncSession
) -> dict[str, Any]:
    settings = Settings()
    cs = ConnectionStore(secret_key=settings.secret_key)
    items = await cs.list_all(session)
    return {
        "items": [
            {
                "id": str(c.id),
                "label": c.label,
                "kind": c.kind.value,
                "last_probe_ok_at": (
                    c.last_probe_ok_at.isoformat() if c.last_probe_ok_at else None
                ),
            }
            for c in items
        ]
    }
