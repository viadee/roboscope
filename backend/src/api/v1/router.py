"""API v1 router — aggregates all domain routers."""

from fastapi import APIRouter

from src.ai.router import router as ai_router
from src.auth.router import router as auth_router
from src.environments.router import router as environments_router
from src.execution.router import router as execution_router
from src.explorer.router import router as explorer_router
from src.reports.router import router as reports_router
from src.repos.router import router as repos_router
from src.settings.router import router as settings_router
from src.stats.router import router as stats_router

api_router = APIRouter()

api_router.include_router(auth_router, prefix="/auth", tags=["Authentication"])
api_router.include_router(repos_router, prefix="/repos", tags=["Repositories"])
api_router.include_router(explorer_router, prefix="/explorer", tags=["Explorer"])
api_router.include_router(execution_router, tags=["Execution"])
api_router.include_router(environments_router, prefix="/environments", tags=["Environments"])
api_router.include_router(reports_router, prefix="/reports", tags=["Reports"])
api_router.include_router(stats_router, prefix="/stats", tags=["Statistics"])
api_router.include_router(settings_router, prefix="/settings", tags=["Settings"])
api_router.include_router(ai_router, prefix="/ai", tags=["AI Generation"])
