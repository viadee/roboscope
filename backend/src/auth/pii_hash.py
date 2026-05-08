"""Deterministic email hashing for audit-log payloads.

Story (deferred from Phase 4 code review): `SSO_LOGIN_SUCCESS.detail`
was storing plaintext `email` values. Long retention + SIEM ingestion
multiplies the PII footprint. This module produces a stable, short
hash that:

  - Stays correlatable across audit rows from the same account (same
    input → same hash).
  - Doesn't round-trip back to the email without brute force of the
    email corpus (HMAC with the server's SECRET_KEY as the key).
  - Has a visible prefix (`sha256-hmac:`) so a SIEM operator sees
    immediately that the value is a hash, not a partial email.
  - Truncates to 16 hex chars (64 bits) for readable logs. Collision
    probability across a 10M-user corpus is ~1e-3 per row-pair; good
    enough for forensic correlation, not strong enough to substitute
    for the real email in investigations — the human follow-up still
    needs a join against the User table.

Use `hash_email(email)` from any audit-emitter that previously passed
`detail={"email": user.email, ...}` and drop the plaintext.
"""

from __future__ import annotations

import hashlib
import hmac

from src.config import settings

_HASH_PREFIX = "sha256-hmac:"
_TRUNCATE_CHARS = 16


def hash_email(email: str | None) -> str | None:
    """Return a stable prefix-tagged HMAC hash of the email, or None.

    None / empty input returns None so audit emitters can drop the
    field entirely when there's nothing to hash.
    """
    if not email:
        return None
    normalised = email.strip().lower()
    if not normalised:
        return None
    value = normalised.encode("utf-8")
    digest = hmac.new(
        settings.SECRET_KEY.encode("utf-8"),
        value,
        hashlib.sha256,
    ).hexdigest()
    return f"{_HASH_PREFIX}{digest[:_TRUNCATE_CHARS]}"


def is_email_hash(value: object) -> bool:
    """Return True when `value` looks like a `hash_email` result.

    Useful for tests that want to assert on the SHAPE of a detail
    field without pinning it to a specific email literal."""
    return (
        isinstance(value, str)
        and value.startswith(_HASH_PREFIX)
        and len(value) == len(_HASH_PREFIX) + _TRUNCATE_CHARS
    )
