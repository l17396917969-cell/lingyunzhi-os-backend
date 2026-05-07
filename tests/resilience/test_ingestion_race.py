# tests/resilience/test_ingestion_race.py
"""Resilience test: promote-during-ingestion yields STALE_VERSION.

§11.5 of the design spec: when staging is modified by another principal
while an ingestion job is running, the worker's final save call detects
the version mismatch and marks the job as failed with error_code=STALE_VERSION.
"""
import asyncio
from typing import Any

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from onto_platform.config import Settings
from onto_platform.ingestion.llm_client import LLMResponse, LLMToolCall, StubLiteLLM
from onto_platform.ingestion.store import ImportMode, IngestionStore, JobStatus
from onto_platform.ingestion.workers import run_one_job
from onto_platform.proto_models import OntologyRegistry
from onto_platform.registry.store import Env, RegistryStore

pytestmark = pytest.mark.asyncio


class _SlowStubLiteLLM(StubLiteLLM):
    """StubLiteLLM that yields to the event loop before each response.

    This ensures concurrent asyncio tasks (e.g. the interruptor) get a
    chance to run between LLM calls, making the race condition reproducible.
    """

    async def acompletion(
        self,
        *,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        tool_choice: str = "auto",
    ) -> LLMResponse:
        # Yield to the event loop so any pending tasks can run
        await asyncio.sleep(0)
        return await super().acompletion(
            messages=messages, tools=tools, tool_choice=tool_choice
        )


@pytest.fixture
async def factory(postgres_url: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> Any:
    monkeypatch.setenv("ONTO_DATABASE_URL", postgres_url)
    monkeypatch.setenv("ONTO_SECRET_KEY", Fernet.generate_key().decode())
    monkeypatch.setenv("ONTO_INGESTION_DATA_DIR", str(tmp_path))
    engine = create_async_engine(postgres_url, future=True)
    f = async_sessionmaker(engine, expire_on_commit=False)
    async with f() as s:
        await s.execute(text("DELETE FROM ingestion_uploads"))
        await s.execute(text("DELETE FROM ingestion_jobs"))
        await s.execute(
            text(
                "UPDATE registries SET "
                "payload='{\"version\":\"__empty__\","
                "\"shared_property_types\":{},\"interface_types\":{},"
                "\"object_types\":{},\"link_types\":{},\"action_types\":{}}'::jsonb, "
                "version=0"
            )
        )
        await s.commit()
    yield f
    await engine.dispose()


async def test_promote_during_ingestion_yields_stale_version(factory: Any, tmp_path: Any) -> None:
    """Concurrently run a 2-step ingestion job and interrupt staging mid-run.

    The interruptor bumps staging after the agent has started but before
    the worker tries to import.  The worker must detect the version mismatch
    and mark the job failed with error_code=STALE_VERSION.
    """
    sql_file = tmp_path / "x.sql"
    sql_file.write_text("CREATE TABLE T (id INT);")
    store = IngestionStore()
    rstore = RegistryStore()

    async with factory() as s:
        up_id = await store.insert_upload(
            s,
            filename="x.sql",
            kind="sql",
            size_bytes=10,
            sha256="a",
            path=str(sql_file),
            created_by_token_id=None,
        )
        jid = await store.create_job(
            s,
            mode=ImportMode.merge,
            instructions=None,
            upload_ids=[up_id],
            created_by_token_id=None,
        )
        await s.commit()

    # While the job is running (2-step stub: one tool call + final),
    # another writer bumps staging to make the version stale.
    # The interruptor fires immediately (no sleep needed) because the
    # _SlowStubLiteLLM yields to the event loop between calls.
    async def _interrupt() -> None:
        async with factory() as s:
            snap = await rstore.load(s, Env.staging)
            # Save a different registry to bump the version ahead
            bumped_reg = OntologyRegistry(
                version="bumped",
                shared_property_types={},
                interface_types={},
                object_types={},
                link_types={},
                action_types={},
            )
            await rstore.save(
                s,
                Env.staging,
                bumped_reg,
                expected_version=snap.version,
                token_label="other-principal",
            )
            await s.commit()

    stub = _SlowStubLiteLLM(
        responses=[
            LLMResponse(
                content=None,
                tool_calls=[
                    LLMToolCall(
                        id="c",
                        name="working_put_object_type",
                        arguments={
                            "definition": {
                                "rid": "ri.obj.aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                                "api_name": "x",
                                "lifecycle_status": "ACTIVE",
                            }
                        },
                        reason="seed",
                    )
                ],
            ),
            LLMResponse(content="done", tool_calls=[]),
        ]
    )

    settings = Settings()
    # Ensure llm_max_steps >= 2 so the agent processes one tool call + ends
    settings.llm_max_steps = 10

    # Schedule the interruptor as a background task before the job starts;
    # _SlowStubLiteLLM yields to the event loop between calls so the
    # interruptor runs while the agent is between its two LLM calls.
    interruptor = asyncio.create_task(_interrupt())
    await run_one_job(factory, jid, llm=stub, settings=settings)
    await interruptor

    async with factory() as s:
        job = await store.get_job(s, jid)

    assert job.status is JobStatus.failed, f"Expected failed, got {job.status!r}"
    assert job.error_code == "STALE_VERSION", (
        f"Expected STALE_VERSION, got {job.error_code!r}"
    )
