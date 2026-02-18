"""mateoX FastAPI application entry point."""

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.responses import FileResponse

from src.api.v1.router import api_router
from src.config import settings
from src.database import create_tables, get_db, AsyncSessionLocal
from src.websocket.manager import ws_manager

logger = logging.getLogger("mateox")

# Event loop reference for background threads to schedule async work
_event_loop: asyncio.AbstractEventLoop | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifecycle."""
    global _event_loop
    _event_loop = asyncio.get_running_loop()

    # Startup
    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logger.info(f"Starting mateoX v{settings.VERSION}")
    logger.info(f"Database: {'SQLite' if settings.is_sqlite else 'PostgreSQL'}")
    logger.info("Task executor: in-process ThreadPoolExecutor (max_workers=1)")

    # Create tables (in production, use Alembic migrations instead)
    await create_tables()

    # Seed default admin user
    async with AsyncSessionLocal() as session:
        from src.auth.service import ensure_admin_exists
        await ensure_admin_exists(session)
        await session.commit()

    # Seed default settings
    async with AsyncSessionLocal() as session:
        from src.settings.service import seed_default_settings
        await seed_default_settings(session)
        await session.commit()

    # Seed "Examples" project with bundled test files
    async with AsyncSessionLocal() as session:
        from src.repos.models import Repository
        from sqlalchemy import select
        result = await session.execute(
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
                await session.commit()
                logger.info("Seeded 'Examples' project: %s", examples_dir)
            else:
                logger.warning("Examples directory not found: %s", examples_dir)

    # Discover and load plugins
    from src.plugins.registry import plugin_registry
    plugin_registry.discover_builtin()

    logger.info("mateoX started successfully")
    yield

    # Shutdown
    logger.info("Shutting down mateoX...")
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
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # API routes
    app.include_router(api_router, prefix=settings.API_V1_PREFIX)

    # Health check
    @app.get("/health")
    async def health_check():
        return {
            "status": "healthy",
            "version": settings.VERSION,
            "database": "sqlite" if settings.is_sqlite else "postgresql",
            "task_executor": "in-process",
        }

    # WebSocket: global notifications
    @app.websocket("/ws/notifications")
    async def ws_notifications(websocket: WebSocket):
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
    async def ws_run_output(websocket: WebSocket, run_id: int):
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
