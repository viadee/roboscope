"""OIDC Authorization Code Flow with PKCE (Story 2-1)."""

from __future__ import annotations

import base64
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from src.auth.models import IdentityProvider, OidcLoginAttempt
from src.auth.oidc_discovery import get_or_fetch_discovery
from src.encryption import encrypt_value

_ATTEMPT_TTL_MINUTES = 10


def _unreachable(name: str, detail_suffix: str = "") -> HTTPException:
    msg = f"Identity provider '{name}' is not reachable."
    if detail_suffix:
        msg = f"{msg} {detail_suffix}"
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail={
            "code": "idp.unreachable",
            "message": f"{msg} Check configuration and try again.",
            "localization_key": "auth.error.idpUnreachable",
        },
    )


def initiate_sso_login(
    db: Session,
    idp: IdentityProvider,
    safe_return_to: str,
    redirect_uri: str,
) -> str:
    """Build OIDC authorization URL and persist ephemeral login attempt row.

    Returns the authorization URL to redirect the browser to.
    Raises HTTP 503 if the IdP discovery doc is unavailable or malformed.
    """
    discovery = get_or_fetch_discovery(db, idp)
    if discovery is None:
        raise _unreachable(idp.name)

    auth_endpoint = discovery.get("authorization_endpoint")
    if not isinstance(auth_endpoint, str) or not auth_endpoint:
        raise _unreachable(idp.name, "Discovery doc missing authorization_endpoint.")

    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    pkce_verifier = secrets.token_urlsafe(32)
    digest = hashlib.sha256(pkce_verifier.encode("ascii")).digest()
    code_challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")

    # pkce_verifier is encrypted at rest: DB leak doesn't expose active verifiers
    # within their 10-min TTL window. Decrypted by Story 2-2 callback for token exchange.
    attempt = OidcLoginAttempt(
        state=state,
        nonce=nonce,
        pkce_verifier=encrypt_value(pkce_verifier),
        idp_id=idp.id,
        return_to=safe_return_to,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=_ATTEMPT_TTL_MINUTES),
    )
    db.add(attempt)
    db.flush()

    # Normalize scopes: collapse any whitespace (newlines, tabs) to single spaces
    # and ensure "openid" is present — silently skipping it produces a pure OAuth2
    # response (no id_token), which breaks Story 2-2's identity verification.
    raw_scopes = (idp.scopes or "").split()
    scope_set = set(raw_scopes) or {"openid", "profile", "email"}
    scope_set.add("openid")
    scope = " ".join(sorted(scope_set))

    params = urlencode(
        {
            "response_type": "code",
            "client_id": idp.client_id,
            "redirect_uri": redirect_uri,
            "scope": scope,
            "state": state,
            "nonce": nonce,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }
    )
    # Preserve any existing query string on the authorization endpoint
    # (e.g. Azure AD B2C vanity endpoints with `?p=B2C_1A_SIGNIN`).
    separator = "&" if "?" in auth_endpoint else "?"
    return f"{auth_endpoint}{separator}{params}"
