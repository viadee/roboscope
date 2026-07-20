"""RoboScope FastAPI application entry point."""

import asyncio
import logging
import os
import sys
import uuid
import webbrowser
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pythonjsonlogger.json import JsonFormatter
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy.orm import Session
from starlette.responses import FileResponse

from src.api.v1.router import api_router
from src.config import settings
from src.database import create_tables, get_db, SessionLocal
from src.rate_limit import limiter
from src.utc_response import UtcJSONResponse
from src.websocket.manager import ws_manager

logger = logging.getLogger("roboscope")

# Event loop reference for background threads to schedule async work
_event_loop: asyncio.AbstractEventLoop | None = None


def _build_formatter() -> logging.Formatter:
    """Pick the log formatter based on LOG_FORMAT env var.

    `LOG_FORMAT=text` → readable single-line `LEVEL  logger: message`
    for humans launching the standalone bundle from a terminal.
    Anything else (including unset) → JSON for log shippers in
    `make dev`, Docker, and CI.
    """
    if os.environ.get("LOG_FORMAT", "json").lower() == "text":
        return logging.Formatter(
            fmt="%(levelname)-5s %(name)s: %(message)s",
        )
    return JsonFormatter(
        fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
        rename_fields={"asctime": "timestamp", "levelname": "level", "name": "logger"},
    )


def _supports_unicode_box() -> bool:
    """Return True iff the terminal is likely to render `═` correctly.

    Windows cmd / PowerShell in legacy code-page modes mojibakes
    Unicode box-drawing chars; we fall back to ASCII (`====`) there.
    """
    if sys.platform == "win32":
        return False
    encoding = (os.environ.get("PYTHONIOENCODING") or "").lower()
    return not encoding or "utf-8" in encoding or "utf8" in encoding


def _print_ready_banner() -> None:
    """Print the loud "open this URL" banner to stdout.

    Goes through `print()` (NOT the logger) so it survives both
    JSON and text log formats and is never mistaken for an INFO
    line. Suppressed under pytest to keep test output clean.
    """
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return
    port = settings.PORT
    url = f"http://localhost:{port}"
    if _supports_unicode_box():
        bar = "═" * 56
        check = "✓"
    else:
        bar = "=" * 56
        check = "*"
    # Blank line first so the banner separates cleanly from boot logs.
    print(f"\n{bar}", flush=True)
    print(f" {check}  RoboScope is running", flush=True)
    print(f"    Open in your browser:  {url}", flush=True)
    print(f"{bar}\n", flush=True)

    if os.environ.get("OPEN_BROWSER", "").strip() in ("1", "true", "yes"):
        try:
            webbrowser.open(url)
        except Exception:
            # Headless or BROWSER misconfigured — banner already
            # tells the user where to go, so don't fail startup.
            logger.warning("OPEN_BROWSER set but webbrowser.open failed", exc_info=True)


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
    handler.setFormatter(_build_formatter())
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

    # H4: reap runs orphaned by a previous backend restart (the in-memory
    # runner registry is empty now, so any PENDING/RUNNING row is dead).
    try:
        from src.execution.tasks import reconcile_interrupted_runs
        reconcile_interrupted_runs()
    except Exception:
        logger.warning("startup run reconciliation failed", exc_info=True)

    # EXEC.10: warm the curated-modifier registry at boot so a broken org
    # modifier (entry-point / ROBOSCOPE_MODIFIERS_CONFIG) surfaces in the startup
    # logs immediately rather than on the first run-dialog open. Never fatal.
    try:
        from src.execution.modifiers import load_registry
        load_registry(force=True)
    except Exception:
        logger.warning("startup modifier-registry load failed", exc_info=True)

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

    # Auto-start rf-mcp (bundled dependency — always start). Skipped under
    # pytest (same signal as the ready banner): every TestClient lifespan
    # would otherwise spawn a real rf-mcp subprocess through the single-worker
    # task executor, competing with the tasks the test actually dispatched.
    if os.environ.get("PYTEST_CURRENT_TEST"):
        logger.info("pytest detected — skipping rf-mcp auto-start")
    else:
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

    # DEBUG-2: wire the in-process debug-session manager. The manager
    # forwards DAP events through the existing /ws/notifications
    # broadcast channel; the state-fetcher pulls stack/scopes via the
    # foundation's DapClient after every `stopped` event so the
    # frontend gets a live variable snapshot pushed.
    from src.debug.session_manager import session_manager
    from src.debug.state_fetcher import fetch_state

    def _debug_forwarder(topic: str, kind: str, body: dict[str, object]) -> None:
        # Called from inside the session manager's asyncio task — we
        # already have a running loop, so a direct create_task on the
        # broadcast coroutine is safe.
        coro = ws_manager.broadcast({
            "type": "debug_event",
            "topic": topic,
            "kind": kind,
            "body": body,
        })
        asyncio.create_task(coro)

    session_manager.set_forwarder(_debug_forwarder)
    session_manager.set_state_fetcher(fetch_state)

    logger.info("RoboScope started successfully")

    # Loud "open this URL" cue for users running the standalone
    # bundle. Suppressed in tests, doesn't break Docker / dev mode
    # (it's just three lines on stdout).
    _print_ready_banner()

    yield

    # Shutdown
    logger.info("Shutting down RoboScope...")

    # Tear down active debug sessions (best-effort; users may have
    # paused subprocesses we should clean up).
    try:
        await session_manager.stop_all()
    except Exception:  # noqa: BLE001
        logger.exception("Failed to stop debug sessions cleanly")

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

    # WebSocket auth helper: validate JWT token from query parameter AND
    # that the account is still active. Takes `db` via `Depends(get_db)`
    # (NOT a raw `SessionLocal()`) so tests can exercise these checks
    # through the same `app.dependency_overrides[get_db]` swap the HTTP
    # test client uses — FastAPI resolves WebSocket route dependencies
    # through the same DI machinery as HTTP routes, sync generators
    # included, so this doesn't block the event loop either. Before this
    # fix, a still-valid JWT for a deactivated account could keep
    # receiving live broadcasts indefinitely (audit finding 2.5 — the SSE
    # recorder endpoint already checked is_active, WS didn't).
    def _ws_authenticate(token: str | None, db: Session) -> bool:
        """Return True if the token is a valid, non-expired access JWT
        for an active user."""
        if not token:
            return False
        try:
            from src.auth.service import decode_token, get_user_by_id
            payload = decode_token(token)
            if payload.get("type") != "access":
                return False
            user = get_user_by_id(db, int(payload["sub"]))
            return user is not None and user.is_active
        except (ValueError, KeyError, TypeError):
            return False

    # WebSocket auth helper: effective-role gate for a specific run's
    # repository (audit finding 1.2). Mirrors
    # `require_effective_role_for_run` — WebSocket-shaped: no
    # Authorization header (browsers' WebSocket API can't set one, same
    # constraint as EventSource/SSE), so the JWT travels via `?token=`;
    # a failure closes the socket instead of raising HTTPException.
    # Callers must call `_ws_authenticate(token, db)` FIRST — this
    # assumes a syntactically valid, active-user token and only adds the
    # role check.
    def _ws_authorize_run(token: str, run_id: int, min_role, db: Session) -> bool:
        from src.auth.constants import ROLE_HIERARCHY
        from src.auth.permissions import effective_role
        from src.auth.service import decode_token, get_user_by_id
        from src.execution.models import ExecutionRun
        from src.repos.models import Repository

        try:
            payload = decode_token(token)
            user_id = int(payload["sub"])
        except (ValueError, KeyError, TypeError):
            return False

        user = get_user_by_id(db, user_id)
        if user is None or not user.is_active:
            return False
        run = db.get(ExecutionRun, run_id)
        if run is None:
            return False
        repo = db.get(Repository, run.repository_id)
        if repo is None:
            return False
        er = effective_role(db, user, repo)
        return ROLE_HIERARCHY.get(er, -1) >= ROLE_HIERARCHY.get(min_role, 999)

    # WebSocket: global notifications
    @app.websocket("/ws/notifications")
    async def ws_notifications(
        websocket: WebSocket,
        token: str = Query(default=""),
        db: Session = Depends(get_db),
    ):
        if not _ws_authenticate(token, db):
            await websocket.close(code=4401, reason="Unauthorized")
            return
        # Release the pooled DB connection BEFORE the (possibly hours-long)
        # receive loop. A Depends(get_db) session is only finalized after the
        # handler returns — i.e. after disconnect — so without this each open
        # socket pins one connection out of the pool (default 5+10 on SQLite),
        # and ~15 concurrent sockets starve every HTTP request (code-review
        # 2026-07-19). rollback() ends the auth transaction and returns the
        # connection to the pool; the loop below does no DB work, and get_db's
        # own finalizer still closes the (idle) session on disconnect.
        db.rollback()
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
        websocket: WebSocket,
        run_id: int,
        token: str = Query(default=""),
        db: Session = Depends(get_db),
    ):
        from src.auth.constants import Role

        if not _ws_authenticate(token, db):
            await websocket.close(code=4401, reason="Unauthorized")
            return
        # 1.2: before this fix, ANY authenticated user could stream ANY
        # repo's run output — there was no run/repo lookup at all. VIEWER
        # is `effective_role()`'s documented no-deny floor (any user with
        # a valid global role already clears it — read access is
        # intentionally open system-wide, matching GET /runs/{run_id}),
        # so the observable hardening here is: the run/repo must actually
        # exist, and a deactivated account (checked inside
        # `_ws_authorize_run` too) can't ride a still-valid JWT in.
        if not _ws_authorize_run(token, run_id, Role.VIEWER, db):
            await websocket.close(code=4403, reason="Forbidden")
            return
        # Release the pooled DB connection before the receive loop — see the
        # ws_notifications rollback above (code-review 2026-07-19).
        db.rollback()
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
