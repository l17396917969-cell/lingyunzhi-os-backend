# tests/e2e/test_ingestion_e2e.py
import asyncio
import pathlib
from typing import Any

import pytest
from cryptography.fernet import Fernet
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from onto_platform.app import create_app
from onto_platform.auth import Scope, generate_token
from onto_platform.token_store import insert_token
from onto_platform.ingestion.llm_client import LLMResponse, LLMToolCall, StubLiteLLM

pytestmark = [pytest.mark.asyncio, pytest.mark.e2e]

FIXTURES = pathlib.Path(__file__).resolve().parents[1] / "fixtures"


def _put_call(rid: str, api_name: str, reason: str) -> LLMToolCall:
    return LLMToolCall(
        id=f"c-{rid}",
        name="working_put_object_type",
        arguments={
            "definition": {
                "rid": rid,
                "api_name": api_name,
                "lifecycle_status": "ACTIVE",
            }
        },
        reason=reason,
    )


@pytest.fixture
async def setup(postgres_url: str, monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path) -> Any:
    monkeypatch.setenv("ONTO_DATABASE_URL", postgres_url)
    monkeypatch.setenv("ONTO_SECRET_KEY", Fernet.generate_key().decode())
    monkeypatch.setenv("ONTO_INGESTION_DATA_DIR", str(tmp_path))
    engine = create_async_engine(postgres_url, future=True)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        await s.execute(text("DELETE FROM api_tokens"))
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
    plain = generate_token()
    async with factory() as s:
        await insert_token(s, plain, Scope.editor, "ed", None)
        await s.commit()
    app = create_app()
    # Replace the worker's LLM with a scripted stub
    app.state.worker.llm = StubLiteLLM(
        responses=[
            LLMResponse(
                content=None,
                tool_calls=[
                    _put_call(
                        "ri.obj.aaaaaaaa-aaaa-aaaa-aaaa-000000000001",
                        "material",
                        "MD_MATERIAL holds parts; modeled as ObjectType material",
                    ),
                ],
            ),
            LLMResponse(
                content=None,
                tool_calls=[
                    _put_call(
                        "ri.obj.aaaaaaaa-aaaa-aaaa-aaaa-000000000002",
                        "station",
                        "MD_STATION holds workshop locations",
                    ),
                ],
            ),
            LLMResponse(
                content=None,
                tool_calls=[
                    _put_call(
                        "ri.obj.aaaaaaaa-aaaa-aaaa-aaaa-000000000003",
                        "warehouse_location",
                        "MD_WAREHOUSE_LOCATION holds storage bins",
                    ),
                ],
            ),
            LLMResponse(
                content=None,
                tool_calls=[
                    _put_call(
                        "ri.obj.aaaaaaaa-aaaa-aaaa-aaaa-000000000004",
                        "delivery_task",
                        "BO_DELIVERY_TASK_DETAIL holds a shipment",
                    ),
                ],
            ),
            LLMResponse(content="ontology built", tool_calls=[]),
        ]
    )
    yield app, plain, factory
    await engine.dispose()


async def test_ingestion_e2e_happy_path(setup: Any) -> None:
    app, token, factory = setup
    ddl = (FIXTURES / "sql" / "logistics_ddl.sql").read_text()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        # upload DDL
        r1 = await c.post(
            "/admin/ingestion/uploads",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": ("logistics_ddl.sql", ddl.encode(), "text/plain")},
        )
        assert r1.status_code == 200, r1.text
        ddl_id = r1.json()["upload_id"]

        # submit the job
        r2 = await c.post(
            "/admin/ingestion/jobs",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "upload_ids": [ddl_id],
                "mode": "replace",
                "instructions": "Build the logistics ontology.",
            },
        )
        assert r2.status_code == 200, r2.text
        job_id = r2.json()["job_id"]

        # Poll until terminal (up to ~12 seconds)
        body: dict[str, Any] = {}
        for _ in range(60):
            r3 = await c.get(
                f"/admin/ingestion/jobs/{job_id}",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert r3.status_code == 200, r3.text
            body = r3.json()
            if body["status"] in {"imported", "failed", "cancelled"}:
                break
            await asyncio.sleep(0.2)

        assert body["status"] == "imported", body
        assert body["decisions_report"]["imported_entity_counts"]["object_types"] >= 4

    # Load staging and verify expected api_names are present
    async with factory() as s:
        from onto_platform.registry.store import RegistryStore, Env

        snap = await RegistryStore().load(s, Env.staging)
    api_names = {v.api_name for v in snap.registry.object_types.values()}
    assert {"material", "station", "warehouse_location", "delivery_task"}.issubset(
        api_names
    ), f"Missing types — found: {api_names}"
