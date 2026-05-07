# onto_platform/chat/http.py
from __future__ import annotations

import asyncio
import logging
import pathlib
import uuid
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from onto_platform.auth import RequestPrincipal, Scope
from onto_platform.chat.orchestrator import (
    ChatSessionOrchestrator,
    SessionNotFoundError,
    StaleStagingError,
    TooManySessionsError,
    TurnInFlightError,
)
from onto_platform.chat.sse import sse_format
from onto_platform.config import Settings
from onto_platform.ingestion.http import process_upload as _process_upload
from onto_platform.registry.store import RegistryStore
from onto_platform.ui_auth import require_scope_via_cookie_or_bearer

if TYPE_CHECKING:
    from onto_platform.ingestion.llm_client import LLMClient

_log = logging.getLogger("onto_platform.chat.http")


def make_chat_router(
    session_provider: Any,
    *,
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
    orchestrator: ChatSessionOrchestrator | None = None,
    llm: "LLMClient | None" = None,
) -> APIRouter:
    router = APIRouter(prefix="/chat")
    rstore = RegistryStore()
    orch = orchestrator or ChatSessionOrchestrator(
        session_factory,
        rstore,
        max_sessions_per_token=settings.chat_max_concurrent_sessions_per_token,
    )
    editor_dep = require_scope_via_cookie_or_bearer(Scope.editor, session_provider)

    @router.post("/sessions", status_code=201)
    async def create_session(
        principal: RequestPrincipal = Depends(editor_dep),
    ) -> dict[str, str]:
        try:
            sid = await orch.create_session(token_id=principal.token_id)
        except TooManySessionsError:
            raise HTTPException(429, detail={"code": "TOO_MANY_SESSIONS"})
        return {"session_id": str(sid)}

    @router.get("/sessions/{session_id}")
    async def get_session(
        session_id: str,
        principal: RequestPrincipal = Depends(editor_dep),
    ) -> dict[str, Any]:
        try:
            sid = uuid.UUID(session_id)
        except ValueError:
            raise HTTPException(404, detail={"code": "NOT_FOUND"})
        try:
            info = await orch.get_session(sid, requester_token_id=principal.token_id)
        except SessionNotFoundError:
            raise HTTPException(404, detail={"code": "NOT_FOUND"})
        return {
            "session_id": str(info.id),
            "status": info.status,
            "messages": info.messages,
        }

    @router.post("/sessions/{session_id}/save", status_code=204)
    async def save_session(
        session_id: str,
        principal: RequestPrincipal = Depends(editor_dep),
    ) -> None:
        try:
            sid = uuid.UUID(session_id)
        except ValueError:
            raise HTTPException(404, detail={"code": "NOT_FOUND"})
        try:
            await orch.save_session(sid, requester_token_id=principal.token_id)
        except SessionNotFoundError:
            raise HTTPException(404, detail={"code": "NOT_FOUND"})
        except TurnInFlightError:
            raise HTTPException(409, detail={"code": "TURN_IN_FLIGHT"})
        return None

    @router.post("/sessions/{session_id}/cancel", status_code=204)
    async def cancel_session(
        session_id: str,
        principal: RequestPrincipal = Depends(editor_dep),
    ) -> None:
        try:
            sid = uuid.UUID(session_id)
        except ValueError:
            raise HTTPException(404, detail={"code": "NOT_FOUND"})
        try:
            await orch.cancel_session(sid, requester_token_id=principal.token_id)
        except SessionNotFoundError:
            raise HTTPException(404, detail={"code": "NOT_FOUND"})
        except TurnInFlightError:
            raise HTTPException(409, detail={"code": "TURN_IN_FLIGHT"})
        except StaleStagingError as e:
            raise HTTPException(
                409,
                detail={"code": "STALE_STAGING", "message": str(e)},
            )
        return None

    @router.post("/sessions/{session_id}/uploads")
    async def upload_for_session(
        session_id: str,
        file: UploadFile = File(...),
        principal: RequestPrincipal = Depends(editor_dep),
        session: AsyncSession = Depends(session_provider),
    ) -> dict[str, Any]:
        try:
            sid = uuid.UUID(session_id)
        except ValueError:
            raise HTTPException(404, detail={"code": "NOT_FOUND"})
        try:
            await orch.get_session(sid, requester_token_id=principal.token_id)
        except SessionNotFoundError:
            raise HTTPException(404, detail={"code": "NOT_FOUND"})
        data_dir = pathlib.Path(settings.ingestion_data_dir)
        return await _process_upload(
            file, principal=principal, session=session, settings=settings, data_dir=data_dir
        )

    @router.post("/sessions/{session_id}/turns", status_code=202)
    async def submit_turn(
        session_id: str,
        body: dict[str, Any],
        principal: RequestPrincipal = Depends(editor_dep),
    ) -> dict[str, str]:
        try:
            sid = uuid.UUID(session_id)
        except ValueError:
            raise HTTPException(404, detail={"code": "NOT_FOUND"})
        message = body.get("message")
        upload_ids = body.get("upload_ids", [])
        if not isinstance(message, str) or not message.strip():
            raise HTTPException(422, detail={"code": "INVALID_BODY"})
        if not isinstance(upload_ids, list):
            raise HTTPException(422, detail={"code": "INVALID_BODY"})
        try:
            turn_id = await orch.start_turn(
                sid,
                user_message=message,
                upload_ids=[str(u) for u in upload_ids],
                token_id=principal.token_id,
                requester_token_id=principal.token_id,
            )
        except SessionNotFoundError:
            raise HTTPException(404, detail={"code": "NOT_FOUND"})
        except TurnInFlightError:
            raise HTTPException(409, detail={"code": "TURN_IN_FLIGHT"})
        task = asyncio.create_task(orch.run_turn_worker(sid, turn_id, llm=llm, settings=settings))

        def _log_exc(t: asyncio.Task) -> None:
            if t.cancelled():
                return
            exc = t.exception()
            if exc is not None:
                _log.exception(
                    "chat turn worker failed: session=%s turn=%s", sid, turn_id, exc_info=exc
                )

        task.add_done_callback(_log_exc)
        return {"turn_id": str(turn_id)}

    @router.get("/sessions/{session_id}/stream")
    async def stream_turn(
        session_id: str,
        turn_id: str,
        principal: RequestPrincipal = Depends(editor_dep),
    ) -> StreamingResponse:
        try:
            sid = uuid.UUID(session_id)
            tid = uuid.UUID(turn_id)
        except ValueError:
            raise HTTPException(404, detail={"code": "NOT_FOUND"})
        try:
            await orch.get_session(sid, requester_token_id=principal.token_id)
        except SessionNotFoundError:
            raise HTTPException(404, detail={"code": "NOT_FOUND"})

        heartbeat_s = settings.chat_sse_heartbeat_s

        async def gen():
            sub_iter = orch.event_bus.subscribe(str(tid)).__aiter__()
            while True:
                try:
                    item = await asyncio.wait_for(sub_iter.__anext__(), timeout=heartbeat_s)
                except asyncio.TimeoutError:
                    yield "event: heartbeat\ndata: {}\n\n"
                    continue
                except StopAsyncIteration:
                    return
                event_type, payload = item
                yield sse_format(event_type, payload)
                if event_type in ("turn_complete", "turn_error"):
                    return

        return StreamingResponse(gen(), media_type="text/event-stream")

    return router
