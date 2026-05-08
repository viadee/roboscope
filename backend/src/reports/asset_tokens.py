"""HMAC-signed report-scoped asset access tokens.

Story SECURITY-3 — replaces the user's JWT in iframe asset URLs with
a purpose-built short-lived token. The token is:

  * **Stateless** — verified entirely from the signature; no DB
    lookup, no revocation table.
  * **Report-scoped** — `verify_asset_token(t, report_id)` only
    returns True for the report the token was minted for. A token
    that leaks gives access to *one* report's assets, not the
    whole instance.
  * **Short-lived** — default 1-hour TTL. Operators concerned about
    leaks can shorten this without code changes.
  * **Identity-free** — no user ID is encoded; auditing falls back
    to other surfaces (the `/html` request that minted the token
    *is* authenticated, and that login event is recorded).

Format: ``base64url(<report_id>:<expiry>.<hex_hmac>)``. The
embedded `:` separator is safe because both halves are integer
strings; the leading payload is reproduced verbatim during
verification, so we don't need a structured JSON wrapper.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import time

from src.config import settings


def _key() -> bytes:
    """Resolve the HMAC key. `settings.SECRET_KEY` is required at
    startup (main.py errors out if it's missing), so we fail loud
    here rather than silently falling back to an empty key.
    """
    sk = settings.SECRET_KEY or ""
    if not sk:
        raise RuntimeError("SECRET_KEY is not configured — cannot sign asset tokens")
    return sk.encode("utf-8")


def _b64url_encode(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode("ascii").rstrip("=")


def _b64url_decode(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode((s + pad).encode("ascii"))


# SHA-256 output is always 32 bytes — the suffix length is fixed,
# so we don't need a printable separator between payload and
# signature. The previous implementation used `.` as a separator
# and `decoded.rsplit(b".", 1)` to recover payload + sig. ASCII
# `0x2E` (period) is a valid byte in a random HMAC, so the sig
# itself contained one with ~12% probability (1 − (255/256)**32),
# at which point `rsplit` split at the wrong byte, the payload
# parse failed, and verify returned False — silently. Fixed-length
# slicing has no such collision class.
_SIG_LEN = hashlib.sha256().digest_size  # 32


def mint_asset_token(report_id: int, ttl_seconds: int = 3600) -> str:
    """Create a token that grants read access to report ``report_id``
    for the next ``ttl_seconds`` seconds.
    """
    expiry = int(time.time()) + ttl_seconds
    payload = f"{report_id}:{expiry}".encode("ascii")
    sig = hmac.new(_key(), payload, hashlib.sha256).digest()
    return _b64url_encode(payload + sig)


def verify_asset_token(token: str, report_id: int) -> bool:
    """Return True iff the token is well-formed, signed by us, not
    expired, and scoped to ``report_id``. Constant-time signature
    compare via `hmac.compare_digest`.
    """
    if not token:
        return False
    try:
        decoded = _b64url_decode(token)
    except (ValueError, binascii.Error):
        return False

    if len(decoded) <= _SIG_LEN:
        # Need at least one payload byte — `:` separator + at least
        # one digit per side — but the conservative lower bound is
        # "more than the signature itself".
        return False
    payload, sig = decoded[:-_SIG_LEN], decoded[-_SIG_LEN:]
    expected = hmac.new(_key(), payload, hashlib.sha256).digest()
    if not hmac.compare_digest(sig, expected):
        return False

    # Decode the payload `report_id:expiry`.
    try:
        rid_str, exp_str = payload.decode("ascii").split(":", 1)
        rid = int(rid_str)
        exp = int(exp_str)
    except (UnicodeDecodeError, ValueError):
        return False

    if rid != report_id:
        return False
    if exp < int(time.time()):
        return False
    return True
