# onto_platform/api_routes.py
from enum import Enum
from typing import Any
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from onto_platform.auth import Scope, RequestPrincipal
from onto_platform.ui_auth import require_scope_via_cookie_or_bearer
from onto_platform.registry.store import RegistryStore, Env
from onto_platform.registry.diff import compute_diff


def make_api_router(session_provider: object) -> APIRouter:
    router = APIRouter(prefix="/api")
    rstore = RegistryStore()

    _read_dep = require_scope_via_cookie_or_bearer(Scope.read, session_provider)
    _admin_dep = require_scope_via_cookie_or_bearer(Scope.admin, session_provider)

    @router.get("/whoami")
    async def api_whoami(
        principal: RequestPrincipal = Depends(_read_dep),  # type: ignore[arg-type]
    ) -> dict[str, str]:
        return {
            "token_label": principal.label,
            "scope": principal.scope.name,
            "server_version": "0.1.0",
        }

    @router.get("/registries/{env}/summary")
    async def summary(
        env: str,
        principal: RequestPrincipal = Depends(_read_dep),  # type: ignore[arg-type]
        session: AsyncSession = Depends(session_provider),  # type: ignore[arg-type]
    ) -> dict[str, Any]:
        snap = await rstore.load(session, Env(env))
        return {
            "env": env,
            "version": snap.version,
            "entity_counts": {
                "shared_property_types": len(snap.registry.shared_property_types),
                "interface_types": len(snap.registry.interface_types),
                "object_types": len(snap.registry.object_types),
                "link_types": len(snap.registry.link_types),
                "action_types": len(snap.registry.action_types),
            },
        }

    @router.get("/registries/diff")
    async def diff_endpoint(
        principal: RequestPrincipal = Depends(_read_dep),  # type: ignore[arg-type]
        session: AsyncSession = Depends(session_provider),  # type: ignore[arg-type]
    ) -> dict[str, Any]:
        s = await rstore.load(session, Env.staging)
        p = await rstore.load(session, Env.production)
        return compute_diff(s.registry, p.registry)

    @router.get("/registries/{env}/full")
    async def full(
        env: str,
        principal: RequestPrincipal = Depends(_read_dep),  # type: ignore[arg-type]
        session: AsyncSession = Depends(session_provider),  # type: ignore[arg-type]
    ) -> dict[str, Any]:
        snap = await rstore.load(session, Env(env))
        return snap.registry.model_dump()

    @router.get("/registries/{env}/entities/{kind}")
    async def list_entities(
        env: str,
        kind: str,
        principal: RequestPrincipal = Depends(_read_dep),  # type: ignore[arg-type]
        session: AsyncSession = Depends(session_provider),  # type: ignore[arg-type]
    ) -> list[dict[str, Any]]:
        kind_field = kind + "s"
        snap = await rstore.load(session, Env(env))
        d = getattr(snap.registry, kind_field, None)
        if d is None:
            raise HTTPException(404, detail={"code": "NOT_FOUND"})
        return [v.model_dump() for v in d.values()]

    @router.get("/registries/{env}/entities/{kind}/{rid:path}")
    async def get_entity(
        env: str,
        kind: str,
        rid: str,
        principal: RequestPrincipal = Depends(_read_dep),  # type: ignore[arg-type]
        session: AsyncSession = Depends(session_provider),  # type: ignore[arg-type]
    ) -> dict[str, Any]:
        snap = await rstore.load(session, Env(env))
        d = getattr(snap.registry, kind + "s", None)
        if d is None or rid not in d:
            raise HTTPException(404, detail={"code": "NOT_FOUND"})
        result: dict[str, Any] = d[rid].model_dump()
        return result

    @router.get("/audit-log/recent")
    async def audit_recent(
        limit: int = 20,
        principal: RequestPrincipal = Depends(_read_dep),  # type: ignore[arg-type]
        session: AsyncSession = Depends(session_provider),  # type: ignore[arg-type]
    ) -> dict[str, Any]:
        limit = min(max(1, limit), 50)
        rows = await session.execute(text(
            "SELECT id, ts, token_label, scope, tool, outcome, error_code "
            "FROM audit_log ORDER BY id DESC LIMIT :l"
        ), {"l": limit})
        return {"items": [
            {
                "id": r.id,
                "ts": r.ts.isoformat() if r.ts else None,
                "token_label": r.token_label,
                "scope": r.scope,
                "tool": r.tool,
                "outcome": r.outcome,
                "error_code": r.error_code,
            }
            for r in rows
        ]}

    # --- Lifecycle write endpoints (admin scope) ---

    @router.post("/registries/promote")
    async def promote(
        principal: RequestPrincipal = Depends(_admin_dep),  # type: ignore[arg-type]
        session: AsyncSession = Depends(session_provider),  # type: ignore[arg-type]
    ) -> dict[str, Any]:
        from onto_platform.registry.lifecycle import promote_staging_to_production
        from onto_platform.config import Settings
        from onto_platform.connections.store import ConnectionStore
        settings = Settings()
        cs = ConnectionStore(secret_key=settings.secret_key)
        conn_ids = {str(c.id) for c in await cs.list_all(session)}
        await promote_staging_to_production(
            session,
            rstore,
            commit_message="Promoted via API",
            token_label=principal.label,
            connection_ids=conn_ids,
        )
        await session.commit()
        return {"ok": True}

    @router.post("/registries/revert")
    async def revert(
        principal: RequestPrincipal = Depends(_admin_dep),  # type: ignore[arg-type]
        session: AsyncSession = Depends(session_provider),  # type: ignore[arg-type]
    ) -> dict[str, Any]:
        from onto_platform.registry.lifecycle import revert_staging_to_production
        await revert_staging_to_production(session, rstore, token_label=principal.label)
        await session.commit()
        return {"ok": True}

    @router.post("/registries/undo-promote")
    async def api_undo_promote(
        principal: RequestPrincipal = Depends(_admin_dep),  # type: ignore[arg-type]
        session: AsyncSession = Depends(session_provider),  # type: ignore[arg-type]
    ) -> dict[str, Any]:
        from onto_platform.registry.lifecycle import undo_promote
        await undo_promote(session, rstore, token_label=principal.label)
        await session.commit()
        return {"ok": True}

    return router


# =============================================================================
# Public Ontology Schema & Graph Router (no auth required)
# =============================================================================

def get_ontology_router(session_provider, _rstore):
    """Create the public ontology schema/graph router."""
    from onto_platform.registry.store import RegistryStore
    from onto_platform.config import Settings
    from fastapi import Depends, APIRouter
    from sqlalchemy.ext.asyncio import AsyncSession

    ontology_router = APIRouter(prefix="/ontology")

    def _to_dict(model) -> dict[str, Any]:
        """Convert Pydantic model to dict, handling nested models."""
        result = {}
        for field_name, field_info in model.model_fields.items():
            value = getattr(model, field_name)
            if value is None:
                result[field_name] = None
            elif isinstance(value, dict):
                result[field_name] = {
                    k: _to_dict(v) if hasattr(v, 'model_fields') else v
                    for k, v in value.items()
                }
            elif isinstance(value, list):
                result[field_name] = [
                    _to_dict(item) if hasattr(item, 'model_fields') else item
                    for item in value
                ]
            elif hasattr(value, 'model_fields'):
                result[field_name] = _to_dict(value)
            elif isinstance(value, Enum):
                result[field_name] = value.value
            else:
                result[field_name] = value
        return result

    @ontology_router.get("/schema")
    async def get_ontology_schema(
        env: str = "production",
        session: AsyncSession = Depends(session_provider),
    ) -> dict[str, Any]:
        """Get full ontology schema for the given environment."""
        rstore = RegistryStore()
        snap = await rstore.load(session, Env(env))
        return _to_dict(snap.registry)

    @ontology_router.get("/graph")
    async def get_ontology_graph(
        env: str = "production",
        session: AsyncSession = Depends(session_provider),
    ) -> dict[str, Any]:
        """Get ontology graph from Neo4j in reagraph format."""
        nodes = []
        edges = []

        try:
            from neo4j import AsyncGraphDatabase
            settings = Settings()
            neo4j_uri = getattr(settings, 'neo4j_uri', 'bolt://demo-neo4j-1:7687')

            driver = AsyncGraphDatabase.driver(neo4j_uri, auth=("neo4j", "ontology_pass_2026"))
            async with driver.session() as db:
                # Get ObjectType nodes (new Manufacturing ontology)
                result = await db.run(
                    "MATCH (n:ObjectTypeDef:Manufacturing) RETURN n.apiName as id, n.displayName as label, n.description as description, n.apiName as api_name"
                )
                async for record in result:
                    nodes.append({
                        "id": record["id"],
                        "label": record["label"] or record["api_name"] or "",
                        "description": record["description"] or "",
                        "nodeType": "ObjectTypeDef",
                        "group": "objects"
                    })

                # Get InterfaceType nodes (new Manufacturing ontology)
                result = await db.run(
                    "MATCH (n:InterfaceDef:Manufacturing) RETURN n.apiName as id, n.displayName as label, n.description as description, n.apiName as api_name"
                )
                async for record in result:
                    nodes.append({
                        "id": record["id"],
                        "label": record["label"] or record["api_name"] or "",
                        "description": record["description"] or "",
                        "nodeType": "InterfaceTypeDef",
                        "group": "interfaces"
                    })

                # Get ActionType nodes (new Manufacturing ontology)
                result = await db.run(
                    "MATCH (n:ActionTypeDef:Manufacturing) RETURN n.apiName as id, n.displayName as label, n.description as description, n.apiName as api_name"
                )
                async for record in result:
                    nodes.append({
                        "id": record["id"],
                        "label": record["label"] or record["api_name"] or "",
                        "description": record["description"] or "",
                        "nodeType": "ActionTypeDef",
                        "group": "actions"
                    })

                # Get LINKS_TO edges (new Manufacturing ontology)
                result = await db.run(
                    "MATCH (a:ObjectTypeDef:Manufacturing)-[r:LINKS_TO]->(b:ObjectTypeDef:Manufacturing) RETURN r.apiName as id, a.apiName as source, b.apiName as target, r.displayName as label"
                )
                async for record in result:
                    edges.append({
                        "id": record["id"] or f"link-{record['source']}-{record['target']}",
                        "source": record["source"],
                        "target": record["target"],
                        "edgeType": "LINK",
                        "label": record["label"] or ""
                    })

                # Get IMPLEMENTS edges (new Manufacturing ontology)
                result = await db.run(
                    "MATCH (a:ObjectTypeDef:Manufacturing)-[r:IMPLEMENTS]->(i:InterfaceDef:Manufacturing) RETURN a.apiName as source, i.apiName as target"
                )
                async for record in result:
                    edges.append({
                        "id": f"impl-{record['source']}-{record['target']}",
                        "source": record["source"],
                        "target": record["target"],
                        "edgeType": "IMPLEMENTS",
                        "label": "implements"
                    })

            await driver.close()
        except Exception as e:
            import logging
            logging.getLogger().error(f"Neo4j query failed: {e}")
            pass

        return {"nodes": nodes, "edges": edges}

    return ontology_router
