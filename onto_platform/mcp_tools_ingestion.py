"""MCP tools for ingestion: register_upload, submit/get/list/cancel ingestion job,
delete_orphan_uploads.
"""
from __future__ import annotations

import base64
import hashlib
import pathlib
import uuid
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from onto_platform.auth import RequestPrincipal, Scope
from onto_platform.config import Settings
from onto_platform.ingestion.store import ImportMode, IngestionStore, JobStatus
from onto_platform.mcp_server import mcp_tool

_store = IngestionStore()


@mcp_tool(
    "register_upload",
    Scope.admin,
    "Upload a (small) file directly via MCP. "
    "Files > max upload bytes should use POST /admin/ingestion/uploads instead.",
    schema={
        "type": "object",
        "properties": {
            "filename": {"type": "string"},
            "base64_content": {"type": "string"},
        },
        "required": ["filename", "base64_content"],
        "additionalProperties": False,
    },
)
async def register_upload(
    *,
    principal: RequestPrincipal,
    session: AsyncSession,
    filename: str,
    base64_content: str,
) -> dict[str, Any]:
    settings = Settings()
    body = base64.b64decode(base64_content)
    if len(body) > settings.ingestion_max_upload_bytes:
        raise ValueError(f"upload exceeds {settings.ingestion_max_upload_bytes} bytes")
    ext = pathlib.Path(filename).suffix.lstrip(".").lower()
    if ext not in ("sql", "pdf", "docx", "pptx", "xlsx"):
        raise ValueError(f"unsupported extension: {ext!r}")
    upload_id = uuid.uuid4()
    base_dir = pathlib.Path(settings.ingestion_data_dir) / "orphan"
    base_dir.mkdir(parents=True, exist_ok=True)
    path = base_dir / f"{upload_id}_{pathlib.Path(filename).name}"
    path.write_bytes(body)
    sha = hashlib.sha256(body).hexdigest()
    await session.execute(
        text(
            "INSERT INTO ingestion_uploads "
            "(id, filename, kind, size_bytes, sha256, path, created_by_token_id) "
            "VALUES (:i, :f, :k, :s, :h, :p, :c)"
        ),
        {
            "i": str(upload_id),
            "f": filename,
            "k": ext,
            "s": len(body),
            "h": sha,
            "p": str(path),
            "c": str(principal.token_id),
        },
    )
    return {
        "upload_id": str(upload_id),
        "kind": ext,
        "size_bytes": len(body),
        "sha256": sha,
    }


@mcp_tool(
    "submit_ingestion_job",
    Scope.editor,
    "Kick off an ingestion job over previously-uploaded files.",
    schema={
        "type": "object",
        "properties": {
            "upload_ids": {"type": "array", "items": {"type": "string"}},
            "mode": {"type": "string", "enum": ["replace", "merge"]},
            "instructions": {"type": "string"},
        },
        "required": ["upload_ids", "mode"],
        "additionalProperties": False,
    },
)
async def submit_ingestion_job(
    *,
    principal: RequestPrincipal,
    session: AsyncSession,
    upload_ids: list[str],
    mode: str,
    instructions: str = "",
) -> dict[str, Any]:
    settings = Settings()
    if len(upload_ids) > settings.ingestion_max_files_per_job:
        raise ValueError(
            f"too many files (max {settings.ingestion_max_files_per_job})"
        )
    job_id = await _store.create_job(
        session,
        mode=ImportMode(mode),
        instructions=instructions or None,
        upload_ids=[uuid.UUID(u) for u in upload_ids],
        created_by_token_id=principal.token_id,
    )
    return {"job_id": str(job_id), "status": "queued"}


@mcp_tool(
    "get_ingestion_job",
    Scope.editor,
    "Status and decisions report for a specific ingestion job.",
    schema={
        "type": "object",
        "properties": {"job_id": {"type": "string"}},
        "required": ["job_id"],
        "additionalProperties": False,
    },
)
async def get_ingestion_job(
    *,
    principal: RequestPrincipal,
    session: AsyncSession,
    job_id: str,
) -> dict[str, Any]:
    j = await _store.get_job(session, uuid.UUID(job_id))
    return {
        "id": str(j.id),
        "status": j.status.value,
        "phase": j.phase_message,
        "progress_pct": j.progress_pct,
        "mode": j.mode.value,
        "decisions_report": j.decisions_report,
        "staging_version_after": j.staging_version_after,
        "error_code": j.error_code,
        "error_details": j.error_details,
    }


@mcp_tool(
    "list_ingestion_jobs",
    Scope.editor,
    "List ingestion jobs (most-recent first).",
    schema={
        "type": "object",
        "properties": {
            "limit": {"type": "integer", "minimum": 1, "maximum": 200},
        },
        "additionalProperties": False,
    },
)
async def list_ingestion_jobs(
    *,
    principal: RequestPrincipal,
    session: AsyncSession,
    limit: int = 50,
) -> dict[str, Any]:
    effective_limit = min(max(1, limit), 200)
    rows = await session.execute(
        text(
            "SELECT id, status, mode, progress_pct, error_code, created_at "
            "FROM ingestion_jobs ORDER BY created_at DESC LIMIT :l"
        ),
        {"l": effective_limit},
    )
    return {
        "items": [
            {
                "id": str(r.id),
                "status": r.status,
                "mode": r.mode,
                "progress_pct": r.progress_pct,
                "error_code": r.error_code,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]
    }


@mcp_tool(
    "cancel_ingestion_job",
    Scope.editor,
    "Cooperatively cancel a job. Already-imported or failed jobs cannot be cancelled.",
    schema={
        "type": "object",
        "properties": {"job_id": {"type": "string"}},
        "required": ["job_id"],
        "additionalProperties": False,
    },
)
async def cancel_ingestion_job(
    *,
    principal: RequestPrincipal,
    session: AsyncSession,
    job_id: str,
) -> dict[str, Any]:
    await session.execute(
        text(
            "UPDATE ingestion_jobs SET status = 'cancelled', finished_at = now() "
            "WHERE id = :i AND status NOT IN ('imported', 'failed', 'cancelled')"
        ),
        {"i": job_id},
    )
    return {"cancelled": True}


@mcp_tool(
    "delete_orphan_uploads",
    Scope.admin,
    "Delete uploads that were never associated with a job.",
    schema={
        "type": "object",
        "properties": {
            "older_than_minutes": {"type": "integer", "minimum": 1},
        },
        "required": ["older_than_minutes"],
        "additionalProperties": False,
    },
)
async def delete_orphan_uploads(
    *,
    principal: RequestPrincipal,
    session: AsyncSession,
    older_than_minutes: int,
) -> dict[str, Any]:
    rows = await session.execute(
        text(
            "DELETE FROM ingestion_uploads "
            "WHERE job_id IS NULL "
            "AND created_at < now() - (:m * interval '1 minute') "
            "RETURNING id"
        ),
        {"m": older_than_minutes},
    )
    return {"deleted": len(rows.all())}
