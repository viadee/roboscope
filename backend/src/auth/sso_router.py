"""SSO login endpoints: provider listing, OIDC flow initiation, and callback handler."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from src.audit.event_types import AuditEventType
from src.audit.service import log_event
from src.auth.client_ip import get_client_ip
from src.auth.idp_service import get_identity_provider
from src.auth.models import IdentityProvider
from src.auth.oidc_callback_service import SsoCallbackError, handle_sso_callback
from src.auth.oidc_service import initiate_sso_login
from src.auth.return_to import is_valid_return_to, validate_return_to
from src.auth.schemas import SsoProviderPublic
from src.auth.service import create_token_response
from src.auth.sso_rate_limit import (
    is_rate_limited,
    record_failure,
    reset_failures,
)
from src.database import get_db
from src.settings.service import get_setting_value

router = APIRouter()

_CALLBACK_PATH = "/api/v1/auth/sso/callback"
_SSO_ERROR_PATH = "/sso-error"
_COOKIE_MAX_AGE = 60  # seconds — frontend Story 2-3 migrates to localStorage synchronously

# Story W (deferred-work) — per-IP audit dedup window. Held-down attacker
# otherwise writes one AuditLog row per 429 request, which floods retention.
# A 60 s cooldown keeps forensics meaningful (still one row per burst) while
# bounding the write amplification to ~1 row/ip/minute.
_AUDIT_DEDUP_WINDOW_S = 60
_last_audit_emit: dict[str, float] = {}


def _clear_audit_dedup_state() -> None:
    """Test-only helper — conftest autouse fixture resets the per-process
    dedup dict between tests so one test does not starve the next."""
    _last_audit_emit.clear()


def _should_audit_429(client_ip: str) -> bool:
    import time
    now = time.monotonic()
    last = _last_audit_emit.get(client_ip)
    if last is not None and now - last < _AUDIT_DEDUP_WINDOW_S:
        return False
    _last_audit_emit[client_ip] = now
    # Bound the dict size — garbage-collect entries older than 2× window.
    if len(_last_audit_emit) > 1000:
        cutoff = now - 2 * _AUDIT_DEDUP_WINDOW_S
        for ip, t in list(_last_audit_emit.items()):
            if t < cutoff:
                _last_audit_emit.pop(ip, None)
    return True


def _rate_limit_response_if_blocked(
    db: Session, client_ip: str | None
) -> JSONResponse | None:
    """Return a 429 response if `client_ip` has exceeded the SSO-failure
    threshold in the current window; otherwise None.

    Audit emission is deduplicated per IP to a 60 s window so one
    held-down attacker cannot pump the audit log. Forensics still see
    at least one row per burst.
    """
    if client_ip is None:
        return None
    limited, retry_after = is_rate_limited(db, client_ip)
    if not limited:
        return None
    if _should_audit_429(client_ip):
        log_event(
            db,
            AuditEventType.SSO_LOGIN_RATE_LIMITED,
            detail={"ip": client_ip, "retry_after": retry_after},
            ip_address=client_ip,
        )
        db.commit()
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={
            "reason": "rate_limited",
            "retry_after": retry_after,
        },
        headers={"Retry-After": str(retry_after)},
    )


@router.get("/providers", response_model=list[SsoProviderPublic])
def list_sso_providers(db: Session = Depends(get_db)) -> list[IdentityProvider]:
    """Return all enabled identity providers (public fields only, no auth required)."""
    return db.query(IdentityProvider).filter(IdentityProvider.is_enabled.is_(True)).all()


@router.get("/public-settings")
def public_sso_settings(db: Session = Depends(get_db)) -> dict[str, object]:
    """Public (no-auth) subset of settings the unauthenticated login page needs.

    Intentionally minimal — only keys consumed by `LoginView` and the
    `SsoErrorView`. Never include secrets, internal endpoints, or
    anything that could aid reconnaissance.
    """
    hide_raw = get_setting_value(db, "hide_local_login_form", "false")
    admin_contact = get_setting_value(db, "admin_contact_email", "")
    return {
        "hide_local_login_form": hide_raw.lower() == "true",
        "admin_contact_email": admin_contact,
    }


@router.get("/{idp_id}/login")
def sso_login_initiate(
    idp_id: int,
    request: Request,
    return_to: str | None = Query(None),
    db: Session = Depends(get_db),
):
    """Validate return_to, build PKCE authorization URL, persist attempt, redirect."""
    base_url = str(request.base_url).rstrip("/")
    client_ip = get_client_ip(request)

    # Reject early if the source IP has exceeded the failure threshold.
    blocked = _rate_limit_response_if_blocked(db, client_ip)
    if blocked is not None:
        return blocked

    # IdP lookup FIRST so a malformed return_to cannot help an anon caller
    # distinguish "valid idp_id" from "invalid idp_id" (enumeration guard,
    # Phase-4 security review).
    idp = get_identity_provider(db, idp_id)
    if not idp or not idp.is_enabled:
        if client_ip:
            record_failure(db, client_ip)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Identity provider not found or not enabled",
        )

    if return_to and not is_valid_return_to(return_to, base_url):
        if client_ip:
            record_failure(db, client_ip)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "return_to.invalid",
                "message": "return_to must be a same-origin URL",
                "localization_key": "auth.error.returnToInvalid",
            },
        )

    safe_return_to = validate_return_to(return_to, base_url)
    redirect_uri = f"{base_url}{_CALLBACK_PATH}"

    authorization_url = initiate_sso_login(db, idp, safe_return_to, redirect_uri)
    db.commit()

    response = RedirectResponse(
        url=authorization_url, status_code=status.HTTP_302_FOUND
    )
    # state/nonce are in the URL — prevent caches or browser history from retaining them.
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    return response


@router.get("/callback")
def sso_callback(
    request: Request,
    code: str = Query(...),
    state: str = Query(...),
    db: Session = Depends(get_db),
):
    """Single shared OIDC callback (AR9). IdP identified via state lookup."""
    base_url = str(request.base_url).rstrip("/")
    client_ip = get_client_ip(request)

    blocked = _rate_limit_response_if_blocked(db, client_ip)
    if blocked is not None:
        return blocked

    try:
        result = handle_sso_callback(db, code=code, state=state, base_url=base_url)
    except SsoCallbackError as err:
        # P11 — discard any partial user/membership writes before auditing so
        # the failure event isn't committed alongside half-upserted state.
        db.rollback()
        # Story 4-7 — link-consent gate: not a failure, just a deferred flow.
        # Emit NO audit event and NO rate-limit penalty; redirect to the
        # frontend consent page with the short-lived signed consent token.
        if err.code == "user.link_consent_required":
            consent_token = err.detail.get("consent_token")
            if isinstance(consent_token, str):
                resp = RedirectResponse(
                    url=f"/sso-link-consent?token={quote(consent_token, safe='')}",
                    status_code=status.HTTP_302_FOUND,
                )
                resp.headers["Cache-Control"] = "no-store"
                return resp
            # Fall through to generic error if token missing — defensive.
        # Story 2-8 — increment the per-IP counter on any callback failure.
        if client_ip:
            record_failure(db, client_ip)
        # P1 — Constraint 6 mandates the failure key be `reason`. Sub-detail
        # reasons from the service layer are promoted to `sub_reason` to avoid
        # a spread collision clobbering the top-level value.
        failure_detail: dict[str, object] = {"reason": err.code}
        for key, value in err.detail.items():
            failure_detail["sub_reason" if key == "reason" else key] = value
        log_event(
            db,
            AuditEventType.SSO_LOGIN_FAILURE,
            detail=failure_detail,
            ip_address=client_ip,
        )
        db.commit()
        # P13 — defensive URL-encoding guards against future codes with
        # control characters that could bend the redirect target.
        resp = RedirectResponse(
            url=f"{_SSO_ERROR_PATH}?code={quote(err.code, safe='')}",
            status_code=status.HTTP_302_FOUND,
        )
        resp.headers["Cache-Control"] = "no-store"
        return resp

    tokens = create_token_response(result.user)

    log_event(
        db,
        AuditEventType.TEAM_MEMBER_SYNCED_FROM_IDP,
        user_id=result.user.id,
        detail={
            "added": result.sync.added,
            "removed": result.sync.removed,
            "updated": result.sync.updated,
        },
        ip_address=client_ip,
    )
    log_event(
        db,
        AuditEventType.SSO_LOGIN_SUCCESS,
        user_id=result.user.id,
        detail={
            "email": result.user.email,
            "return_to": result.return_to,
            "teams_synced": len(result.sync.added)
            + len(result.sync.updated)
            + len(result.sync.removed),
        },
        ip_address=client_ip,
    )
    db.commit()

    # Story 2-8 — a successful login clears all rate-limit counters for
    # the source IP so a user who legitimately re-authenticates after
    # some failures is not stuck at the threshold.
    if client_ip:
        reset_failures(db, client_ip)

    # P12 — defense-in-depth: re-validate the stored return_to against the
    # current base_url. Attempt rows survive base_url config changes and an
    # admin could edit the DB; treat the stored value as untrusted.
    safe_return_to = validate_return_to(result.return_to, base_url)
    resp = RedirectResponse(
        url=safe_return_to, status_code=status.HTTP_302_FOUND
    )
    resp.headers["Cache-Control"] = "no-store"
    # Non-HttpOnly by design: frontend (Story 2-3) reads these on landing,
    # migrates them to localStorage, then clears both cookies.
    resp.set_cookie(
        "roboscope_sso_access_token",
        tokens.access_token,
        max_age=_COOKIE_MAX_AGE,
        secure=True,
        samesite="lax",
        httponly=False,
        path="/",
    )
    resp.set_cookie(
        "roboscope_sso_refresh_token",
        tokens.refresh_token,
        max_age=_COOKIE_MAX_AGE,
        secure=True,
        samesite="lax",
        httponly=False,
        path="/",
    )
    return resp


# --- Story 4-7: link-consent endpoints ---


class SsoLinkConsentRequest(BaseModel):
    consent_token: str
    approve: bool


class SsoLinkConsentResponse(BaseModel):
    status: Literal["linked", "cancelled"]
    return_to: str
    access_token: str | None = None
    refresh_token: str | None = None


@router.post("/link-consent", response_model=SsoLinkConsentResponse)
def sso_link_consent(
    data: SsoLinkConsentRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Story 4-7: complete or cancel a pending SSO link.

    - approve=True: detach the user's local password (hashed_password=''),
      sync team memberships from the consent-token groups, emit
      `user.account_linked`, return session tokens (frontend persists +
      navigates to return_to).
    - approve=False: emit `user.account_link_cancelled`, return
      status=cancelled — the browser navigates to /login with a toast.
    """
    from src.audit.event_types import AuditEventType
    from src.audit.service import log_event
    from src.auth.models import User
    from src.auth.oidc_callback_service import _sync_team_memberships
    from src.auth.service import create_token_response
    from src.auth.sso_link_consent import decode_consent_token

    try:
        payload = decode_consent_token(data.consent_token)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "consent.invalid", "message": str(exc)},
        ) from exc

    user = db.get(User, payload["user_id"])
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Account is inactive"
        )
    if user.email != payload["email"]:
        # Defense in depth — token's email must still match. If email was
        # changed admin-side between mint and redeem, refuse.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Email no longer matches"
        )

    ip = get_client_ip(request)

    if not data.approve:
        log_event(
            db,
            AuditEventType.USER_ACCOUNT_LINK_CANCELLED,
            user_id=user.id,
            resource_id=user.id,
            detail={"email": user.email, "idp_id": payload["idp_id"]},
            ip_address=ip,
        )
        db.commit()
        return SsoLinkConsentResponse(status="cancelled", return_to="/login")

    # Approve: detach local password, sync teams, mint session.
    user.hashed_password = ""
    user.last_login_at = datetime.now(timezone.utc)
    db.flush()

    try:
        _sync_team_memberships(db, user, payload["idp_id"], payload.get("groups", []))
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "sync.failed", "message": str(exc)[:200]},
        ) from exc

    log_event(
        db,
        AuditEventType.USER_ACCOUNT_LINKED,
        user_id=user.id,
        resource_id=user.id,
        detail={"email": user.email, "idp_id": payload["idp_id"]},
        ip_address=ip,
    )
    db.commit()

    tokens = create_token_response(user)
    return SsoLinkConsentResponse(
        status="linked",
        return_to=payload.get("return_to", "/"),
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
    )
