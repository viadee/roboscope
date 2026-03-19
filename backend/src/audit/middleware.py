"""Audit logging — automatic middleware + manual helper."""

import logging
import re
import threading

from fastapi import Request, Response
from sqlalchemy.orm import Session
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from src.audit.service import log_audit
from src.auth.models import User

logger = logging.getLogger("roboscope.audit")

# Methods that indicate write operations
_WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

# Paths to skip (health, static, websocket, auth refresh, audit itself)
_SKIP_PATTERNS = [
    re.compile(r"^/health"),
    re.compile(r"^/ws/"),
    re.compile(r"^/assets/"),
    re.compile(r"^/static/"),
    re.compile(r"^/api/v1/auth/refresh$"),
    re.compile(r"^/api/v1/audit"),
]

# Map path patterns to resource types
_RESOURCE_MAP = [
    (re.compile(r"/api/v1/runs"), "run"),
    (re.compile(r"/api/v1/schedules"), "schedule"),
    (re.compile(r"/api/v1/repos"), "repository"),
    (re.compile(r"/api/v1/environments"), "environment"),
    (re.compile(r"/api/v1/reports"), "report"),
    (re.compile(r"/api/v1/settings"), "setting"),
    (re.compile(r"/api/v1/auth/users"), "user"),
    (re.compile(r"/api/v1/auth/login"), "auth"),
    (re.compile(r"/api/v1/webhooks/tokens"), "api_token"),
    (re.compile(r"/api/v1/webhooks/hooks"), "webhook"),
    (re.compile(r"/api/v1/webhooks/git"), "git_webhook"),
    (re.compile(r"/api/v1/ai"), "ai"),
    (re.compile(r"/api/v1/stats"), "stats"),
    (re.compile(r"/api/v1/explorer"), "explorer"),
]


def _should_skip(path: str) -> bool:
    return any(p.search(path) for p in _SKIP_PATTERNS)


def _get_resource_type(path: str) -> str:
    for pattern, resource in _RESOURCE_MAP:
        if pattern.search(path):
            return resource
    return "unknown"


def _extract_resource_id(path: str) -> int | None:
    """Try to extract a numeric ID from the URL path."""
    parts = path.rstrip("/").split("/")
    for part in reversed(parts):
        if part.isdigit():
            return int(part)
    return None


def _method_to_action(method: str) -> str:
    return {
        "POST": "create",
        "PUT": "update",
        "PATCH": "update",
        "DELETE": "delete",
    }.get(method, method.lower())


def _log_audit_in_background(
    method: str, path: str, status_code: int, auth_header_value: str, ip: str | None,
) -> None:
    """Fire-and-forget audit log write in a daemon thread.

    This avoids blocking the async event loop with sync DB operations.
    """
    def _write():
        try:
            from src.database import SessionLocal

            user_id = None
            username = None
            if auth_header_value.startswith("Bearer "):
                token = auth_header_value[7:]
                try:
                    if token.startswith("rbs_"):
                        from src.webhooks.service import get_token_by_hash, verify_token
                        token_hash = verify_token(token)
                        with SessionLocal() as session:
                            api_token = get_token_by_hash(session, token_hash)
                            if api_token:
                                user_id = api_token.user_id
                                from src.auth.service import get_user_by_id
                                user = get_user_by_id(session, api_token.user_id)
                                username = user.username if user else None
                    else:
                        from src.auth.service import decode_token, get_user_by_id
                        payload = decode_token(token)
                        user_id = int(payload.get("sub", 0))
                        with SessionLocal() as session:
                            user = get_user_by_id(session, user_id)
                            username = user.username if user else None
                except Exception:
                    pass

            with SessionLocal() as session:
                log_audit(
                    session,
                    user_id=user_id,
                    username=username,
                    action=_method_to_action(method),
                    resource_type=_get_resource_type(path),
                    resource_id=_extract_resource_id(path),
                    detail={"method": method, "path": path, "status": status_code},
                    ip_address=ip,
                )
                session.commit()
        except Exception:
            logger.debug("Could not log audit entry", exc_info=True)

    t = threading.Thread(target=_write, daemon=True)
    t.start()


class AuditMiddleware(BaseHTTPMiddleware):
    """Automatically logs write operations (POST/PUT/PATCH/DELETE) to the audit log.

    DB writes happen in a daemon thread to avoid blocking the async event loop.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)

        # Only audit write methods that succeeded (2xx/3xx)
        if (
            request.method not in _WRITE_METHODS
            or response.status_code >= 400
            or _should_skip(request.url.path)
        ):
            return response

        # Fire-and-forget audit log in background thread
        _log_audit_in_background(
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            auth_header_value=request.headers.get("authorization", ""),
            ip=request.client.host if request.client else None,
        )

        return response


def audit(
    db: Session,
    user: User,
    request: Request,
    *,
    action: str,
    resource_type: str,
    resource_id: int | None = None,
    detail: dict | str | None = None,
) -> None:
    """Log an audit entry manually from a route handler.

    Use this for fine-grained audit logging beyond what the middleware captures.
    """
    ip = request.client.host if request.client else None
    log_audit(
        db,
        user_id=user.id,
        username=user.username,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        detail=detail,
        ip_address=ip,
    )
