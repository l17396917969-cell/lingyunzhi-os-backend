# tests/integration/test_bootstrap.py
import io
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from onto_platform.bootstrap import bootstrap_admin_token_if_needed
from onto_platform.auth import Scope
from onto_platform.token_store import lookup_token

pytestmark = pytest.mark.asyncio


@pytest.fixture
async def session_factory(postgres_url):
    engine = create_async_engine(postgres_url, future=True)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    # ensure clean api_tokens for this test
    async with factory() as s:
        await s.execute(text("DELETE FROM api_tokens"))
        await s.commit()
    yield factory
    await engine.dispose()


async def test_bootstrap_emits_token_when_table_empty(session_factory):
    out = io.StringIO()
    plaintext = await bootstrap_admin_token_if_needed(session_factory, stdout=out)
    assert plaintext is not None
    assert plaintext.startswith("op_")
    assert "ADMIN BOOTSTRAP TOKEN:" in out.getvalue()
    async with session_factory() as s:
        result = await lookup_token(s, plaintext)
    assert result is not None
    assert result.scope is Scope.admin
    assert result.label == "bootstrap"


async def test_bootstrap_is_noop_when_token_exists(session_factory):
    out1 = io.StringIO()
    plain1 = await bootstrap_admin_token_if_needed(session_factory, stdout=out1)
    assert plain1 is not None
    out2 = io.StringIO()
    plain2 = await bootstrap_admin_token_if_needed(session_factory, stdout=out2)
    assert plain2 is None
    assert "ADMIN BOOTSTRAP TOKEN:" not in out2.getvalue()
