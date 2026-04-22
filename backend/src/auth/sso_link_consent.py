"""Story 4-7: short-lived signed token carrying the SSO consent context.

When the callback encounters an existing local-account user (non-empty
hashed_password) logging in via SSO for the first time, we do NOT auto-
link. Instead we mint a signed token encoding everything the consent
endpoint needs to complete the flow and redirect the browser to the
frontend consent page.

The token is a JWT signed with the same SECRET_KEY used for session
JWTs. TTL is 5 minutes — long enough for a human to read + click,
short enough that a leaked URL is not a standing risk. Fields are NOT
encrypted: they carry no secrets, only identifiers.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt

from src.config import settings

_CONSENT_TTL_SECONDS = 300
_ALGORITHM = "HS256"
_TOKEN_TYPE = "sso_link_consent"


def encode_consent_token(
    *,
    user_id: int,
    idp_id: int,
    sub: str,
    email: str,
    groups: list[str],
    return_to: str,
) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "type": _TOKEN_TYPE,
        "user_id": user_id,
        "idp_id": idp_id,
        "sub": sub,
        "email": email,
        "groups": groups,
        "return_to": return_to,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=_CONSENT_TTL_SECONDS)).timestamp()),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=_ALGORITHM)


def decode_consent_token(token: str) -> dict:
    """Return the decoded claim bundle, or raise `ValueError` on any failure."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[_ALGORITHM])
    except jwt.InvalidTokenError as exc:
        raise ValueError(f"invalid consent token: {exc}") from exc
    if payload.get("type") != _TOKEN_TYPE:
        raise ValueError("not an sso_link_consent token")
    for field in ("user_id", "idp_id", "sub", "email", "groups", "return_to"):
        if field not in payload:
            raise ValueError(f"consent token missing field: {field}")
    return payload
