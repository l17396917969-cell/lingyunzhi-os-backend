# tests/integration/test_audit.py
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from onto_platform.audit import AuditLogWriter, summarize_args

pytestmark = pytest.mark.asyncio


@pytest.fixture
async def factory(postgres_url):
    engine = create_async_engine(postgres_url, future=True)
    f = async_sessionmaker(engine, expire_on_commit=False)
    async with f() as s:
        await s.execute(text("DELETE FROM audit_log"))
        await s.commit()
    yield f
    await engine.dispose()


def test_summarize_redacts_dsn_password():
    args = {"dsn": "postgres://user:topsecret@host:5432/db"}
    out = summarize_args("add_connection", args)
    assert "topsecret" not in repr(out)


def test_summarize_truncates_long_sql():
    args = {"sql": "SELECT " + "x" * 1000 + " FROM t"}
    out = summarize_args("query_sql", args)
    assert out["sql_truncated"] is True
    assert len(out["sql"]) == 500


def test_summarize_summarizes_registry_payload():
    args = {"registry": {"object_types": {"a": {}, "b": {}}, "link_types": {"x": {}}}}
    out = summarize_args("import_full_registry_to_staging", args)
    assert "entity_counts" in out
    assert out["entity_counts"]["object_types"] == 2


async def test_audit_log_writer_writes_row(factory):
    w = AuditLogWriter()
    async with factory() as s:
        await w.record(
            s,
            tool="put_object_type",
            token_id=None, token_label="alice", scope="editor",
            args={"definition": {"rid": "ri.obj.x"}},
            outcome="ok", error_code=None,
        )
        await s.commit()
        rows = (await s.execute(text("SELECT tool, outcome FROM audit_log"))).all()
    assert any(r.tool == "put_object_type" and r.outcome == "ok" for r in rows)


async def test_audit_log_writer_does_not_persist_token_plaintext(factory):
    w = AuditLogWriter()
    async with factory() as s:
        await w.record(
            s,
            tool="mint_token",
            token_id=None, token_label="admin", scope="admin",
            args={"scope": "read", "label": "x"},
            outcome="ok", error_code=None,
            return_value={"token": "op_LEAKED_VALUE", "token_id": "id-1"},
        )
        await s.commit()
        rows = (await s.execute(text("SELECT args_summary FROM audit_log WHERE tool='mint_token'"))).all()
    assert all("op_LEAKED_VALUE" not in repr(r.args_summary) for r in rows)
