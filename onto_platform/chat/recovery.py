from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from onto_platform.chat.orchestrator import (
    ChatSessionOrchestrator,
    StaleStagingError,
)

log = logging.getLogger(__name__)


@dataclass
class OrphanSweepResult:
    recovered: int = 0
    failed: int = 0


async def sweep_orphan_sessions(
    orchestrator: ChatSessionOrchestrator,
    session_factory: async_sessionmaker[AsyncSession],
    *,
    orphan_after_s: int,
) -> OrphanSweepResult:
    """Roll back chat sessions that have been idle longer than orphan_after_s.

    A session is considered orphaned when status='active' AND
      (last_turn_at IS NULL AND created_at < now() - orphan_after_s)
      OR (last_turn_at < now() - orphan_after_s).
    """
    async with session_factory() as s:
        rows = await s.execute(
            text(
                "SELECT id, created_at, last_turn_at FROM chat_sessions "
                "WHERE status = 'active' AND ("
                "  (last_turn_at IS NULL AND created_at < now() - make_interval(secs => :s)) OR "
                "  (last_turn_at < now() - make_interval(secs => :s))"
                ")"
            ),
            {"s": orphan_after_s},
        )
        orphan_ids = [uuid.UUID(str(r.id)) for r in rows]
    result = OrphanSweepResult()
    for sid in orphan_ids:
        try:
            await orchestrator.cancel_session(sid)
            log.warning("orphan chat session %s rolled back", sid)
            result.recovered += 1
        except StaleStagingError as e:
            log.error(
                "orphan chat session %s rollback failed (StaleStagingError): %s",
                sid,
                e,
            )
            result.failed += 1
        except Exception as e:
            log.exception("orphan chat session %s rollback failed: %s", sid, e)
            result.failed += 1
    return result
