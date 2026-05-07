"""Integration tests for the onto-admin CLI."""
from __future__ import annotations

import json
import os
import subprocess

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

pytestmark = pytest.mark.asyncio


@pytest.fixture
def env(postgres_url: str) -> dict[str, str]:
    e = os.environ.copy()
    e["ONTO_DATABASE_URL"] = postgres_url
    e["ONTO_SECRET_KEY"] = "0" * 44
    return e


def test_cli_help(env: dict[str, str]) -> None:
    r = subprocess.run(
        ["uv", "run", "python", "-m", "onto_platform.cli", "--help"],
        capture_output=True,
        text=True,
        env=env,
    )
    assert r.returncode == 0
    assert "bootstrap-admin" in r.stdout


def test_cli_bootstrap_admin_emits_token_when_empty(env: dict[str, str]) -> None:
    import asyncio

    async def wipe() -> None:
        engine = create_async_engine(env["ONTO_DATABASE_URL"], future=True)
        async with engine.connect() as c:
            await c.execute(text("DELETE FROM api_tokens"))
            await c.commit()
        await engine.dispose()

    asyncio.run(wipe())
    r = subprocess.run(
        ["uv", "run", "python", "-m", "onto_platform.cli", "bootstrap-admin"],
        capture_output=True,
        text=True,
        env=env,
    )
    assert r.returncode == 0
    assert "ADMIN BOOTSTRAP TOKEN:" in r.stdout


def test_cli_dump_registry_to_stdout(env: dict[str, str]) -> None:
    r = subprocess.run(
        [
            "uv",
            "run",
            "python",
            "-m",
            "onto_platform.cli",
            "dump-registry",
            "--env",
            "production",
            "--out",
            "-",
        ],
        capture_output=True,
        text=True,
        env=env,
    )
    assert r.returncode == 0
    payload = json.loads(r.stdout)
    assert "object_types" in payload


def test_cli_force_revoke_all_tokens(env: dict[str, str]) -> None:
    r = subprocess.run(
        ["uv", "run", "python", "-m", "onto_platform.cli", "force-revoke-all-tokens"],
        capture_output=True,
        text=True,
        env=env,
    )
    assert r.returncode == 0
    assert "revoked" in r.stdout
