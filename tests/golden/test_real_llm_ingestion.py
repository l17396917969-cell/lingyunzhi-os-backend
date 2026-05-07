# tests/golden/test_real_llm_ingestion.py
import asyncio
import datetime
import json
import os
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
from onto_platform.ingestion.llm_client import LiteLLMClient

pytestmark = [pytest.mark.asyncio, pytest.mark.live_llm]

FIXTURES = pathlib.Path(__file__).resolve().parents[1] / "fixtures"
RUNS_DIR = FIXTURES / "golden" / "runs"


def _matrix() -> list[tuple[str, str, str]]:
    """Parse ONTO_GOLDEN_MATRIX env var into list of (provider, model, base_url) triples.

    Format: "provider|model|base_url,provider2|model2|base_url2"
    Returns an empty list if the env var is unset or empty — pytest.parametrize
    with an empty list yields zero test cases (no error).
    """
    raw = os.getenv("ONTO_GOLDEN_MATRIX", "")
    out: list[tuple[str, str, str]] = []
    for triple in (raw.split(",") if raw else []):
        parts = triple.split("|")
        if len(parts) == 3:
            out.append((parts[0].strip(), parts[1].strip(), parts[2].strip()))
    return out


@pytest.mark.skipif(
    os.getenv("RUN_LIVE_LLM_TESTS") != "1",
    reason="RUN_LIVE_LLM_TESTS not set to '1'",
)
@pytest.mark.parametrize("provider,model,base_url", _matrix() or [("_skip_", "_skip_", "_skip_")])
async def test_real_llm_logistics_ingestion(
    postgres_url: str,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: pathlib.Path,
    provider: str,
    model: str,
    base_url: str,
) -> None:
    """Release-gated golden test — runs real LLM calls against the logistics DDL fixture.

    Gated by RUN_LIVE_LLM_TESTS=1.  Per-provider API key is read from
    <PROVIDER>_API_KEY env var (e.g. VOLCENGINE_API_KEY, OPENAI_API_KEY).
    Results are saved to tests/fixtures/golden/runs/<date>/<provider>-<model>.json
    for historical regression diffing.
    """
    api_key = os.environ.get(f"{provider.upper()}_API_KEY", "")
    monkeypatch.setenv("ONTO_DATABASE_URL", postgres_url)
    monkeypatch.setenv("ONTO_SECRET_KEY", Fernet.generate_key().decode())
    monkeypatch.setenv("ONTO_INGESTION_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("ONTO_LLM_PROVIDER", provider)
    monkeypatch.setenv("ONTO_LLM_BASE_URL", base_url)
    monkeypatch.setenv("ONTO_LLM_API_KEY", api_key)
    monkeypatch.setenv("ONTO_LLM_MODEL", model)

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
        await insert_token(s, plain, Scope.editor, "golden", None)
        await s.commit()

    app = create_app()
    app.state.worker.llm = LiteLLMClient(
        model=model,
        api_base=base_url,
        api_key=api_key,
        request_timeout_s=120,
    )

    ddl = (FIXTURES / "sql" / "logistics_ddl.sql").read_text()

    body: dict[str, Any] = {}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r1 = await c.post(
            "/admin/ingestion/uploads",
            headers={"Authorization": f"Bearer {plain}"},
            files={"file": ("logistics_ddl.sql", ddl.encode(), "text/plain")},
        )
        assert r1.status_code == 200, r1.text
        ddl_id = r1.json()["upload_id"]

        r2 = await c.post(
            "/admin/ingestion/jobs",
            headers={"Authorization": f"Bearer {plain}"},
            json={
                "upload_ids": [ddl_id],
                "mode": "replace",
                "instructions": (
                    "Build a logistics ontology including Material, Station, "
                    "WarehouseLocation, DeliveryTask."
                ),
            },
        )
        assert r2.status_code == 200, r2.text
        job_id = r2.json()["job_id"]

        # Poll up to 15 minutes (900 iterations × 1s)
        for _ in range(900):
            r3 = await c.get(
                f"/admin/ingestion/jobs/{job_id}",
                headers={"Authorization": f"Bearer {plain}"},
            )
            body = r3.json()
            if body["status"] in {"imported", "failed", "cancelled"}:
                break
            await asyncio.sleep(1)

    await engine.dispose()

    # Save run output for historical regression diffing
    today = datetime.date.today().isoformat()
    model_slug = model.replace("/", "_")
    target = RUNS_DIR / today / f"{provider}-{model_slug}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(body, indent=2, ensure_ascii=False))

    # Structural assertions
    assert body["status"] == "imported", body
    counts = body["decisions_report"]["imported_entity_counts"]
    assert counts["object_types"] >= 4, f"Expected >= 4 object_types, got: {counts}"
    assert any(
        d["tool"].startswith("working_put_object_type")
        for d in body["decisions_report"]["decisions"]
    ), "Expected at least one working_put_object_type decision"
