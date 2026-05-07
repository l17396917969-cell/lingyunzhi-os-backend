from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from typing import Optional

from sqlalchemy.ext.asyncio import async_sessionmaker

from onto_platform.config import Settings
from onto_platform.connections.store import ConnectionStore
from onto_platform.registry.crud import ValidationFailedError
from onto_platform.registry.imports import import_into_registry
from onto_platform.registry.store import Env, RegistryStore, StaleVersionError

from onto_platform.ingestion.agent import (
    AgentRunResult,
    CancellationToken,
    StepCapExceeded,
    run_agent,
)
from onto_platform.ingestion.extractors import get_extractor
from onto_platform.ingestion.extractors.types import (
    ExtractionBundle,
    ExtractionFailure,
)
from onto_platform.ingestion.llm_client import LLMClient
from onto_platform.ingestion.prompts import SYSTEM_PROMPT
from onto_platform.ingestion.store import (
    ImportMode,
    IngestionStore,
    Job,
    JobStatus,
)
from onto_platform.ingestion.working_registry import WorkingRegistry


def _user_prompt(bundle: ExtractionBundle, job_instructions: Optional[str]) -> str:
    parts: list[str] = []
    if job_instructions:
        parts.append(f"Operator instructions: {job_instructions}")
    for doc in bundle.documents:
        parts.append(f"# {doc.source_filename} ({doc.kind})")
        for sec in doc.sections:
            parts.append(f"## {sec.heading}")
            parts.append(sec.text)
    return "\n\n".join(parts)


async def run_one_job(
    session_factory: async_sessionmaker,  # type: ignore[type-arg]
    job_id: uuid.UUID,
    *,
    llm: LLMClient,
    settings: Settings,
    cancel: Optional[CancellationToken] = None,
) -> None:
    cancel = cancel or CancellationToken()
    store = IngestionStore()
    rstore = RegistryStore()
    cstore = ConnectionStore(secret_key=settings.secret_key)

    # Phase: extracting
    try:
        async with session_factory() as s:
            await store.set_status(
                s,
                job_id,
                JobStatus.extracting,
                phase="extracting files",
                progress=10,
                mark_started=True,
            )
            await s.commit()
            uploads = await store.list_uploads_for_job(s, job_id)

        bundle = ExtractionBundle(documents=[])
        for up in uploads:
            ex = get_extractor(up.kind)
            try:
                doc = await ex(up.path, up.filename)
            except ExtractionFailure as e:
                async with session_factory() as s:
                    await store.set_status(
                        s,
                        job_id,
                        JobStatus.failed,
                        phase="extraction failed",
                        error_code="EXTRACTION_FAILED",
                        error_details={
                            "failed_files": [
                                {"filename": up.filename, "reason": str(e)}
                            ]
                        },
                        mark_finished=True,
                    )
                    await s.commit()
                return
            bundle.documents.append(doc)
    except asyncio.CancelledError:
        async with session_factory() as s:
            await store.set_status(
                s, job_id, JobStatus.cancelled, phase="cancelled", mark_finished=True
            )
            await s.commit()
        return
    except Exception as e:
        async with session_factory() as s:
            await store.set_status(
                s,
                job_id,
                JobStatus.failed,
                phase="extraction error",
                error_code="EXTRACTION_FAILED",
                error_details={"reason": str(e)},
                mark_finished=True,
            )
            await s.commit()
        return

    # Phase: agent_running
    async with session_factory() as s:
        await store.set_status(
            s, job_id, JobStatus.agent_running, phase="agent running", progress=40
        )
        await s.commit()
        snap = await rstore.load(s, Env.staging)
        staging_version_at_start = snap.version
        job: Job = await store.get_job(s, job_id)
        conn_ids = {str(c.id) for c in await cstore.list_all(s)}

    if job.mode is ImportMode.replace:
        wr = WorkingRegistry.empty()
    else:
        wr = WorkingRegistry.from_registry(snap.registry)

    try:
        agent_result: AgentRunResult = await asyncio.wait_for(
            run_agent(
                wr,
                llm=llm,
                system_prompt=SYSTEM_PROMPT,
                user_prompt=_user_prompt(bundle, job.instructions),
                connection_ids=conn_ids,
                max_steps=settings.llm_max_steps,
                cancel=cancel,
            ),
            timeout=float(settings.ingestion_job_wall_clock_timeout_s),
        )
    except asyncio.TimeoutError:
        async with session_factory() as s:
            await store.set_status(
                s,
                job_id,
                JobStatus.failed,
                phase="wall-clock timeout",
                error_code="WALL_CLOCK_TIMEOUT",
                mark_finished=True,
            )
            await s.commit()
        return
    except StepCapExceeded:
        async with session_factory() as s:
            await store.set_status(
                s,
                job_id,
                JobStatus.failed,
                phase="step cap exceeded",
                error_code="STEP_CAP_EXCEEDED",
                error_details={"max_steps": settings.llm_max_steps},
                mark_finished=True,
            )
            await s.commit()
        return
    except asyncio.CancelledError:
        async with session_factory() as s:
            await store.set_status(
                s, job_id, JobStatus.cancelled, phase="cancelled", mark_finished=True
            )
            await s.commit()
        return
    except Exception as e:
        async with session_factory() as s:
            await store.set_status(
                s,
                job_id,
                JobStatus.failed,
                phase="LLM provider error",
                error_code="LLM_PROVIDER_ERROR",
                error_details={"driver_error": str(e)},
                mark_finished=True,
            )
            await s.commit()
        return

    # Phase: validating + import
    async with session_factory() as s:
        await store.set_status(
            s, job_id, JobStatus.validating, phase="validating", progress=80
        )
        await s.commit()

    try:
        async with session_factory() as s:
            new_reg = import_into_registry(
                snap.registry,
                wr.snapshot(),
                mode=job.mode,
                connection_ids=conn_ids,
            )
            new_version = await rstore.save(
                s,
                Env.staging,
                new_reg,
                expected_version=staging_version_at_start,
                token_label="ingestion",
            )
            await s.commit()
    except StaleVersionError as e:
        async with session_factory() as s:
            await store.set_status(
                s,
                job_id,
                JobStatus.failed,
                phase="stale staging",
                error_code="STALE_VERSION",
                error_details={
                    "expected_version": e.expected_version,
                    "current_version": e.current_version,
                },
                mark_finished=True,
            )
            await s.commit()
        return
    except ValidationFailedError as e:
        async with session_factory() as s:
            await store.set_status(
                s,
                job_id,
                JobStatus.failed,
                phase="validation failed",
                error_code="VALIDATION_FAILED",
                error_details={
                    "findings": [
                        {
                            "severity": f.severity.value,
                            "code": f.code,
                            "path": f.path,
                            "message": f.message,
                        }
                        for f in e.findings
                    ]
                },
                mark_finished=True,
            )
            await s.commit()
        return

    # Phase: imported
    decisions_payload: dict = {  # type: ignore[type-arg]
        "decisions": [
            {
                "tool": d.tool,
                "args_summary": d.args_summary,
                "outcome": d.outcome,
                "reason": d.reason,
                "error": d.error,
            }
            for d in agent_result.decisions
        ],
        "imported_entity_counts": {
            "shared_property_types": len(new_reg.shared_property_types),
            "interface_types": len(new_reg.interface_types),
            "object_types": len(new_reg.object_types),
            "link_types": len(new_reg.link_types),
            "action_types": len(new_reg.action_types),
        },
    }
    async with session_factory() as s:
        await store.set_status(
            s,
            job_id,
            JobStatus.imported,
            phase="imported",
            progress=100,
            decisions_report=decisions_payload,
            staging_version_after=new_version,
            mark_finished=True,
        )
        await s.commit()


@dataclass
class IngestionWorker:
    factory: async_sessionmaker  # type: ignore[type-arg]
    settings: Settings
    llm: LLMClient
    _running: dict[uuid.UUID, "asyncio.Task[None]"] = field(
        default_factory=dict, init=False, repr=False
    )

    def submit(
        self,
        job_id: uuid.UUID,
        *,
        cancel: Optional[CancellationToken] = None,
    ) -> "asyncio.Task[None]":
        task: asyncio.Task[None] = asyncio.create_task(
            run_one_job(
                self.factory,
                job_id,
                llm=self.llm,
                settings=self.settings,
                cancel=cancel,
            )
        )
        self._running[job_id] = task
        task.add_done_callback(lambda t: self._running.pop(job_id, None))
        return task

    def cancel(self, job_id: uuid.UUID) -> bool:
        task = self._running.get(job_id)
        if task is None:
            return False
        task.cancel()
        return True
