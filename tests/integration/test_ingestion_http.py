import pytest
from cryptography.fernet import Fernet
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from onto_platform.app import create_app
from onto_platform.auth import Scope, generate_token
from onto_platform.token_store import insert_token

pytestmark = pytest.mark.asyncio


@pytest.fixture
async def setup(postgres_url, monkeypatch, tmp_path):
    monkeypatch.setenv("ONTO_DATABASE_URL", postgres_url)
    monkeypatch.setenv("ONTO_SECRET_KEY", Fernet.generate_key().decode())
    monkeypatch.setenv("ONTO_INGESTION_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("ONTO_INGESTION_MAX_UPLOAD_BYTES", "5000")
    monkeypatch.setenv("ONTO_INGESTION_MAX_FILES_PER_JOB", "3")
    engine = create_async_engine(postgres_url, future=True)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        await s.execute(text("DELETE FROM api_tokens"))
        await s.execute(text("DELETE FROM ingestion_uploads"))
        await s.execute(text("DELETE FROM ingestion_jobs"))
        await s.commit()
    plain = generate_token()
    async with factory() as s:
        await insert_token(s, plain, Scope.editor, "ed", None)
        await s.commit()
    yield create_app(), plain, factory
    await engine.dispose()


async def test_upload_then_create_job(setup):
    app, token, _ = setup
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post(
            "/admin/ingestion/uploads",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": ("x.sql", b"CREATE TABLE T (id INT);", "text/plain")},
        )
        assert r.status_code == 200, r.text
        upload_id = r.json()["upload_id"]
        r2 = await c.post(
            "/admin/ingestion/jobs",
            headers={"Authorization": f"Bearer {token}"},
            json={"upload_ids": [upload_id], "mode": "replace"},
        )
        assert r2.status_code == 200, r2.text
        job_id = r2.json()["job_id"]
        # immediate fetch — likely still queued or running
        r3 = await c.get(
            f"/admin/ingestion/jobs/{job_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r3.status_code == 200, r3.text
        assert r3.json()["status"] in {
            "queued", "extracting", "agent_running", "validating", "imported", "failed",
        }


async def test_upload_too_large(setup):
    app, token, _ = setup
    big = b"x" * 6000
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post(
            "/admin/ingestion/uploads",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": ("big.sql", big, "text/plain")},
        )
    assert r.status_code == 413
    assert r.json()["detail"]["code"] == "UPLOAD_TOO_LARGE"


async def test_too_many_files_per_job(setup):
    app, token, _ = setup
    upload_ids = []
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        for i in range(4):
            r = await c.post(
                "/admin/ingestion/uploads",
                headers={"Authorization": f"Bearer {token}"},
                files={"file": (f"x{i}.sql", b"SELECT 1;", "text/plain")},
            )
            assert r.status_code == 200, r.text
            upload_ids.append(r.json()["upload_id"])
        r = await c.post(
            "/admin/ingestion/jobs",
            headers={"Authorization": f"Bearer {token}"},
            json={"upload_ids": upload_ids, "mode": "merge"},
        )
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "JOB_TOO_LARGE"


async def test_upload_unsupported_extension(setup):
    app, token, _ = setup
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post(
            "/admin/ingestion/uploads",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": ("readme.txt", b"hello", "text/plain")},
        )
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "UPLOAD_KIND_UNSUPPORTED"
