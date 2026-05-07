import pytest
from cryptography.fernet import Fernet
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from onto_platform.config import Settings
from onto_platform.ingestion.store import IngestionStore, JobStatus, ImportMode
from onto_platform.ingestion.workers import (
    IngestionWorker,
    run_one_job,
)
from onto_platform.ingestion.llm_client import LLMResponse, LLMToolCall, StubLiteLLM

pytestmark = pytest.mark.asyncio


@pytest.fixture
async def factory(postgres_url, monkeypatch, tmp_path):
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
                "UPDATE registries SET payload='{\"version\":\"__empty__\","
                "\"shared_property_types\":{},\"interface_types\":{},"
                "\"object_types\":{},\"link_types\":{},\"action_types\":{}}'::jsonb, version=0"
            )
        )
        await s.commit()
    yield f
    await engine.dispose()


async def test_worker_runs_job_to_imported(factory, tmp_path):
    # Seed an upload (a tiny SQL file) and create a job
    sql_file = tmp_path / "x.sql"
    sql_file.write_text("CREATE TABLE T (id INT);")
    store = IngestionStore()
    async with factory() as s:
        up_id = await store.insert_upload(
            s,
            filename="x.sql",
            kind="sql",
            size_bytes=sql_file.stat().st_size,
            sha256="abc",
            path=str(sql_file),
            created_by_token_id=None,
        )
        job_id = await store.create_job(
            s,
            mode=ImportMode.replace,
            instructions=None,
            upload_ids=[up_id],
            created_by_token_id=None,
        )
        await s.commit()

    stub = StubLiteLLM(
        responses=[
            LLMResponse(
                content=None,
                tool_calls=[
                    LLMToolCall(
                        id="c1",
                        name="working_put_object_type",
                        arguments={
                            "definition": {
                                "rid": "ri.obj.aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                                "api_name": "t",
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
    await run_one_job(factory, job_id, llm=stub, settings=settings)

    async with factory() as s:
        job = await store.get_job(s, job_id)
    assert job.status is JobStatus.imported
    assert job.staging_version_after is not None


async def test_worker_step_cap_marks_failed(factory, tmp_path):
    sql_file = tmp_path / "x.sql"
    sql_file.write_text("CREATE TABLE T (id INT);")
    store = IngestionStore()
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
            mode=ImportMode.replace,
            instructions=None,
            upload_ids=[up_id],
            created_by_token_id=None,
        )
        await s.commit()
    forever = LLMResponse(
        content=None,
        tool_calls=[
            LLMToolCall(
                id="c",
                name="working_put_object_type",
                arguments={
                    "definition": {
                        "rid": "ri.obj.aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                        "api_name": "t",
                        "lifecycle_status": "ACTIVE",
                    }
                },
                reason="loop",
            )
        ],
    )
    stub = StubLiteLLM(responses=[forever] * 5)
    settings = Settings()
    settings.llm_max_steps = 2
    await run_one_job(factory, jid, llm=stub, settings=settings)
    async with factory() as s:
        job = await store.get_job(s, jid)
    assert job.status is JobStatus.failed
    assert job.error_code == "STEP_CAP_EXCEEDED"
