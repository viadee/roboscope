"""Return-to URL validation for SSO login (NFR7 — open-redirect defense)."""

from __future__ import annotations

from urllib.parse import urlparse

_DEFAULT_REDIRECT = "/"

# Aligned with OidcLoginAttempt.return_to column (String(500)) with headroom.
MAX_RETURN_TO_LENGTH = 450


def _default_port(scheme: str) -> int:
    return 443 if scheme == "https" else 80


def is_valid_return_to(return_to: str | None, base_url: str) -> bool:
    """Return True if return_to is safe to redirect to after SSO login.

    - None/empty → True (caller resolves to "/")
    - Longer than MAX_RETURN_TO_LENGTH → False
    - Relative path starting with "/" (not "//") → True
    - Absolute URL matching base_url's scheme + hostname + effective port → True
    - Anything else (external, protocol-relative, scheme mismatch) → False
    """
    if not return_to:
        return True
    if len(return_to) > MAX_RETURN_TO_LENGTH:
        return False
    if return_to.startswith("/") and not return_to.startswith("//"):
        return True
    parsed = urlparse(return_to)
    base = urlparse(base_url.rstrip("/"))
    if not parsed.scheme or not parsed.hostname:
        return False
    return (
        parsed.scheme == base.scheme
        and parsed.hostname == base.hostname
        and (parsed.port or _default_port(parsed.scheme))
        == (base.port or _default_port(base.scheme))
    )


def validate_return_to(return_to: str | None, base_url: str) -> str:
    """Return a safe return_to URL; falls back to "/" when invalid or missing."""
    if not return_to:
        return _DEFAULT_REDIRECT
    return return_to if is_valid_return_to(return_to, base_url) else _DEFAULT_REDIRECT
