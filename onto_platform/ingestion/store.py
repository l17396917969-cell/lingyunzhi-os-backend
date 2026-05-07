from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from onto_platform.registry.imports import ImportMode as ImportMode  # re-export


class JobStatus(str, Enum):
    queued = "queued"
    extracting = "extracting"
    agent_running = "agent_running"
    validating = "validating"
    imported = "imported"
    failed = "failed"
    cancelled = "cancelled"


@dataclass
class Upload:
    id: uuid.UUID
    job_id: Optional[uuid.UUID]
    filename: str
    kind: str
    size_bytes: int
    sha256: str
    path: str


@dataclass
class Job:
    id: uuid.UUID
    mode: ImportMode
    instructions: Optional[str]
    status: JobStatus
    phase_message: str
    progress_pct: int
    decisions_report: Optional[dict]  # type: ignore[type-arg]
    staging_version_after: Optional[int]
    error_code: Optional[str]
    error_details: Optional[dict]  # type: ignore[type-arg]
    created_at: datetime
    started_at: Optional[datetime]
    finished_at: Optional[datetime]


class IngestionStore:
    async def insert_upload(
        self,
        session: AsyncSession,
        *,
        filename: str,
        kind: str,
        size_bytes: int,
        sha256: str,
        path: str,
        created_by_token_id: Optional[uuid.UUID],
    ) -> uuid.UUID:
        row = await session.execute(
            text(
                "INSERT INTO ingestion_uploads "
                "(filename, kind, size_bytes, sha256, path, created_by_token_id) "
                "VALUES (:f, :k, :s, :h, :p, :c) RETURNING id"
            ),
            {
                "f": filename,
                "k": kind,
                "s": size_bytes,
                "h": sha256,
                "p": path,
                "c": str(created_by_token_id) if created_by_token_id else None,
            },
        )
        return uuid.UUID(str(row.scalar_one()))

    async def list_orphan_uploads(
        self, session: AsyncSession, older_than_minutes: int
    ) -> list[Upload]:
        rows = await session.execute(
            text(
                "SELECT id, job_id, filename, kind, size_bytes, sha256, path "
                "FROM ingestion_uploads WHERE job_id IS NULL "
                "AND created_at < now() - (:m * interval '1 minute')"
            ),
            {"m": older_than_minutes},
        )
        return [
            Upload(
                id=uuid.UUID(str(r.id)),
                job_id=uuid.UUID(str(r.job_id)) if r.job_id else None,
                filename=r.filename,
                kind=r.kind,
                size_bytes=r.size_bytes,
                sha256=r.sha256,
                path=r.path,
            )
            for r in rows
        ]

    async def create_job(
        self,
        session: AsyncSession,
        *,
        mode: ImportMode,
        instructions: Optional[str],
        upload_ids: list[uuid.UUID],
        created_by_token_id: Optional[uuid.UUID],
    ) -> uuid.UUID:
        row = await session.execute(
            text(
                "INSERT INTO ingestion_jobs (mode, instructions, created_by_token_id) "
                "VALUES (:m, :i, :c) RETURNING id"
            ),
            {
                "m": mode.value,
                "i": instructions,
                "c": str(created_by_token_id) if created_by_token_id else None,
            },
        )
        job_id = uuid.UUID(str(row.scalar_one()))
        for up in upload_ids:
            await session.execute(
                text(
                    "UPDATE ingestion_uploads SET job_id = :j "
                    "WHERE id = :u AND job_id IS NULL"
                ),
                {"j": str(job_id), "u": str(up)},
            )
        return job_id

    async def get_job(self, session: AsyncSession, job_id: uuid.UUID) -> Job:
        row = await session.execute(
            text("SELECT * FROM ingestion_jobs WHERE id = :i"),
            {"i": str(job_id)},
        )
        rec = row.one()
        return Job(
            id=uuid.UUID(str(rec.id)),
            mode=ImportMode(rec.mode),
            instructions=rec.instructions,
            status=JobStatus(rec.status),
            phase_message=rec.phase_message or "",
            progress_pct=rec.progress_pct,
            decisions_report=rec.decisions_report,
            staging_version_after=rec.staging_version_after,
            error_code=rec.error_code,
            error_details=rec.error_details,
            created_at=rec.created_at,
            started_at=rec.started_at,
            finished_at=rec.finished_at,
        )

    async def list_uploads_for_job(
        self, session: AsyncSession, job_id: uuid.UUID
    ) -> list[Upload]:
        rows = await session.execute(
            text(
                "SELECT id, job_id, filename, kind, size_bytes, sha256, path "
                "FROM ingestion_uploads WHERE job_id = :j ORDER BY created_at"
            ),
            {"j": str(job_id)},
        )
        return [
            Upload(
                id=uuid.UUID(str(r.id)),
                job_id=uuid.UUID(str(r.job_id)) if r.job_id else None,
                filename=r.filename,
                kind=r.kind,
                size_bytes=r.size_bytes,
                sha256=r.sha256,
                path=r.path,
            )
            for r in rows
        ]

    async def set_status(
        self,
        session: AsyncSession,
        job_id: uuid.UUID,
        status: JobStatus,
        *,
        phase: str = "",
        progress: Optional[int] = None,
        error_code: Optional[str] = None,
        error_details: Optional[dict] = None,  # type: ignore[type-arg]
        decisions_report: Optional[dict] = None,  # type: ignore[type-arg]
        staging_version_after: Optional[int] = None,
        mark_started: bool = False,
        mark_finished: bool = False,
    ) -> None:
        await session.execute(
            text(
                "UPDATE ingestion_jobs SET "
                "status = :s, "
                "phase_message = :p, "
                "progress_pct = COALESCE(:pct, progress_pct), "
                "error_code = COALESCE(:ec, error_code), "
                "error_details = COALESCE(CAST(:ed AS JSONB), error_details), "
                "decisions_report = COALESCE(CAST(:dr AS JSONB), decisions_report), "
                "staging_version_after = COALESCE(:sv, staging_version_after), "
                "started_at = CASE WHEN :ms THEN COALESCE(started_at, now()) "
                "             ELSE started_at END, "
                "finished_at = CASE WHEN :mf THEN now() ELSE finished_at END "
                "WHERE id = :i"
            ),
            {
                "s": status.value,
                "p": phase,
                "pct": progress,
                "ec": error_code,
                "ed": json.dumps(error_details) if error_details is not None else None,
                "dr": json.dumps(decisions_report) if decisions_report is not None else None,
                "sv": staging_version_after,
                "ms": mark_started,
                "mf": mark_finished,
                "i": str(job_id),
            },
        )
