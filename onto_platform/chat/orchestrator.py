from __future__ import annotations

import asyncio as _aio
import json
import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from onto_platform.proto_models import OntologyRegistry
from onto_platform.registry.store import (
    Env,
    RegistryStore,
    StaleVersionError,
)
from onto_platform.ingestion.store import ImportMode
from onto_platform.ingestion.workers import run_one_job as _run_one_job
from onto_platform.chat.sse import EventBus

if TYPE_CHECKING:
    from onto_platform.config import Settings
    from onto_platform.ingestion.llm_client import LLMClient


@dataclass
class SessionInfo:
    id: uuid.UUID
    status: str
    pre_session_version: int
    messages: list[dict[str, Any]] = field(default_factory=list)


class SessionNotFoundError(Exception):
    pass


class TurnInFlightError(Exception):
    pass


class StaleStagingError(Exception):
    """Raised when a Cancel rollback would clobber concurrent staging changes."""


class TooManySessionsError(Exception):
    pass


class ChatSessionOrchestrator:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        registry_store: RegistryStore,
        *,
        event_bus: EventBus | None = None,
        max_sessions_per_token: int | None = None,
    ) -> None:
        self._sf = session_factory
        self._rstore = registry_store
        # In-memory registry of in-flight turns: session_id -> turn_id
        self._running: dict[uuid.UUID, uuid.UUID] = {}
        self._bus: EventBus = event_bus or EventBus()
        self._max_sessions_per_token = max_sessions_per_token

    @property
    def event_bus(self) -> EventBus:
        return self._bus

    async def create_session(self, *, token_id: uuid.UUID) -> uuid.UUID:
        async with self._sf() as s:
            if self._max_sessions_per_token is not None:
                count_row = await s.execute(
                    text(
                        "SELECT count(*) FROM chat_sessions "
                        "WHERE token_id = :t AND status = 'active'"
                    ),
                    {"t": str(token_id)},
                )
                if count_row.scalar_one() >= self._max_sessions_per_token:
                    raise TooManySessionsError(str(token_id))
            snap = await self._rstore.load(s, Env.staging)
            row = await s.execute(
                text(
                    "INSERT INTO chat_sessions "
                    "(token_id, status, pre_session_registry, pre_session_version) "
                    "VALUES (:t, 'active', CAST(:p AS jsonb), :v) "
                    "RETURNING id"
                ),
                {
                    "t": str(token_id),
                    "p": snap.registry.model_dump_json(),
                    "v": snap.version,
                },
            )
            sid = row.scalar_one()
            await s.commit()
            return uuid.UUID(str(sid))

    async def get_session(
        self,
        session_id: uuid.UUID,
        *,
        requester_token_id: uuid.UUID | None = None,
    ) -> SessionInfo:
        async with self._sf() as s:
            row = await s.execute(
                text(
                    "SELECT status, pre_session_version, token_id "
                    "FROM chat_sessions WHERE id = :i"
                ),
                {"i": str(session_id)},
            )
            rec = row.one_or_none()
            if rec is None:
                raise SessionNotFoundError(str(session_id))
            if requester_token_id is not None and uuid.UUID(str(rec.token_id)) != requester_token_id:
                raise SessionNotFoundError(str(session_id))
            msgs = await s.execute(
                text(
                    "SELECT turn_index, role, content, created_at "
                    "FROM chat_messages WHERE session_id = :i ORDER BY id ASC"
                ),
                {"i": str(session_id)},
            )
            messages = [
                {
                    "turn_index": m.turn_index,
                    "role": m.role,
                    "content": m.content,
                    "created_at": m.created_at.isoformat() if m.created_at else None,
                }
                for m in msgs
            ]
            return SessionInfo(
                id=session_id,
                status=rec.status,
                pre_session_version=rec.pre_session_version,
                messages=messages,
            )

    async def save_session(
        self,
        session_id: uuid.UUID,
        *,
        requester_token_id: uuid.UUID | None = None,
    ) -> None:
        if session_id in self._running:
            raise TurnInFlightError(str(session_id))
        async with self._sf() as s:
            r = await s.execute(
                text(
                    "UPDATE chat_sessions SET status='saving' "
                    "WHERE id = :i RETURNING id, token_id"
                ),
                {"i": str(session_id)},
            )
            rec = r.one_or_none()
            if rec is None:
                raise SessionNotFoundError(str(session_id))
            if requester_token_id is not None and uuid.UUID(str(rec.token_id)) != requester_token_id:
                raise SessionNotFoundError(str(session_id))
            await s.execute(
                text("DELETE FROM chat_sessions WHERE id = :i"),
                {"i": str(session_id)},
            )
            await s.commit()

    async def cancel_session(
        self,
        session_id: uuid.UUID,
        *,
        requester_token_id: uuid.UUID | None = None,
    ) -> None:
        if session_id in self._running:
            raise TurnInFlightError(str(session_id))
        async with self._sf() as s:
            row = await s.execute(
                text(
                    "UPDATE chat_sessions SET status='cancelling' WHERE id = :i "
                    "RETURNING pre_session_registry, pre_session_version, token_id"
                ),
                {"i": str(session_id)},
            )
            rec = row.one_or_none()
            if rec is None:
                raise SessionNotFoundError(str(session_id))
            if requester_token_id is not None and uuid.UUID(str(rec.token_id)) != requester_token_id:
                raise SessionNotFoundError(str(session_id))
            pre_registry = OntologyRegistry.model_validate(rec.pre_session_registry)
            current = await self._rstore.load(s, Env.staging)
            try:
                await self._rstore.save(
                    s,
                    Env.staging,
                    pre_registry,
                    expected_version=current.version,
                    token_label="chat-cancel",
                    commit_message=f"cancel chat session {session_id}",
                )
            except StaleVersionError as e:
                # Leave row in 'cancelling' for operator inspection
                await s.commit()
                raise StaleStagingError(str(e)) from e
            await s.execute(
                text("DELETE FROM chat_sessions WHERE id = :i"),
                {"i": str(session_id)},
            )
            await s.commit()

    async def start_turn(
        self,
        session_id: uuid.UUID,
        *,
        user_message: str,
        upload_ids: list[str],
        token_id: uuid.UUID,
        requester_token_id: uuid.UUID | None = None,
    ) -> uuid.UUID:
        if session_id in self._running:
            raise TurnInFlightError(str(session_id))
        async with self._sf() as s:
            row = await s.execute(
                text("SELECT status, token_id FROM chat_sessions WHERE id = :i"),
                {"i": str(session_id)},
            )
            rec = row.one_or_none()
            if rec is None:
                raise SessionNotFoundError(str(session_id))
            if requester_token_id is not None and uuid.UUID(str(rec.token_id)) != requester_token_id:
                raise SessionNotFoundError(str(session_id))
            if rec.status != "active":
                raise TurnInFlightError(f"session not active: {rec.status}")

            r2 = await s.execute(
                text(
                    "SELECT COALESCE(MAX(turn_index), -1) + 1 AS next "
                    "FROM chat_messages WHERE session_id = :i"
                ),
                {"i": str(session_id)},
            )
            turn_index = r2.scalar_one()

            await s.execute(
                text(
                    "INSERT INTO chat_messages (session_id, turn_index, role, content) "
                    "VALUES (:s, :t, 'user', CAST(:c AS jsonb))"
                ),
                {
                    "s": str(session_id),
                    "t": turn_index,
                    "c": json.dumps({"text": user_message, "upload_ids": upload_ids}),
                },
            )

            await s.execute(
                text("UPDATE chat_sessions SET last_turn_at = now() WHERE id = :i"),
                {"i": str(session_id)},
            )

            r3 = await s.execute(
                text(
                    "INSERT INTO ingestion_jobs (mode, instructions, chat_session_id, "
                    "created_by_token_id) VALUES (:m, :i, :cs, :ct) RETURNING id"
                ),
                {
                    "m": ImportMode.merge.value,
                    "i": user_message,
                    "cs": str(session_id),
                    "ct": str(token_id),
                },
            )
            turn_id = r3.scalar_one()

            # Link uploads to the job (mirrors IngestionStore.create_job behavior)
            for up in upload_ids:
                await s.execute(
                    text(
                        "UPDATE ingestion_uploads SET job_id = :j "
                        "WHERE id = :u AND job_id IS NULL"
                    ),
                    {"j": str(turn_id), "u": up},
                )

            await s.commit()
            self._running[session_id] = uuid.UUID(str(turn_id))
            return uuid.UUID(str(turn_id))

    async def run_turn_worker(
        self,
        session_id: uuid.UUID,
        turn_id: uuid.UUID,
        *,
        llm: "LLMClient | None",
        settings: "Settings | None",
    ) -> None:
        try:
            await self._bus.publish(str(turn_id), "turn_start", {"turn_id": str(turn_id)})
            # Hand off to the existing ingestion-job worker
            if settings is not None:
                try:
                    await _aio.wait_for(
                        _run_one_job(self._sf, turn_id, llm=llm, settings=settings),
                        timeout=float(settings.chat_turn_max_wall_clock_s),
                    )
                except _aio.TimeoutError:
                    async with self._sf() as s:
                        await s.execute(
                            text(
                                "UPDATE ingestion_jobs SET status='failed', "
                                "phase_message='wall-clock timeout', "
                                "error_code='WALL_CLOCK_TIMEOUT', finished_at=now() "
                                "WHERE id = :i AND finished_at IS NULL"
                            ),
                            {"i": str(turn_id)},
                        )
                        await s.commit()
            else:
                await _run_one_job(self._sf, turn_id, llm=llm, settings=settings)
            # After the job completes, fetch its outcome
            async with self._sf() as s:
                row = await s.execute(
                    text(
                        "SELECT status, decisions_report, error_code, phase_message "
                        "FROM ingestion_jobs WHERE id = :i"
                    ),
                    {"i": str(turn_id)},
                )
                rec = row.one()
                if rec.status == "imported":
                    text_summary = "已完成本轮变更。"
                elif rec.status == "cancelled":
                    text_summary = "本轮已取消。"
                else:
                    text_summary = (
                        f"本轮失败：{rec.phase_message or rec.error_code or '未知错误'}"
                    )
                r2 = await s.execute(
                    text(
                        "SELECT COALESCE(MAX(turn_index), 0) FROM chat_messages "
                        "WHERE session_id = :s"
                    ),
                    {"s": str(session_id)},
                )
                turn_index = r2.scalar_one()
                await s.execute(
                    text(
                        "INSERT INTO chat_messages (session_id, turn_index, role, content) "
                        "VALUES (:s, :t, 'assistant', CAST(:c AS jsonb))"
                    ),
                    {
                        "s": str(session_id),
                        "t": turn_index,
                        "c": json.dumps({"text": text_summary}),
                    },
                )
                await s.commit()
            if rec.status == "imported":
                tool_calls = len(
                    ((rec.decisions_report or {}).get("decisions") or [])
                )
                await self._bus.publish(
                    str(turn_id),
                    "turn_complete",
                    {"turn_id": str(turn_id), "tool_calls_made": tool_calls},
                )
            else:
                await self._bus.publish(
                    str(turn_id),
                    "turn_error",
                    {
                        "kind": rec.error_code or "unknown",
                        "message": rec.phase_message or "",
                    },
                )
        finally:
            self._running.pop(session_id, None)
            await self._bus.close(str(turn_id))
