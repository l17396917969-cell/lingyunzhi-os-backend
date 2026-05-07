import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from onto_platform.bootstrap import bootstrap_admin_token_if_needed
from onto_platform.config import Settings
from onto_platform.db import get_sessionmaker, make_engine
from onto_platform.health import make_health_router
from onto_platform.logging_setup import configure_logging
from onto_platform.mcp_server import make_mcp_router
from onto_platform import mcp_tools_read as _mcp_tools_read  # noqa: F401
from onto_platform import mcp_tools_editor as _mcp_tools_editor  # noqa: F401
from onto_platform import mcp_tools_admin as _mcp_tools_admin  # noqa: F401
from onto_platform import mcp_tools_ingestion as _mcp_tools_ingestion  # noqa: F401
from onto_platform.ui_auth import make_ui_auth_router
from onto_platform.api_routes import make_api_router, get_ontology_router
from onto_platform.data_routes import make_data_router
from onto_platform.ingestion.http import make_ingestion_router
from onto_platform.ingestion.workers import IngestionWorker
from onto_platform.ingestion.llm_client import LiteLLMClient, StubLiteLLM
from onto_platform.chat.orchestrator import ChatSessionOrchestrator
from onto_platform.chat.recovery import sweep_orphan_sessions
from onto_platform.chat.http import make_chat_router
from onto_platform.registry.store import RegistryStore
from onto_platform.connections.store import ConnectionStore
from onto_platform.connections.pool import ConnectionPool
from onto_platform.connections.query_builder import InstanceQueryBuilder


def create_app() -> FastAPI:
    settings = Settings()
    configure_logging(settings.log_level)
    engine = make_engine(settings.database_url)
    Session: async_sessionmaker[AsyncSession] = get_sessionmaker(engine)

    chat_orch = ChatSessionOrchestrator(
        Session,
        RegistryStore(),
        max_sessions_per_token=settings.chat_max_concurrent_sessions_per_token,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        await bootstrap_admin_token_if_needed(Session)
        await sweep_orphan_sessions(
            chat_orch, Session, orphan_after_s=settings.chat_session_orphan_after_s
        )
        yield
        await engine.dispose()

    app = FastAPI(title="Onto Platform", lifespan=lifespan)

    async def session_provider() -> AsyncGenerator[AsyncSession, None]:
        async with Session() as s:
            yield s

    # Build LLM client
    if settings.llm_api_key:
        llm: LiteLLMClient | StubLiteLLM = LiteLLMClient(
            model=settings.llm_model,
            api_base=settings.llm_base_url,
            api_key=settings.llm_api_key,
            request_timeout_s=settings.llm_request_timeout_s,
        )
    else:
        llm = StubLiteLLM(responses=[])

    worker = IngestionWorker(factory=Session, settings=settings, llm=llm)

    # Data source query infrastructure
    conn_store = ConnectionStore(secret_key=settings.secret_key)
    conn_pool = ConnectionPool(store=conn_store)
    query_builder = InstanceQueryBuilder(
        registry_store=RegistryStore(),
        connection_pool=conn_pool,
        connection_store=conn_store,
    )

    app.state.settings = settings
    app.state.session_factory = Session
    app.state.session_provider = session_provider
    app.state.worker = worker
    app.state.chat_orchestrator = chat_orch
    app.state.connection_pool = conn_pool

    def _get_worker() -> Optional[IngestionWorker]:
        return app.state.worker  # type: ignore[no-any-return]

    app.include_router(make_health_router(session_provider))
    app.include_router(make_mcp_router(session_provider, app_state=app.state))
    app.include_router(make_ui_auth_router(session_provider, settings))
    app.include_router(make_api_router(session_provider))
    app.include_router(make_data_router(session_provider, query_builder))
    app.include_router(
        make_ingestion_router(session_provider, get_worker=_get_worker, settings=settings)
    )
    app.include_router(
        make_chat_router(
            session_provider,
            session_factory=Session,
            settings=settings,
            orchestrator=chat_orch,
            llm=llm,
        )
    )

    # Public ontology schema/graph endpoints (before SPA catch-all)
    rstore = RegistryStore()
    ontology_router = get_ontology_router(session_provider, rstore)
    app.include_router(ontology_router)

    ui_dist = os.environ.get("ONTO_UI_DIST_PATH", "/srv/ui/dist")
    if os.path.isdir(ui_dist):
        _index_html = os.path.join(ui_dist, "index.html")
        _assets_dir = os.path.join(ui_dist, "assets")
        if os.path.isdir(_assets_dir):
            app.mount("/assets", StaticFiles(directory=_assets_dir), name="ui-assets")

        @app.get("/{full_path:path}", include_in_schema=False)
        async def _spa_fallback(full_path: str) -> FileResponse:
            candidate = os.path.normpath(os.path.join(ui_dist, full_path)) if full_path else _index_html
            if candidate.startswith(os.path.realpath(ui_dist)) and os.path.isfile(candidate):
                return FileResponse(candidate)
            return FileResponse(_index_html)

    return app
