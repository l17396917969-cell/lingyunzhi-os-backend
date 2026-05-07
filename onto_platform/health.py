# onto_platform/health.py
from typing import Any, AsyncGenerator, Callable

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


def make_health_router(
    session_provider: Callable[[], AsyncGenerator[AsyncSession, None]],
) -> APIRouter:
    router = APIRouter()

    @router.get("/healthz")
    async def healthz() -> dict[str, Any]:
        return {"status": "ok"}

    @router.get("/readyz")
    async def readyz(
        session: AsyncSession = Depends(session_provider),
    ) -> JSONResponse:
        # Verify all 3 registries rows exist
        rows = (
            await session.execute(
                text(
                    "SELECT env FROM registries WHERE env IN "
                    "('staging','production','previous_production')"
                )
            )
        ).all()
        envs = {r.env for r in rows}
        expected = {"staging", "production", "previous_production"}
        if envs != expected:
            return JSONResponse(
                content={
                    "status": "not-ready",
                    "missing": list(expected - envs),
                },
                status_code=503,
            )
        return JSONResponse(content={"status": "ok"}, status_code=200)

    return router
