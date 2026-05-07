"""
Data instance query routes – read-only queries against mapped data sources.
"""

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from onto_platform.auth import Scope
from onto_platform.ui_auth import require_scope_via_cookie_or_bearer
from onto_platform.connections.query_builder import InstanceQueryBuilder, QueryBuildError


def make_data_router(
    session_provider: object,
    query_builder: InstanceQueryBuilder,
) -> APIRouter:
    router = APIRouter(prefix="/api/data")
    _read_dep = require_scope_via_cookie_or_bearer(Scope.read, session_provider)

    @router.get("/{object_type_rid}/instances")
    async def list_instances(
        object_type_rid: str,
        page: int = Query(1, ge=1),
        page_size: int = Query(20, ge=1, le=100),
        search: Optional[str] = Query(None),
        sort_field: Optional[str] = Query(None),
        sort_order: str = Query("asc", pattern="^(asc|desc)$"),
        session: AsyncSession = Depends(session_provider),  # type: ignore[arg-type]
    ) -> dict[str, Any]:
        try:
            result = await query_builder.query(
                session,
                object_type_rid,
                page=page,
                page_size=page_size,
                search=search,
                sort_field=sort_field,
                sort_order=sort_order,
            )
        except QueryBuildError as e:
            raise HTTPException(status_code=400, detail={"code": "QUERY_BUILD_ERROR", "message": str(e)})
        except Exception as e:
            raise HTTPException(status_code=500, detail={"code": "QUERY_EXECUTION_ERROR", "message": str(e)})

        return {
            "object_type_rid": result.object_type_rid,
            "object_type_name": result.object_type_name,
            "columns": [
                {
                    "api_name": c.api_name,
                    "display_name": c.display_name,
                    "physical_column": c.physical_column,
                }
                for c in result.columns
            ],
            "data": result.data,
            "total": result.total,
            "page": result.page,
            "page_size": result.page_size,
            "has_more": result.has_more,
        }

    return router
