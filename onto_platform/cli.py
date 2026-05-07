"""onto-admin CLI — admin subcommands for the Onto Platform."""
from __future__ import annotations

import argparse
import asyncio
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from onto_platform.bootstrap import bootstrap_admin_token_if_needed
from onto_platform.config import Settings
from onto_platform.connections.store import ConnectionStore
from onto_platform.proto_models import OntologyRegistry
from onto_platform.registry.store import Env, RegistryStore


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="onto-admin", description="Onto Platform admin CLI")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("db-migrate", help="Run alembic upgrade head")
    sub.add_parser("bootstrap-admin", help="Print bootstrap admin token if api_tokens is empty")

    dump = sub.add_parser("dump-registry", help="Dump a registry environment to JSON")
    dump.add_argument("--env", required=True, choices=[e.value for e in Env])
    dump.add_argument("--out", required=True, help="Output path or - for stdout")

    rest = sub.add_parser("restore-registry", help="Replace a registry environment from JSON")
    rest.add_argument("--env", required=True, choices=[e.value for e in Env])
    rest.add_argument("--in", dest="inp", required=True, help="Input path")

    rot = sub.add_parser("rotate-secret", help="Re-encrypt all connection DSNs with a new Fernet key")
    rot.add_argument("--new-key", required=True, help="New Fernet secret key (base64-url, 44 chars)")

    sub.add_parser("force-revoke-all-tokens", help="Revoke every active api_token (incident response)")

    return p


async def _cmd_db_migrate(_args: argparse.Namespace) -> None:
    subprocess.run(["alembic", "upgrade", "head"], check=True)


async def _cmd_bootstrap_admin(_args: argparse.Namespace) -> None:
    settings = Settings()
    engine = create_async_engine(settings.database_url, future=True)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        await bootstrap_admin_token_if_needed(factory)
    finally:
        await engine.dispose()


async def _cmd_dump_registry(args: argparse.Namespace) -> None:
    settings = Settings()
    engine = create_async_engine(settings.database_url, future=True)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as s:
            snap = await RegistryStore().load(s, Env(args.env))
        payload = snap.registry.model_dump_json(indent=2)
        if args.out == "-":
            sys.stdout.write(payload)
            sys.stdout.write("\n")
        else:
            Path(args.out).write_text(payload)
    finally:
        await engine.dispose()


async def _cmd_restore_registry(args: argparse.Namespace) -> None:
    settings = Settings()
    engine = create_async_engine(settings.database_url, future=True)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        payload = Path(args.inp).read_text()
        reg = OntologyRegistry.model_validate_json(payload)
        async with factory() as s:
            store = RegistryStore()
            snap = await store.load(s, Env(args.env))
            await store.save(
                s,
                Env(args.env),
                reg,
                expected_version=snap.version,
                token_label="cli",
            )
            await s.commit()
    finally:
        await engine.dispose()


async def _cmd_rotate_secret(args: argparse.Namespace) -> None:
    settings = Settings()
    old_store = ConnectionStore(secret_key=settings.secret_key)
    new_store = ConnectionStore(secret_key=args.new_key)
    engine = create_async_engine(settings.database_url, future=True)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as s:
            connections = await old_store.list_all(s)
            for conn in connections:
                plaintext = await old_store.decrypt_dsn(s, conn.id)
                reblob = new_store.encrypt(plaintext)
                await s.execute(
                    text("UPDATE connections SET dsn_encrypted = :e WHERE id = :i"),
                    {"e": reblob, "i": str(conn.id)},
                )
            await s.commit()
        sys.stdout.write("rotated; restart the server with the new ONTO_SECRET_KEY\n")
    finally:
        await engine.dispose()


async def _cmd_force_revoke_all(_args: argparse.Namespace) -> None:
    settings = Settings()
    engine = create_async_engine(settings.database_url, future=True)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as s:
            r = await s.execute(
                text("UPDATE api_tokens SET revoked_at = now() WHERE revoked_at IS NULL")
            )
            await s.commit()
            sys.stdout.write(f"revoked {r.rowcount} tokens\n")  # type: ignore[attr-defined]
    finally:
        await engine.dispose()


_DISPATCH: dict[str, Any] = {
    "db-migrate": _cmd_db_migrate,
    "bootstrap-admin": _cmd_bootstrap_admin,
    "dump-registry": _cmd_dump_registry,
    "restore-registry": _cmd_restore_registry,
    "rotate-secret": _cmd_rotate_secret,
    "force-revoke-all-tokens": _cmd_force_revoke_all,
}


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    asyncio.run(_DISPATCH[args.cmd](args))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
