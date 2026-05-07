# onto_platform/connections/probe.py
import asyncio
import re
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from onto_platform.connections.store import (
    Connection,
    ConnectionKind,
    ConnectionStore,
)


class ConnectionProbeError(Exception):
    def __init__(self, driver_error: str):
        super().__init__(f"Connection probe failed: {driver_error}")
        self.driver_error = driver_error


_DSN_PW_RE = re.compile(r"(://[^:]+:)[^@]+(@)")


def _redact(msg: str) -> str:
    return _DSN_PW_RE.sub(r"\1***\2", msg)


async def probe(
    dsn: str,
    kind: ConnectionKind,
    *,
    timeout_s: int = 5,
) -> tuple[bool, Optional[str]]:
    """Open a temp engine, run SELECT 1, return (ok, redacted_err_str_or_none)."""
    engine = create_async_engine(dsn, future=True)
    try:
        async with asyncio.timeout(timeout_s):
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
        return True, None
    except Exception as e:
        return False, _redact(str(e))
    finally:
        await engine.dispose()


async def register_connection(
    session: AsyncSession,
    *,
    store: ConnectionStore,
    label: str,
    kind: ConnectionKind,
    dsn: str,
) -> Connection:
    ok, err = await probe(dsn, kind)
    if not ok:
        raise ConnectionProbeError(err or "unknown error")
    c = await store.insert(session, label=label, kind=kind, dsn=dsn)
    await store.mark_probe_ok(session, c.id)
    refreshed = await store.get_by_id(session, c.id)
    return refreshed
