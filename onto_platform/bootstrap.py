# onto_platform/bootstrap.py
import sys
from typing import IO, Optional
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from onto_platform.auth import Scope, generate_token
from onto_platform.token_store import insert_token


async def bootstrap_admin_token_if_needed(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    stdout: IO[str] = sys.stdout,
) -> Optional[str]:
    """If api_tokens is empty, mint an admin token labelled 'bootstrap',
    print it to stdout once, return the plaintext. Otherwise return None.
    """
    async with session_factory() as s:
        row = await s.execute(text("SELECT COUNT(*) FROM api_tokens"))
        if row.scalar_one() > 0:
            return None
    plaintext = generate_token()
    async with session_factory() as s:
        await insert_token(s, plaintext, Scope.admin, "bootstrap", None)
        await s.commit()
    print(f"ADMIN BOOTSTRAP TOKEN: {plaintext}", file=stdout, flush=True)
    return plaintext
