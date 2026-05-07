# onto_platform/connections/store.py
import uuid
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional

from cryptography.fernet import Fernet
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession


class ConnectionKind(str, Enum):
    postgres = "postgres"
    mysql = "mysql"
    sqlite = "sqlite"


@dataclass
class Connection:
    id: uuid.UUID
    label: str
    kind: ConnectionKind
    last_probe_ok_at: Optional[datetime]


class ConnectionAlreadyExists(Exception):
    pass


class ConnectionNotFound(Exception):
    pass


class ConnectionStore:
    def __init__(self, secret_key: str) -> None:
        self._fernet = Fernet(secret_key.encode())

    def encrypt(self, dsn: str) -> bytes:
        return self._fernet.encrypt(dsn.encode())

    def decrypt(self, blob: bytes) -> str:
        return self._fernet.decrypt(blob).decode()

    async def insert(
        self,
        session: AsyncSession,
        *,
        label: str,
        kind: ConnectionKind,
        dsn: str,
    ) -> Connection:
        try:
            row = await session.execute(
                text(
                    "INSERT INTO connections (label, kind, dsn_encrypted) "
                    "VALUES (:l, :k, :e) RETURNING id"
                ),
                {"l": label, "k": kind.value, "e": self.encrypt(dsn)},
            )
        except IntegrityError as e:
            raise ConnectionAlreadyExists(label) from e
        cid = row.scalar_one()
        return Connection(id=cid, label=label, kind=kind, last_probe_ok_at=None)

    async def get_by_id(
        self,
        session: AsyncSession,
        connection_id: uuid.UUID,
    ) -> Connection:
        row = await session.execute(
            text("SELECT id, label, kind, last_probe_ok_at FROM connections WHERE id = :i"),
            {"i": str(connection_id)},
        )
        rec = row.one_or_none()
        if rec is None:
            raise ConnectionNotFound(str(connection_id))
        return Connection(
            id=rec.id,
            label=rec.label,
            kind=ConnectionKind(rec.kind),
            last_probe_ok_at=rec.last_probe_ok_at,
        )

    async def get_by_label(
        self,
        session: AsyncSession,
        label: str,
    ) -> Connection:
        row = await session.execute(
            text("SELECT id, label, kind, last_probe_ok_at FROM connections WHERE label = :l"),
            {"l": label},
        )
        rec = row.one_or_none()
        if rec is None:
            raise ConnectionNotFound(label)
        return Connection(
            id=rec.id,
            label=rec.label,
            kind=ConnectionKind(rec.kind),
            last_probe_ok_at=rec.last_probe_ok_at,
        )

    async def list_all(self, session: AsyncSession) -> list[Connection]:
        rows = await session.execute(
            text(
                "SELECT id, label, kind, last_probe_ok_at FROM connections ORDER BY label"
            )
        )
        return [
            Connection(
                id=r.id,
                label=r.label,
                kind=ConnectionKind(r.kind),
                last_probe_ok_at=r.last_probe_ok_at,
            )
            for r in rows
        ]

    async def decrypt_dsn(
        self,
        session: AsyncSession,
        connection_id: uuid.UUID,
    ) -> str:
        row = await session.execute(
            text("SELECT dsn_encrypted FROM connections WHERE id = :i"),
            {"i": str(connection_id)},
        )
        rec = row.one_or_none()
        if rec is None:
            raise ConnectionNotFound(str(connection_id))
        return self.decrypt(rec.dsn_encrypted)

    async def update_dsn(
        self,
        session: AsyncSession,
        connection_id: uuid.UUID,
        dsn: str,
    ) -> None:
        await session.execute(
            text("UPDATE connections SET dsn_encrypted = :e WHERE id = :i"),
            {"e": self.encrypt(dsn), "i": str(connection_id)},
        )

    async def mark_probe_ok(
        self,
        session: AsyncSession,
        connection_id: uuid.UUID,
    ) -> None:
        await session.execute(
            text("UPDATE connections SET last_probe_ok_at = now() WHERE id = :i"),
            {"i": str(connection_id)},
        )

    async def delete(
        self,
        session: AsyncSession,
        connection_id: uuid.UUID,
    ) -> None:
        await session.execute(
            text("DELETE FROM connections WHERE id = :i"),
            {"i": str(connection_id)},
        )
