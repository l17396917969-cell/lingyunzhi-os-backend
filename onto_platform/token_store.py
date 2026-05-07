# onto_platform/token_store.py
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from onto_platform.auth import (
    Scope, hash_token, verify_token, token_prefix,
)


@dataclass
class TokenLookupResult:
    token_id: uuid.UUID
    scope: Scope
    label: str


@dataclass
class TokenListItem:
    token_id: uuid.UUID
    scope: Scope
    label: str
    created_at: datetime
    revoked_at: Optional[datetime]


async def insert_token(
    session: AsyncSession,
    plaintext: str,
    scope: Scope,
    label: str,
    created_by_token_id: Optional[uuid.UUID],
) -> uuid.UUID:
    row = await session.execute(
        text(
            "INSERT INTO api_tokens (token_hash, token_prefix, scope, label, created_by_token_id) "
            "VALUES (:h, :p, :s, :l, :cb) RETURNING id"
        ),
        {
            "h": hash_token(plaintext),
            "p": token_prefix(plaintext),
            "s": scope.name,
            "l": label,
            "cb": str(created_by_token_id) if created_by_token_id else None,
        },
    )
    result: uuid.UUID = row.scalar_one()
    return result


async def lookup_token(session: AsyncSession, plaintext: str) -> Optional[TokenLookupResult]:
    rows = await session.execute(
        text(
            "SELECT id, token_hash, scope, label FROM api_tokens "
            "WHERE token_prefix = :p AND revoked_at IS NULL"
        ),
        {"p": token_prefix(plaintext)},
    )
    for row in rows:
        if verify_token(plaintext, row.token_hash):
            return TokenLookupResult(
                token_id=row.id, scope=Scope[row.scope], label=row.label,
            )
    return None


async def revoke_token(session: AsyncSession, token_id: uuid.UUID) -> bool:
    res = await session.execute(
        text("UPDATE api_tokens SET revoked_at = now() WHERE id = :i AND revoked_at IS NULL"),
        {"i": str(token_id)},
    )
    affected: bool = res.rowcount > 0  # type: ignore[attr-defined]
    return affected


async def list_tokens(session: AsyncSession) -> list[TokenListItem]:
    rows = await session.execute(
        text(
            "SELECT id, scope, label, created_at, revoked_at "
            "FROM api_tokens ORDER BY created_at DESC"
        )
    )
    return [
        TokenListItem(
            token_id=r.id, scope=Scope[r.scope], label=r.label,
            created_at=r.created_at, revoked_at=r.revoked_at,
        )
        for r in rows
    ]
