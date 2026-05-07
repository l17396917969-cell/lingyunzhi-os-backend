# onto_platform/connections/pool.py
import uuid
from contextlib import asynccontextmanager
from typing import AsyncIterator, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, AsyncSession, create_async_engine

from onto_platform.connections.store import ConnectionKind, ConnectionStore


class ConnectionPool:
    def __init__(self, *, store: ConnectionStore) -> None:
        self._store = store
        self._engines: dict[uuid.UUID, tuple[AsyncEngine, ConnectionKind]] = {}

    async def _get_or_create(
        self,
        session: AsyncSession,
        connection_id: uuid.UUID,
    ) -> tuple[AsyncEngine, ConnectionKind]:
        if connection_id in self._engines:
            return self._engines[connection_id]
        meta = await self._store.get_by_id(session, connection_id)
        dsn = await self._store.decrypt_dsn(session, connection_id)
        engine = create_async_engine(dsn, future=True)
        if meta.kind is not ConnectionKind.sqlite:
            engine = engine.execution_options(readonly=True)
        self._engines[connection_id] = (engine, meta.kind)
        return self._engines[connection_id]

    @asynccontextmanager
    async def session(
        self,
        session: AsyncSession,
        connection_id: uuid.UUID,
        *,
        timeout_ms: Optional[int] = 30_000,
    ) -> AsyncIterator[AsyncConnection]:
        engine, kind = await self._get_or_create(session, connection_id)
        async with engine.connect() as conn:
            await self._enforce_read_only(conn, kind, timeout_ms)
            yield conn

    async def _enforce_read_only(
        self,
        conn: AsyncConnection,
        kind: ConnectionKind,
        timeout_ms: Optional[int],
    ) -> None:
        if kind is ConnectionKind.postgres:
            await conn.execute(text("SET TRANSACTION READ ONLY"))
            if timeout_ms:
                await conn.execute(
                    text("SET LOCAL statement_timeout = :t"),
                    {"t": timeout_ms},
                )
        elif kind is ConnectionKind.mysql:
            await conn.execute(text("SET SESSION TRANSACTION READ ONLY"))
            if timeout_ms:
                await conn.execute(
                    text(f"SET SESSION MAX_EXECUTION_TIME = {int(timeout_ms)}"),
                )
        elif kind is ConnectionKind.sqlite:
            pass

    def invalidate(self, connection_id: uuid.UUID) -> None:
        self._engines.pop(connection_id, None)

    async def dispose_all(self) -> None:
        for engine, _ in list(self._engines.values()):
            await engine.dispose()
        self._engines.clear()
