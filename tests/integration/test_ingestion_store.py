import uuid
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from onto_platform.ingestion.store import (
    IngestionStore,
    JobStatus,
    ImportMode,
)

pytestmark = pytest.mark.asyncio


@pytest.fixture
async def factory(postgres_url):
    engine = create_async_engine(postgres_url, future=True)
    f = async_sessionmaker(engine, expire_on_commit=False)
    async with f() as s:
        await s.execute(text("DELETE FROM ingestion_uploads"))
        await s.execute(text("DELETE FROM ingestion_jobs"))
        await s.commit()
    yield f
    await engine.dispose()


async def test_insert_upload_and_create_job(factory):
    store = IngestionStore()
    async with factory() as s:
        up_id = await store.insert_upload(
            s,
            filename="x.sql",
            kind="sql",
            size_bytes=42,
            sha256="abc" * 16,
            path="/tmp/x.sql",
            created_by_token_id=None,
        )
        job_id = await store.create_job(
            s,
            mode=ImportMode.replace,
            instructions="seed",
            upload_ids=[up_id],
            created_by_token_id=None,
        )
        await s.commit()
    async with factory() as s:
        job = await store.get_job(s, job_id)
    assert job.status is JobStatus.queued
    assert job.mode is ImportMode.replace


async def test_update_status_transitions(factory):
    store = IngestionStore()
    async with factory() as s:
        up_id = await store.insert_upload(
            s,
            filename="x.sql",
            kind="sql",
            size_bytes=1,
            sha256="abc",
            path="/tmp/x",
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
    async with factory() as s:
        await store.set_status(
            s, jid, JobStatus.extracting, phase="extracting", progress=10
        )
        await s.commit()
    async with factory() as s:
        job = await store.get_job(s, jid)
    assert job.status is JobStatus.extracting
    assert job.progress_pct == 10


async def test_list_uploads_for_job(factory):
    store = IngestionStore()
    async with factory() as s:
        up1 = await store.insert_upload(
            s,
            filename="a.sql",
            kind="sql",
            size_bytes=10,
            sha256="aaa",
            path="/tmp/a.sql",
            created_by_token_id=None,
        )
        up2 = await store.insert_upload(
            s,
            filename="b.pdf",
            kind="pdf",
            size_bytes=20,
            sha256="bbb",
            path="/tmp/b.pdf",
            created_by_token_id=None,
        )
        jid = await store.create_job(
            s,
            mode=ImportMode.replace,
            instructions=None,
            upload_ids=[up1, up2],
            created_by_token_id=None,
        )
        await s.commit()
    async with factory() as s:
        uploads = await store.list_uploads_for_job(s, jid)
    assert len(uploads) == 2
    filenames = {u.filename for u in uploads}
    assert filenames == {"a.sql", "b.pdf"}


async def test_set_status_with_error_details(factory):
    store = IngestionStore()
    async with factory() as s:
        up_id = await store.insert_upload(
            s,
            filename="x.sql",
            kind="sql",
            size_bytes=1,
            sha256="xyz",
            path="/tmp/x.sql",
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
    async with factory() as s:
        await store.set_status(
            s,
            jid,
            JobStatus.failed,
            phase="error",
            error_code="STEP_CAP_EXCEEDED",
            error_details={"max_steps": 5},
            mark_finished=True,
        )
        await s.commit()
    async with factory() as s:
        job = await store.get_job(s, jid)
    assert job.status is JobStatus.failed
    assert job.error_code == "STEP_CAP_EXCEEDED"
    assert job.error_details is not None
    assert job.error_details["max_steps"] == 5
    assert job.finished_at is not None
