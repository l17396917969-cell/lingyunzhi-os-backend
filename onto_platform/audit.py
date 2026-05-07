# onto_platform/audit.py
import json
import re
import uuid
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

_DSN_KEYS = ("password", "pwd")
_SQL_TRUNC = 500
_REGISTRY_FIELDS = (
    "shared_property_types",
    "interface_types",
    "object_types",
    "link_types",
    "action_types",
)


def _redact_dsn(s: str) -> str:
    out = s
    for k in _DSN_KEYS:
        out = re.sub(rf"({k}=)[^&\s]+", rf"\1***", out, flags=re.IGNORECASE)
    out = re.sub(r"(://[^:]+:)[^@]+(@)", r"\1***\2", out)
    return out


def summarize_args(tool: str, args: dict[str, Any]) -> dict[str, Any]:
    """Sanitize argument dict for audit logging."""
    out: dict[str, Any] = {}
    for k, v in args.items():
        if k == "sql" and isinstance(v, str):
            if len(v) > _SQL_TRUNC:
                out["sql"] = v[:_SQL_TRUNC]
                out["sql_truncated"] = True
            else:
                out["sql"] = v
        elif k == "dsn" and isinstance(v, str):
            out["dsn"] = _redact_dsn(v)
        elif k == "registry" and isinstance(v, dict):
            out["entity_counts"] = {
                f: len(v.get(f, {})) for f in _REGISTRY_FIELDS
            }
        elif k in ("token", "token_plaintext"):
            out[k] = "***"
        else:
            out[k] = v
    return out


class AuditLogWriter:
    async def record(
        self,
        session: AsyncSession,
        *,
        tool: str,
        token_id: Optional[uuid.UUID],
        token_label: Optional[str],
        scope: Optional[str],
        args: dict[str, Any],
        outcome: str,
        error_code: Optional[str],
        return_value: Optional[dict[str, Any]] = None,
    ) -> None:
        summary = summarize_args(tool, args)
        # If a tool's return_value contains plaintext token material,
        # explicitly never embed it in args_summary. The return_value param
        # exists so the writer can be future-extended; we intentionally do
        # nothing with it here beyond ignoring its content.
        await session.execute(
            text(
                "INSERT INTO audit_log "
                "(token_id, token_label, scope, tool, args_summary, outcome, error_code) "
                "VALUES (:tid, :lbl, :sc, :tl, CAST(:as_ AS jsonb), :oc, :ec)"
            ),
            {
                "tid": str(token_id) if token_id else None,
                "lbl": token_label,
                "sc": scope,
                "tl": tool,
                "as_": json.dumps(summary, default=str),
                "oc": outcome,
                "ec": error_code,
            },
        )
