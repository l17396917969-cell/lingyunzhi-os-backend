# onto_platform/ui_auth.py
import uuid
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass
from typing import Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from onto_platform.auth import (
    Scope, RequestPrincipal, _extract_bearer,
)
from onto_platform.config import Settings
from onto_platform.token_store import lookup_token


_COOKIE_NAME = "onto_session"


@dataclass
class _UISession:
    id: uuid.UUID
    token_id: uuid.UUID
    label: str
    scope: Scope


async def _resolve_session(session: AsyncSession, session_id: uuid.UUID) -> Optional[_UISession]:
    row = await session.execute(text(
        "SELECT s.id, s.token_id, s.scope, s.expires_at, s.revoked_at, t.label, t.revoked_at AS token_revoked "
        "FROM ui_sessions s JOIN api_tokens t ON t.id = s.token_id "
        "WHERE s.id = :i"
    ), {"i": str(session_id)})
    rec = row.one_or_none()
    if not rec:
        return None
    if rec.revoked_at is not None or rec.token_revoked is not None:
        return None
    if rec.expires_at < datetime.now(timezone.utc):
        return None
    return _UISession(id=rec.id, token_id=rec.token_id, label=rec.label, scope=Scope[rec.scope])


def make_ui_auth_router(session_provider: object, settings: Settings) -> APIRouter:
    router = APIRouter()

    @router.post("/admin/login")
    async def login(
        request: Request,
        response: Response,
        session: AsyncSession = Depends(session_provider),  # type: ignore[arg-type]
    ) -> dict[str, Any]:
        body = await request.json()
        token = body.get("token", "")
        result = await lookup_token(session, token)
        if result is None:
            raise HTTPException(401, detail={"code": "UNAUTHORIZED", "message": "Invalid or revoked token"})
        expires = datetime.now(timezone.utc) + timedelta(seconds=settings.ui_session_ttl_seconds)
        sid = uuid.uuid4()
        await session.execute(text(
            "INSERT INTO ui_sessions (id, token_id, scope, expires_at) VALUES (:i, :t, :s, :e)"
        ), {"i": str(sid), "t": str(result.token_id), "s": result.scope.name, "e": expires})
        await session.commit()
        response.set_cookie(
            _COOKIE_NAME, str(sid),
            httponly=True, secure=settings.ui_cookie_secure, samesite="strict",
            max_age=settings.ui_session_ttl_seconds,
        )
        return {"label": result.label, "scope": result.scope.name}

    @router.post("/admin/logout")
    async def logout(
        request: Request,
        response: Response,
        session: AsyncSession = Depends(session_provider),  # type: ignore[arg-type]
    ) -> dict[str, Any]:
        sid_raw = request.cookies.get(_COOKIE_NAME)
        if sid_raw:
            try:
                sid = uuid.UUID(sid_raw)
                await session.execute(text(
                    "UPDATE ui_sessions SET revoked_at = now() WHERE id = :i"
                ), {"i": str(sid)})
                await session.commit()
            except ValueError:
                pass
        response.delete_cookie(_COOKIE_NAME)
        return {"ok": True}

    return router


def require_scope_via_cookie_or_bearer(min_scope: Scope, session_provider: object) -> object:
    """Like require_scope, but also accepts an `onto_session` cookie."""
    async def dep(
        request: Request,
        session: AsyncSession = Depends(session_provider),  # type: ignore[arg-type]
    ) -> RequestPrincipal:
        bearer = _extract_bearer(request)
        if bearer:
            result = await lookup_token(session, bearer)
            if result is None:
                raise HTTPException(401, detail={"code": "UNAUTHORIZED"})
            if result.scope < min_scope:
                raise HTTPException(403, detail={"code": "FORBIDDEN", "message": f"Requires scope >= {min_scope.name}"})
            return RequestPrincipal(token_id=result.token_id, label=result.label, scope=result.scope)
        sid_raw = request.cookies.get(_COOKIE_NAME)
        if sid_raw:
            try:
                sid = uuid.UUID(sid_raw)
            except ValueError:
                raise HTTPException(401, detail={"code": "UNAUTHORIZED"})
            ui = await _resolve_session(session, sid)
            if ui is None:
                raise HTTPException(401, detail={"code": "UNAUTHORIZED"})
            if ui.scope < min_scope:
                raise HTTPException(403, detail={"code": "FORBIDDEN", "message": f"Requires scope >= {min_scope.name}"})
            return RequestPrincipal(token_id=ui.token_id, label=ui.label, scope=ui.scope)
        raise HTTPException(401, detail={"code": "UNAUTHORIZED"})
    return dep
