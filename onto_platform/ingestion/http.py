from __future__ import annotations

import hashlib
import pathlib
import uuid
from typing import Any, Callable, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from onto_platform.auth import Scope
from onto_platform.config import Settings
from onto_platform.ingestion.store import ImportMode, IngestionStore, JobStatus
from onto_platform.ingestion.workers import IngestionWorker
from onto_platform.ui_auth import require_scope_via_cookie_or_bearer


async def process_upload(
    file: "UploadFile",
    *,
    principal: Any,
    session: "AsyncSession",
    settings: "Settings",
    data_dir: "pathlib.Path",
) -> dict[str, Any]:
    """Process a file upload — validates kind/size, writes to disk, inserts ingestion_uploads row.
    Returns {upload_id, kind, size_bytes, sha256}.
    Raises HTTPException 400/413 on validation errors.
    """
    ext = (pathlib.Path(file.filename or "").suffix or "").lstrip(".").lower()
    if ext not in ("sql", "pdf", "docx", "pptx", "xlsx"):
        raise HTTPException(
            status_code=400,
            detail={
                "code": "UPLOAD_KIND_UNSUPPORTED",
                "message": f"Unsupported extension: {ext!r}",
            },
        )
    body = await file.read()
    if len(body) > settings.ingestion_max_upload_bytes:
        raise HTTPException(
            status_code=413,
            detail={
                "code": "UPLOAD_TOO_LARGE",
                "message": f"file > {settings.ingestion_max_upload_bytes} bytes",
            },
        )
    sha = hashlib.sha256(body).hexdigest()
    upload_id = uuid.uuid4()
    target_dir = data_dir / "orphan"
    target_dir.mkdir(parents=True, exist_ok=True)
    safe_name = pathlib.Path(file.filename or "upload").name
    target_path = target_dir / f"{upload_id}_{safe_name}"
    target_path.write_bytes(body)
    await session.execute(
        text(
            "INSERT INTO ingestion_uploads "
            "(id, filename, kind, size_bytes, sha256, path, created_by_token_id) "
            "VALUES (:i, :f, :k, :s, :h, :p, :c)"
        ),
        {
            "i": str(upload_id),
            "f": file.filename,
            "k": ext,
            "s": len(body),
            "h": sha,
            "p": str(target_path),
            "c": str(principal.token_id) if principal.token_id else None,
        },
    )
    await session.commit()
    return {
        "upload_id": str(upload_id),
        "kind": ext,
        "size_bytes": len(body),
        "sha256": sha,
    }


def make_ingestion_router(
    session_provider: Any,
    *,
    get_worker: Callable[[], Optional[IngestionWorker]],
    settings: Settings,
) -> APIRouter:
    router = APIRouter(prefix="/admin/ingestion")
    store = IngestionStore()
    data_dir = pathlib.Path(settings.ingestion_data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)

    _editor_dep = require_scope_via_cookie_or_bearer(Scope.editor, session_provider)

    @router.post("/uploads")
    async def upload_file(
        file: UploadFile = File(...),
        principal: Any = Depends(_editor_dep),  # type: ignore[arg-type]
        session: AsyncSession = Depends(session_provider),
    ) -> dict[str, Any]:
        return await process_upload(
            file, principal=principal, session=session, settings=settings, data_dir=data_dir
        )

    @router.post("/jobs")
    async def create_job(
        request: Request,
        principal: Any = Depends(_editor_dep),  # type: ignore[arg-type]
        session: AsyncSession = Depends(session_provider),
    ) -> dict[str, Any]:
        body = await request.json()
        upload_ids_raw: list[str] = body.get("upload_ids") or []
        mode_str: str = body.get("mode") or ""
        instructions: Optional[str] = body.get("instructions")

        if mode_str not in ("replace", "merge"):
            raise HTTPException(
                status_code=400,
                detail={"code": "INVALID_MODE", "message": f"mode must be replace or merge, got {mode_str!r}"},
            )
        if len(upload_ids_raw) > settings.ingestion_max_files_per_job:
            raise HTTPException(
                status_code=400,
                detail={
                    "code": "JOB_TOO_LARGE",
                    "message": f"too many files (max {settings.ingestion_max_files_per_job})",
                },
            )
        # total bytes check
        rows = await session.execute(
            text(
                "SELECT COALESCE(SUM(size_bytes), 0) AS total "
                "FROM ingestion_uploads WHERE id = ANY(:ids)"
            ),
            {"ids": upload_ids_raw},
        )
        total = int(rows.scalar_one())
        if total > settings.ingestion_max_total_bytes_per_job:
            raise HTTPException(
                status_code=400,
                detail={
                    "code": "JOB_TOO_LARGE",
                    "message": f"total bytes ({total}) > {settings.ingestion_max_total_bytes_per_job}",
                },
            )
        job_id = await store.create_job(
            session,
            mode=ImportMode(mode_str),
            instructions=instructions,
            upload_ids=[uuid.UUID(u) for u in upload_ids_raw],
            created_by_token_id=principal.token_id,
        )
        await session.commit()
        worker = get_worker()
        if worker is not None:
            worker.submit(job_id)
        return {"job_id": str(job_id), "status": "queued"}

    @router.get("/jobs")
    async def list_jobs(
        limit: int = 50,
        principal: Any = Depends(_editor_dep),  # type: ignore[arg-type]
        session: AsyncSession = Depends(session_provider),
    ) -> dict[str, Any]:
        limit = min(max(1, limit), 200)
        rows = await session.execute(
            text(
                "SELECT id, status, mode, progress_pct, error_code, created_at "
                "FROM ingestion_jobs ORDER BY created_at DESC LIMIT :l"
            ),
            {"l": limit},
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

    @router.get("/jobs/{job_id}")
    async def get_job(
        job_id: str,
        principal: Any = Depends(_editor_dep),  # type: ignore[arg-type]
        session: AsyncSession = Depends(session_provider),
    ) -> dict[str, Any]:
        try:
            jid = uuid.UUID(job_id)
        except ValueError:
            raise HTTPException(status_code=400, detail={"code": "INVALID_JOB_ID"})
        job = await store.get_job(session, jid)
        return {
            "id": str(job.id),
            "status": job.status.value,
            "phase": job.phase_message,
            "progress_pct": job.progress_pct,
            "mode": job.mode.value,
            "instructions": job.instructions,
            "decisions_report": job.decisions_report,
            "staging_version_after": job.staging_version_after,
            "error_code": job.error_code,
            "error_details": job.error_details,
            "created_at": job.created_at.isoformat() if job.created_at else None,
            "started_at": job.started_at.isoformat() if job.started_at else None,
            "finished_at": job.finished_at.isoformat() if job.finished_at else None,
        }

    @router.post("/jobs/{job_id}:cancel")
    async def cancel_job(
        job_id: str,
        principal: Any = Depends(_editor_dep),  # type: ignore[arg-type]
        session: AsyncSession = Depends(session_provider),
    ) -> dict[str, Any]:
        try:
            jid = uuid.UUID(job_id)
        except ValueError:
            raise HTTPException(status_code=400, detail={"code": "INVALID_JOB_ID"})
        worker = get_worker()
        if worker is not None and worker.cancel(jid):
            return {"cancelled": True}
        raise HTTPException(status_code=404, detail={"code": "JOB_NOT_FOUND"})

    return router
