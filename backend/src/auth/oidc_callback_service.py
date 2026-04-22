"""OIDC callback handler (Story 2-2).

Exchanges the authorization code for tokens, verifies the `id_token` signature
and claims, extracts identity claims, upserts the local `User`, synchronises
team memberships from the IdP-reported groups, and consumes the single-use
`OidcLoginAttempt`.

The raw `id_token` is never persisted or returned; it is discarded as soon as
claim extraction completes (NFR9).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

import httpx
from authlib.integrations.httpx_client import OAuth2Client
from authlib.jose import JsonWebKey, JsonWebToken
from authlib.jose.errors import JoseError
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from src.auth.constants import Role
from src.auth.models import (
    IdentityProvider,
    IdPGroupMapping,
    OidcLoginAttempt,
    User,
)
from src.auth.oidc_discovery import (
    _ALLOW_INSECURE_IDP,
    _TLS_CONTEXT,
    get_or_fetch_discovery,
)
from src.encryption import decrypt_value
from src.teams.models import TeamMember

logger = logging.getLogger("roboscope.auth.oidc_callback")

_CALLBACK_PATH = "/api/v1/auth/sso/callback"
_HTTP_TIMEOUT = httpx.Timeout(4.0, connect=4.0)

# Pin accepted id_token signature algorithms (P8). Reject HS*/none implicitly.
_ID_TOKEN_DECODER = JsonWebToken(
    ["RS256", "RS384", "RS512", "ES256", "ES384", "ES512"]
)
# Essential claims enforced at decode time (P9). Clock leeway handled via validate().
_ID_TOKEN_CLAIMS_OPTIONS = {
    "iss": {"essential": True},
    "aud": {"essential": True},
    "exp": {"essential": True},
    "iat": {"essential": True},
    "nonce": {"essential": True},
}
_CLAIMS_LEEWAY_SECONDS = 60


class SsoCallbackError(Exception):
    """Structured error raised at any failure branch of the callback flow."""

    def __init__(self, code: str, detail: dict | None = None) -> None:
        self.code = code
        self.detail = detail or {}
        super().__init__(code)


@dataclass
class SyncReport:
    added: list[int] = field(default_factory=list)
    removed: list[int] = field(default_factory=list)
    updated: list[int] = field(default_factory=list)


@dataclass
class CallbackResult:
    user: User
    return_to: str
    sync: SyncReport


def handle_sso_callback(
    db: Session, *, code: str, state: str, base_url: str
) -> CallbackResult:
    """Run the full post-IdP redirect flow. See module docstring for semantics."""
    attempt = db.query(OidcLoginAttempt).filter_by(state=state).first()
    if attempt is None:
        raise SsoCallbackError("state.unknown")

    now = datetime.now(timezone.utc)
    expires_at = attempt.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= now:
        raise SsoCallbackError("state.expired", {"idp_id": attempt.idp_id})

    # Capture attempt fields before the atomic state claim detaches the row.
    idp_id = attempt.idp_id
    nonce = attempt.nonce
    return_to = attempt.return_to or "/"
    pkce_verifier_enc = attempt.pkce_verifier

    # P14 — atomic state claim before any network I/O. A concurrent callback
    # for the same state sees no row after commit and gets state.unknown.
    db.delete(attempt)
    db.commit()

    idp = db.query(IdentityProvider).filter_by(id=idp_id).first()
    if idp is None or not idp.is_enabled:
        raise SsoCallbackError("idp.unavailable", {"idp_id": idp_id})

    discovery = get_or_fetch_discovery(db, idp)
    if discovery is None:
        raise SsoCallbackError("idp.unreachable", {"idp_id": idp.id})

    redirect_uri = f"{base_url.rstrip('/')}{_CALLBACK_PATH}"
    token_response = _exchange_code(
        pkce_verifier_enc, idp, discovery, code, redirect_uri
    )
    id_token_str = token_response.get("id_token")
    if not isinstance(id_token_str, str) or not id_token_str:
        raise SsoCallbackError("token.invalid", {"idp_id": idp.id, "reason": "no_id_token"})

    id_token_claims = _verify_id_token(
        id_token_str, idp, discovery, expected_nonce=nonce
    )
    del id_token_str  # NFR9 — id_token discarded after extraction

    claims = _extract_claims(id_token_claims, idp)
    user = _upsert_user(db, email=claims["email"], sub=claims["sub"])
    try:
        sync_report = _sync_team_memberships(db, user, idp.id, claims["groups"])
    except SQLAlchemyError as exc:
        # P3 — surface DB failures during group sync as a structured error so
        # the router can emit sso.login.failure with a recognizable code.
        raise SsoCallbackError(
            "sync.failed",
            {"idp_id": idp.id, "user_id": user.id, "message": str(exc)[:200]},
        ) from exc

    # Story 3-5 AC6 — cache the login-observed groups so the admin
    # `/available-groups` endpoint (Story 3-4) reflects groups seen at
    # login even before they're mapped.
    from src.auth.seen_groups import record_seen_groups

    try:
        record_seen_groups(db, idp.id, claims["groups"])
    except SQLAlchemyError:
        # Non-fatal — losing a cache update must not fail the login.
        logger.warning(
            "Recording seen groups failed for idp_id=%s; continuing", idp.id,
            exc_info=True,
        )

    return CallbackResult(user=user, return_to=return_to, sync=sync_report)


def _exchange_code(
    pkce_verifier_enc: str,
    idp: IdentityProvider,
    discovery: dict,
    code: str,
    redirect_uri: str,
) -> dict:
    token_endpoint = discovery.get("token_endpoint")
    if not isinstance(token_endpoint, str) or not token_endpoint:
        raise SsoCallbackError(
            "idp.unreachable", {"idp_id": idp.id, "reason": "no_token_endpoint"}
        )

    try:
        client_secret = decrypt_value(idp.client_secret_encrypted.decode())
    except Exception as exc:  # noqa: BLE001 — secret corruption is a hard stop
        raise SsoCallbackError(
            "idp.unavailable", {"idp_id": idp.id, "reason": "client_secret_decrypt_failed"}
        ) from exc

    try:
        code_verifier = decrypt_value(pkce_verifier_enc)
    except Exception as exc:  # noqa: BLE001
        raise SsoCallbackError(
            "token.invalid", {"idp_id": idp.id, "reason": "pkce_verifier_decrypt_failed"}
        ) from exc

    verify: object = True if _ALLOW_INSECURE_IDP else _TLS_CONTEXT
    try:
        with OAuth2Client(
            client_id=idp.client_id,
            client_secret=client_secret,
            token_endpoint_auth_method="client_secret_post",
            timeout=_HTTP_TIMEOUT,
            verify=verify,
        ) as client:
            token = client.fetch_token(
                token_endpoint,
                grant_type="authorization_code",
                code=code,
                redirect_uri=redirect_uri,
                code_verifier=code_verifier,
            )
    except httpx.TimeoutException as exc:
        raise SsoCallbackError(
            "idp.unreachable", {"idp_id": idp.id, "reason": "timeout"}
        ) from exc
    except httpx.HTTPStatusError as exc:
        # P2 — surface IdP HTTP status for SIEM correlation.
        raise SsoCallbackError(
            "idp.unreachable",
            {
                "idp_id": idp.id,
                "reason": "http_error",
                "http_status": exc.response.status_code,
                "message": str(exc)[:200],
            },
        ) from exc
    except httpx.HTTPError as exc:
        raise SsoCallbackError(
            "idp.unreachable",
            {"idp_id": idp.id, "reason": "http_error", "message": str(exc)[:200]},
        ) from exc
    except Exception as exc:  # authlib may raise its own OAuthError
        raise SsoCallbackError(
            "token.invalid",
            {"idp_id": idp.id, "reason": "token_exchange_failed", "message": str(exc)[:200]},
        ) from exc

    return dict(token)


def _verify_id_token(
    id_token_str: str,
    idp: IdentityProvider,
    discovery: dict,
    *,
    expected_nonce: str,
) -> dict:
    jwks_uri = discovery.get("jwks_uri")
    if not isinstance(jwks_uri, str) or not jwks_uri:
        raise SsoCallbackError("token.invalid", {"reason": "no_jwks_uri"})

    verify: object = True if _ALLOW_INSECURE_IDP else _TLS_CONTEXT
    try:
        with httpx.Client(timeout=_HTTP_TIMEOUT, verify=verify) as http:
            jwks_resp = http.get(jwks_uri)
            jwks_resp.raise_for_status()
            jwk_set = JsonWebKey.import_key_set(jwks_resp.json())
    except httpx.HTTPError as exc:
        raise SsoCallbackError(
            "token.invalid", {"reason": "jwks_fetch_failed"}
        ) from exc
    except ValueError as exc:  # import_key_set on malformed JSON
        raise SsoCallbackError("token.invalid", {"reason": "jwks_malformed"}) from exc

    try:
        claims = _ID_TOKEN_DECODER.decode(
            id_token_str, jwk_set, claims_options=_ID_TOKEN_CLAIMS_OPTIONS
        )
    except (JoseError, ValueError) as exc:
        # ValueError covers authlib's "Key not found" when kid is absent from JWKS.
        raise SsoCallbackError(
            "token.invalid", {"reason": "signature_invalid", "message": str(exc)[:200]}
        ) from exc

    try:
        claims.validate(leeway=_CLAIMS_LEEWAY_SECONDS)
    except JoseError as exc:
        raise SsoCallbackError(
            "token.invalid", {"reason": "claims_invalid", "message": str(exc)[:200]}
        ) from exc

    issuer_expected = idp.issuer_url.rstrip("/")
    issuer_actual = str(claims.get("iss", "")).rstrip("/")
    if issuer_actual != issuer_expected:
        raise SsoCallbackError("token.invalid", {"reason": "iss_mismatch"})

    aud = claims.get("aud")
    if isinstance(aud, str):
        aud_ok = aud == idp.client_id
    elif isinstance(aud, list):
        aud_ok = idp.client_id in aud
        # P10 — OIDC Core §3.1.3.7: when aud has multiple values, azp MUST be
        # present and equal to client_id.
        if aud_ok and len(aud) > 1 and claims.get("azp") != idp.client_id:
            raise SsoCallbackError("token.invalid", {"reason": "azp_mismatch"})
    else:
        aud_ok = False
    if not aud_ok:
        raise SsoCallbackError("token.invalid", {"reason": "aud_mismatch"})

    if claims.get("nonce") != expected_nonce:
        raise SsoCallbackError("nonce.mismatch", {"reason": "nonce_mismatch"})

    return dict(claims)


def _extract_claims(id_token_claims: dict, idp: IdentityProvider) -> dict:
    sub = id_token_claims.get("sub")
    if not isinstance(sub, str) or not sub:
        raise SsoCallbackError("claims.missing_sub")
    email = id_token_claims.get("email")
    if not isinstance(email, str) or not email:
        raise SsoCallbackError("claims.missing_email")
    # D1 — require email_verified=true. Narrow fix for account-takeover risk
    # via unverified-email IdPs; chosen over a (idp_id, sub) schema change.
    if id_token_claims.get("email_verified") is not True:
        raise SsoCallbackError("claims.email_unverified", {"email": email})
    group_claim = idp.group_claim_name or "groups"
    raw_groups = id_token_claims.get(group_claim)
    groups: list[str] = (
        [g for g in raw_groups if isinstance(g, str)]
        if isinstance(raw_groups, list)
        else []
    )
    return {"sub": sub, "email": email.strip().lower(), "groups": groups}


def _upsert_user(db: Session, *, email: str, sub: str) -> User:
    user = db.query(User).filter(User.email == email).first()
    if user is not None:
        # P6 — block SSO for deactivated accounts; do not silently reactivate.
        if not user.is_active:
            raise SsoCallbackError("user.disabled", {"user_id": user.id})
        user.last_login_at = datetime.now(timezone.utc)
        db.flush()
        return user

    new_user = User(
        email=email,
        username=email,
        hashed_password="",  # SSO-only — local login blocked by empty hash
        role=Role.VIEWER,
        is_active=True,
        last_login_at=datetime.now(timezone.utc),
    )
    db.add(new_user)
    try:
        db.flush()
    except IntegrityError as exc:
        # P15 — race on (email/username) unique constraint. Another concurrent
        # callback won; reuse that row if it matches, else surface a conflict.
        db.rollback()
        existing = db.query(User).filter(User.email == email).first()
        if existing is None:
            raise SsoCallbackError(
                "user.username_conflict", {"email": email}
            ) from exc
        if not existing.is_active:
            raise SsoCallbackError("user.disabled", {"user_id": existing.id}) from exc
        existing.last_login_at = datetime.now(timezone.utc)
        db.flush()
        return existing
    db.refresh(new_user)
    return new_user


def _sync_team_memberships(
    db: Session, user: User, idp_id: int, groups: list[str]
) -> SyncReport:
    mappings = (
        db.query(IdPGroupMapping).filter(IdPGroupMapping.idp_id == idp_id).all()
    )
    expected: dict[int, str] = {}
    for m in mappings:
        if m.group_claim_value in groups:
            expected[m.team_id] = m.role

    current_rows = (
        db.query(TeamMember)
        .filter(TeamMember.user_id == user.id, TeamMember.source == "idp_group_sync")
        .all()
    )
    current: dict[int, TeamMember] = {r.team_id: r for r in current_rows}

    report = SyncReport()
    for team_id, role in expected.items():
        existing = current.get(team_id)
        if existing is not None:
            if existing.role != role:
                existing.role = role
                report.updated.append(team_id)
            continue
        # P7 — don't duplicate any existing (team, user) row regardless of
        # source. Catches manual grants and any admin-flipped source values
        # to avoid tripping the (team_id, user_id) unique constraint.
        existing_any = (
            db.query(TeamMember)
            .filter(
                TeamMember.team_id == team_id,
                TeamMember.user_id == user.id,
            )
            .first()
        )
        if existing_any is None:
            db.add(
                TeamMember(
                    team_id=team_id,
                    user_id=user.id,
                    role=role,
                    source="idp_group_sync",
                )
            )
            report.added.append(team_id)

    for team_id, row in current.items():
        if team_id not in expected:
            db.delete(row)
            report.removed.append(team_id)

    db.flush()
    return report
