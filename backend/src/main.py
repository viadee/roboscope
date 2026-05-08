"""RoboScope FastAPI application entry point."""

import asyncio
import logging
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pythonjsonlogger.json import JsonFormatter
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.responses import FileResponse

from src.api.v1.router import api_router
from src.config import settings
from src.database import create_tables, SessionLocal
from src.rate_limit import limiter
from src.utc_response import UtcJSONResponse
from src.websocket.manager import ws_manager

logger = logging.getLogger("roboscope")

# Event loop reference for background threads to schedule async work
_event_loop: asyncio.AbstractEventLoop | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifecycle."""
    global _event_loop
    _event_loop = asyncio.get_running_loop()

    # Startup — structured JSON logging with request-id correlation
    # (story LOGGING-1: `RequestIdFilter` adds `record.request_id`
    # whenever an HTTP middleware is active in the current async
    # context; pythonjsonlogger picks up custom record attributes
    # automatically — no fmt-string entry needed, so background-task
    # / startup logs stay clean of phantom request_id fields).
    from src.logging_context import RequestIdFilter

    handler = logging.StreamHandler()
    formatter = JsonFormatter(
        fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
        rename_fields={"asctime": "timestamp", "levelname": "level", "name": "logger"},
    )
    handler.setFormatter(formatter)
    handler.addFilter(RequestIdFilter())
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(getattr(logging, settings.LOG_LEVEL))
    logger.info(f"Starting RoboScope v{settings.VERSION}")
    logger.info(f"Database: {'SQLite' if settings.is_sqlite else 'PostgreSQL'}")
    logger.info("Task executor: in-process ThreadPoolExecutor (max_workers=1)")

    # Require SECRET_KEY to be set explicitly
    if not settings.SECRET_KEY:
        logger.error(
            "SECRET_KEY is not set! Set SECRET_KEY in your .env file "
            "(generate with: openssl rand -hex 32)"
        )
        raise SystemExit(1)

    # Create tables (in production, use Alembic migrations instead)
    create_tables()

    # Seed default admin user
    with SessionLocal() as session:
        from src.auth.service import ensure_admin_exists
        ensure_admin_exists(session)
        session.commit()

    # Seed default settings
    with SessionLocal() as session:
        from src.settings.service import seed_default_settings
        seed_default_settings(session)
        session.commit()

    # Seed "Examples" project with bundled test files
    with SessionLocal() as session:
        from src.repos.models import Repository
        from sqlalchemy import select
        result = session.execute(
            select(Repository).where(Repository.name == "Examples")
        )
        if result.scalar_one_or_none() is None:
            examples_dir = Path(__file__).resolve().parent.parent / "examples" / "tests"
            if examples_dir.is_dir():
                repo = Repository(
                    name="Examples",
                    repo_type="local",
                    local_path=str(examples_dir),
                    default_branch="main",
                    auto_sync=False,
                    created_by=1,
                )
                session.add(repo)
                session.commit()
                logger.info("Seeded 'Examples' project: %s", examples_dir)
            else:
                logger.warning("Examples directory not found: %s", examples_dir)

    # Seed "Robot Framework Examples" git project — public reference
    # suite living at github.com/raffelino/robot-framework-examples.
    # Covers the typical RF libraries + language concepts; first-time
    # users get a working playground without configuring a Git URL by
    # hand. Auto-sync is OFF by default so we don't surprise the user
    # with background pulls; the manual Sync button still works.
    with SessionLocal() as session:
        from src.repos.models import Repository
        from sqlalchemy import select
        from src.task_executor import dispatch_task

        EXAMPLES_REPO_NAME = "Robot Framework Examples"
        EXAMPLES_REPO_URL = (
            "https://github.com/raffelino/robot-framework-examples.git"
        )
        result = session.execute(
            select(Repository).where(Repository.name == EXAMPLES_REPO_NAME)
        )
        if result.scalar_one_or_none() is None:
            workspace = Path(settings.WORKSPACE_DIR)
            workspace.mkdir(parents=True, exist_ok=True)
            repo = Repository(
                name=EXAMPLES_REPO_NAME,
                repo_type="git",
                git_url=EXAMPLES_REPO_URL,
                default_branch="main",
                local_path=str(workspace / "robot-framework-examples"),
                auto_sync=False,
                sync_interval_minutes=60,
                pre_run_sync=False,
                created_by=1,
            )
            session.add(repo)
            session.commit()
            logger.info(
                "Seeded '%s' project (git): %s", EXAMPLES_REPO_NAME, EXAMPLES_REPO_URL,
            )
            # Kick off the initial clone in the background so the
            # project shows up in the UI immediately and the working
            # tree fills in within a few seconds.
            try:
                from src.repos.tasks import sync_repo
                dispatch_task(sync_repo, repo.id)
                logger.info("Dispatched initial clone for repo %d", repo.id)
            except Exception:
                logger.exception(
                    "Initial clone dispatch failed for %s — user can "
                    "click Sync manually to retry",
                    EXAMPLES_REPO_NAME,
                )

    # Reset stuck background tasks from previous runs
    with SessionLocal() as session:
        from src.environments.models import Environment, EnvironmentPackage
        from src.repos.models import Repository
        stuck_builds = session.query(Environment).filter(
            Environment.docker_build_status == "building"
        ).all()
        for env in stuck_builds:
            env.docker_build_status = "error"
            env.docker_build_error = "Build interrupted — application was restarted."
            logger.warning("Reset stuck Docker build for env '%s' (id=%d)", env.name, env.id)

        stuck_pkgs = session.query(EnvironmentPackage).filter(
            EnvironmentPackage.install_status.in_(["pending", "installing"])
        ).all()
        for pkg in stuck_pkgs:
            pkg.install_status = "failed"
            pkg.install_error = "Installation interrupted — application was restarted."
            logger.warning(
                "Reset stuck package '%s' in env %d", pkg.package_name, pkg.environment_id,
            )

        # Repositories whose `sync_repo` task was killed mid-pull keep
        # `sync_status='syncing'` forever — auto-sync skips them as
        # "in flight" and the UI shows an indefinite spinner. Surface
        # the interrupt so the user can re-trigger a manual sync.
        stuck_syncs = session.query(Repository).filter(
            Repository.sync_status == "syncing"
        ).all()
        for repo in stuck_syncs:
            repo.sync_status = "error"
            repo.sync_error = "Sync interrupted — application was restarted."
            logger.warning("Reset stuck sync for repo '%s' (id=%d)", repo.name, repo.id)

        if stuck_builds or stuck_pkgs or stuck_syncs:
            session.commit()

    # Discover and load plugins
    from src.plugins.registry import plugin_registry
    plugin_registry.discover_builtin()

    # Auto-start rf-mcp (bundled dependency — always start)
    with SessionLocal() as session:
        from src.settings.service import get_setting_value
        env_id_str = get_setting_value(session, "rf_mcp_environment_id", "")
        port_str = get_setting_value(session, "rf_mcp_port", str(settings.RF_MCP_PORT))

        from src.task_executor import dispatch_task
        from src.ai import rf_mcp_manager
        env_id = int(env_id_str) if env_id_str else None
        port = int(port_str)
        rf_mcp_manager._status = "starting"
        rf_mcp_manager._environment_id = env_id
        try:
            dispatch_task(rf_mcp_manager.start_bundled, env_id, port)
            logger.info("Auto-starting rf-mcp (env_id=%s, port=%d)", env_id, port)
        except Exception:
            logger.warning("Failed to auto-start rf-mcp", exc_info=True)

    # Start retention enforcement scheduler (daily cleanup)
    from datetime import datetime, timedelta, timezone as _timezone
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.interval import IntervalTrigger
    from src.audit.retention import enforce_retention
    from src.auth.discovery_refresh import refresh_discovery_cache
    from src.auth.retention_cleanup import run_hourly_cleanup

    _scheduler = BackgroundScheduler()
    _scheduler.add_job(
        enforce_retention,
        trigger=IntervalTrigger(hours=24),
        id="retention_enforcement",
        name="Retention Enforcement (daily)",
        replace_existing=True,
    )
    # Defer first discovery refresh 24h after boot — preserves the zero-outbound-call
    # boot invariant (AR16 / AC1). Without next_run_time, APScheduler fires immediately.
    _scheduler.add_job(
        refresh_discovery_cache,
        trigger=IntervalTrigger(hours=24),
        id="oidc_discovery_refresh",
        name="OIDC Discovery Cache Refresh (24h)",
        next_run_time=datetime.now(_timezone.utc) + timedelta(hours=24),
        replace_existing=True,
    )
    # Story 5-5: hourly cleanup of expired OidcLoginAttempt and stale
    # RateLimitCounter rows so Phase 4 tables don't grow unbounded.
    _scheduler.add_job(
        run_hourly_cleanup,
        trigger=IntervalTrigger(hours=1),
        id="phase4_hourly_cleanup",
        name="Phase 4 retention cleanup (hourly)",
        replace_existing=True,
    )
    # Story REPO-2: auto-sync scheduler. Every 5 min, find repos
    # whose `auto_sync=True` and `last_synced_at < now - sync_interval_minutes`,
    # dispatch a sync_repo task for each. The 5-min heartbeat is the
    # finest granularity worth the wake-up cost; per-repo
    # sync_interval_minutes is the actual cadence the user controls.
    from src.repos.tasks import auto_sync_due_repos
    _scheduler.add_job(
        auto_sync_due_repos,
        trigger=IntervalTrigger(minutes=5),
        id="repo_auto_sync",
        name="Repository auto-sync (every 5 min)",
        replace_existing=True,
        # Review fix S3 — APScheduler defaults are tight: a single
        # delayed wake-up (e.g. behind a slow retention sweep) can drop
        # the tick. `coalesce=True` collapses multiple missed runs into
        # one; `misfire_grace_time=60` gives the scheduler a minute to
        # catch up before declaring the run lost.
        coalesce=True,
        misfire_grace_time=60,
    )
    _scheduler.start()
    logger.info(
        "Scheduler started: retention (every 24h), OIDC discovery refresh "
        "(every 24h, first run deferred), Phase 4 cleanup (every 1h), "
        "repo auto-sync (every 5m)"
    )

    logger.info("RoboScope started successfully")
    yield

    # Shutdown
    logger.info("Shutting down RoboScope...")

    # Shut down retention scheduler
    _scheduler.shutdown(wait=False)

    # Stop rf-mcp server if running
    from src.ai import rf_mcp_manager
    if rf_mcp_manager.is_running():
        rf_mcp_manager.stop_server()
        logger.info("Stopped rf-mcp server")

    # Gracefully shut down background task executor
    from src.task_executor import shutdown_executor
    shutdown_executor(wait=False)

    from src.plugins.registry import plugin_registry
    plugin_registry.shutdown_all()


def create_app() -> FastAPI:
    """Application factory."""
    app = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        description="Web-based Robot Framework Test Management Tool",
        openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
        docs_url=f"{settings.API_V1_PREFIX}/docs",
        redoc_url=f"{settings.API_V1_PREFIX}/redoc",
        lifespan=lifespan,
        # Naive UTC datetime → `...Z` on the wire. SQLAlchemy on SQLite
        # strips `tzinfo` so Pydantic emits naive ISO; this guarantees
        # every JS client reads timestamps as real UTC. See utc_response.py.
        default_response_class=UtcJSONResponse,
    )

    # Rate limiting
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Audit middleware — logs all write operations (POST/PUT/PATCH/DELETE) to audit_logs
    from src.audit.middleware import AuditMiddleware
    app.add_middleware(AuditMiddleware)

    # Request ID middleware — attaches a unique ID to each request for log correlation.
    # Story LOGGING-1: also publishes the ID on the
    # `request_id_var` ContextVar so the `RequestIdFilter` can stamp
    # every log record emitted during this request.
    from src.logging_context import request_id_var

    @app.middleware("http")
    async def add_request_id(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", uuid.uuid4().hex[:12])
        request.state.request_id = request_id
        token = request_id_var.set(request_id)
        try:
            response = await call_next(request)
        finally:
            # Reset on the way out — uvicorn reuses worker tasks for
            # keep-alive, so leaking the ContextVar would leak the id
            # into the *next* request.
            request_id_var.reset(token)
        response.headers["X-Request-ID"] = request_id
        return response

    # API routes
    app.include_router(api_router, prefix=settings.API_V1_PREFIX)

    # Health check
    # Story ROBUSTNESS-1: deep health-check. The previous endpoint
    # returned 200 unconditionally — Kubernetes / ECS livenessProbes
    # would never see a hung-DB pod and never restart it. Now we run
    # a `SELECT 1` roundtrip; on failure we return 503 with the
    # `unhealthy` status so orchestrators flag the pod for restart.
    @app.get("/health")
    async def health_check():
        from fastapi import Response
        from sqlalchemy import text as sql_text

        from src.database import engine

        body = {
            "status": "healthy",
            "version": settings.VERSION,
            "database": "sqlite" if settings.is_sqlite else "postgresql",
            "task_executor": "in-process",
        }
        try:
            with engine.connect() as conn:
                conn.execute(sql_text("SELECT 1"))
        except Exception as e:
            return Response(
                content=__import__("json").dumps({
                    **body,
                    "status": "unhealthy",
                    "reason": "database_unreachable",
                    "error": str(e)[:200],
                }),
                status_code=503,
                media_type="application/json",
            )
        return body

    # WebSocket auth helper: validate JWT token from query parameter
    def _ws_authenticate(token: str | None) -> bool:
        """Return True if the token is valid."""
        if not token:
            return False
        try:
            from src.auth.service import decode_token
            decode_token(token)
            return True
        except (ValueError, Exception):
            return False

    # WebSocket: global notifications
    @app.websocket("/ws/notifications")
    async def ws_notifications(websocket: WebSocket, token: str = Query(default="")):
        if not _ws_authenticate(token):
            await websocket.close(code=4401, reason="Unauthorized")
            return
        await ws_manager.connect(websocket)
        try:
            while True:
                # Keep connection alive, listen for client messages
                data = await websocket.receive_text()
                # Client can send ping/pong
                if data == "ping":
                    await websocket.send_text("pong")
        except WebSocketDisconnect:
            ws_manager.disconnect(websocket)

    # WebSocket: run-specific live output
    @app.websocket("/ws/runs/{run_id}")
    async def ws_run_output(
        websocket: WebSocket, run_id: int, token: str = Query(default=""),
    ):
        if not _ws_authenticate(token):
            await websocket.close(code=4401, reason="Unauthorized")
            return
        await ws_manager.connect_to_run(websocket, run_id)
        try:
            while True:
                data = await websocket.receive_text()
                if data == "ping":
                    await websocket.send_text("pong")
        except WebSocketDisconnect:
            ws_manager.disconnect_from_run(websocket, run_id)

    # Serve pre-built frontend static files (for standalone / offline mode).
    # The frontend dist/ folder is expected next to the backend package.
    frontend_dist = Path(__file__).resolve().parent.parent / "frontend_dist"
    if not frontend_dist.is_dir():
        # Fallback: check relative to current working directory (start script cd's to dist root)
        frontend_dist = Path.cwd() / "frontend_dist"
    if frontend_dist.is_dir():
        # Serve assets (JS, CSS, images) under /assets
        assets_dir = frontend_dist / "assets"
        if assets_dir.is_dir():
            app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="frontend-assets")

        # Serve other static files (favicon, etc.) at root level
        app.mount("/static", StaticFiles(directory=str(frontend_dist)), name="frontend-static")

        # SPA catch-all: serve index.html for any non-API, non-WS route
        index_html = frontend_dist / "index.html"

        @app.get("/{full_path:path}")
        async def spa_fallback(full_path: str):
            # Serve the file if it exists in frontend_dist
            file_path = frontend_dist / full_path
            if full_path and file_path.is_file():
                return FileResponse(str(file_path))
            return FileResponse(str(index_html))

        logger.info("Serving frontend from %s", frontend_dist)
    else:
        logger.warning(
            "frontend_dist not found (checked %s and %s). "
            "Frontend will not be served — API-only mode.",
            Path(__file__).resolve().parent.parent / "frontend_dist",
            Path.cwd() / "frontend_dist",
        )

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )
