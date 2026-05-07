# tests/integration/test_token_store.py
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from onto_platform.auth import Scope, generate_token
from onto_platform.token_store import (
    insert_token, lookup_token, revoke_token, list_tokens,
    TokenLookupResult,
)

pytestmark = pytest.mark.asyncio


@pytest.fixture
async def session_factory(postgres_url):
    engine = create_async_engine(postgres_url, future=True)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    await engine.dispose()


async def test_insert_and_lookup(session_factory):
    plaintext = generate_token()
    async with session_factory() as s:
        token_id = await insert_token(s, plaintext, Scope.editor, "test-token", None)
        await s.commit()
    async with session_factory() as s:
        result = await lookup_token(s, plaintext)
    assert isinstance(result, TokenLookupResult)
    assert result.token_id == token_id
    assert result.scope is Scope.editor
    assert result.label == "test-token"


async def test_lookup_unknown_returns_none(session_factory):
    async with session_factory() as s:
        result = await lookup_token(s, generate_token())
    assert result is None


async def test_revoke_marks_lookup_as_revoked(session_factory):
    plaintext = generate_token()
    async with session_factory() as s:
        token_id = await insert_token(s, plaintext, Scope.read, "to-revoke", None)
        await s.commit()
    async with session_factory() as s:
        await revoke_token(s, token_id)
        await s.commit()
    async with session_factory() as s:
        result = await lookup_token(s, plaintext)
    assert result is None  # revoked tokens fail lookup


async def test_list_tokens_returns_metadata(session_factory):
    async with session_factory() as s:
        await insert_token(s, generate_token(), Scope.read, "alpha", None)
        await insert_token(s, generate_token(), Scope.admin, "beta", None)
        await s.commit()
    async with session_factory() as s:
        rows = await list_tokens(s)
    labels = {r.label for r in rows}
    assert {"alpha", "beta"}.issubset(labels)
