# onto_platform/mcp_server.py
from dataclasses import dataclass
from typing import Any, AsyncGenerator, Awaitable, Callable, Optional

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from onto_platform.audit import AuditLogWriter
from onto_platform.auth import RequestPrincipal, Scope, require_scope
from onto_platform.connections.data_query import (
    AssetUnboundError,
    BoundAssetNotFoundError,
    SqlRejectedError,
)
from onto_platform.connections.probe import ConnectionProbeError
from onto_platform.connections.store import ConnectionAlreadyExists, ConnectionNotFound
from onto_platform.registry.crud import ReferencedError, ValidationFailedError
from onto_platform.registry.lifecycle import UndoUnavailableError
from onto_platform.registry.store import StaleVersionError


@dataclass
class ToolSpec:
    name: str
    scope: Scope
    description: str
    handler: Callable[..., Awaitable[dict[str, Any]]]
    schema: dict[str, Any]


_TOOLS: dict[str, ToolSpec] = {}


def mcp_tool(
    name: str,
    scope: Scope,
    description: str,
    schema: dict[str, Any],
) -> Callable[[Callable[..., Awaitable[dict[str, Any]]]], Callable[..., Awaitable[dict[str, Any]]]]:
    """Register an async function `(*, principal, session, **args) -> dict`."""

    def deco(
        fn: Callable[..., Awaitable[dict[str, Any]]],
    ) -> Callable[..., Awaitable[dict[str, Any]]]:
        _TOOLS[name] = ToolSpec(
            name=name,
            scope=scope,
            description=description,
            handler=fn,
            schema=schema,
        )
        return fn

    return deco


def _exc_to_error(e: Exception) -> tuple[int, dict[str, Any]]:
    if isinstance(e, ValidationFailedError):
        return 422, {
            "code": "VALIDATION_FAILED",
            "message": str(e),
            "details": {
                "findings": [
                    {
                        "severity": f.severity.value,
                        "code": f.code,
                        "path": f.path,
                        "message": f.message,
                        "details": f.details,
                    }
                    for f in e.findings
                ]
            },
        }
    if isinstance(e, StaleVersionError):
        return 409, {
            "code": "STALE_VERSION",
            "message": str(e),
            "details": {
                "current_version": e.current_version,
                "expected_version": e.expected_version,
            },
        }
    if isinstance(e, ReferencedError):
        return 409, {
            "code": "REFERENCED",
            "message": str(e),
            "details": {
                "referrers": [
                    {"rid": r.rid, "kind": r.kind, "field": r.field, "path": r.path}
                    for r in e.referrers
                ]
            },
        }
    if isinstance(e, UndoUnavailableError):
        return 409, {"code": "UNDO_UNAVAILABLE", "message": str(e)}
    if isinstance(e, SqlRejectedError):
        return 400, {
            "code": "SQL_REJECTED",
            "message": str(e),
            "details": {"reason": e.reason, "detail": e.detail},
        }
    if isinstance(e, ConnectionProbeError):
        return 502, {
            "code": "CONNECTION_PROBE_FAILED",
            "message": str(e),
            "details": {"driver_error": e.driver_error},
        }
    if isinstance(e, (ConnectionNotFound, BoundAssetNotFoundError, AssetUnboundError, KeyError)):
        return 404, {"code": "NOT_FOUND", "message": str(e)}
    if isinstance(e, ConnectionAlreadyExists):
        return 409, {"code": "ALREADY_EXISTS", "message": str(e)}
    return 500, {"code": "INTERNAL", "message": str(e)}


def make_mcp_router(
    session_provider: Callable[[], AsyncGenerator[AsyncSession, None]],
    *,
    app_state: Any,
) -> APIRouter:
    """Mount /mcp as a JSON-RPC 2.0 endpoint implementing the MCP tools/* methods."""
    router = APIRouter()
    audit = AuditLogWriter()

    # Build a reusable dependency for scope.read-floor auth
    _auth_dep = require_scope(Scope.read, session_provider)

    @router.post("/mcp")
    async def mcp_endpoint(
        request: Request,
        session: AsyncSession = Depends(session_provider),
    ) -> Any:
        principal: RequestPrincipal = await _auth_dep(request, session=session)
        body: dict[str, Any] = await request.json()
        method: Optional[str] = body.get("method")
        req_id: Any = body.get("id")
        params: dict[str, Any] = body.get("params") or {}

        if method == "tools/list":
            tools = [
                {
                    "name": t.name,
                    "description": t.description,
                    "inputSchema": t.schema,
                }
                for t in _TOOLS.values()
                if principal.scope >= t.scope
            ]
            return {"jsonrpc": "2.0", "id": req_id, "result": {"tools": tools}}

        if method == "tools/call":
            name: Optional[str] = params.get("name")
            args: dict[str, Any] = params.get("arguments") or {}
            spec = _TOOLS.get(name or "")
            if spec is None:
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32601, "message": f"Unknown tool {name!r}"},
                }
            if principal.scope < spec.scope:
                await audit.record(
                    session,
                    tool=spec.name,
                    token_id=principal.token_id,
                    token_label=principal.label,
                    scope=principal.scope.name,
                    args=args,
                    outcome="forbidden",
                    error_code="FORBIDDEN",
                )
                await session.commit()
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {
                        "code": -32000,
                        "message": "FORBIDDEN",
                        "data": {"required_scope": spec.scope.name},
                    },
                }
            try:
                result = await spec.handler(principal=principal, session=session, **args)
            except Exception as e:
                _, err = _exc_to_error(e)
                await audit.record(
                    session,
                    tool=spec.name,
                    token_id=principal.token_id,
                    token_label=principal.label,
                    scope=principal.scope.name,
                    args=args,
                    outcome="error",
                    error_code=err["code"],
                )
                await session.commit()
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {
                        "code": -32000,
                        "message": err["code"],
                        "data": err.get("details"),
                    },
                }
            await audit.record(
                session,
                tool=spec.name,
                token_id=principal.token_id,
                token_label=principal.label,
                scope=principal.scope.name,
                args=args,
                outcome="ok",
                error_code=None,
            )
            await session.commit()
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"structuredContent": result},
            }

        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": -32601, "message": f"Unknown method {method!r}"},
        }

    return router


# Bootstrap whoami tool — always visible to any valid token
@mcp_tool(
    "whoami",
    Scope.read,
    "Identify the calling principal",
    schema={"type": "object", "properties": {}, "additionalProperties": False},
)
async def whoami(*, principal: RequestPrincipal, session: AsyncSession) -> dict[str, Any]:
    return {
        "token_label": principal.label,
        "scope": principal.scope.name,
        "server_version": "0.1.0",
    }
