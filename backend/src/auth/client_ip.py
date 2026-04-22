"""Proxy-aware client IP extraction (deferred security item — hardens Story 2-8).

`request.client.host` reports only the peer-socket IP. Behind nginx / ALB
/ any trusted reverse proxy that terminates TLS, every user shares the
proxy's IP — which means:

  - Per-IP rate limits (SSO failure window, Story 2-8) lock out the entire
    tenant as soon as one attacker triggers the threshold.
  - Audit rows record the proxy IP, not the actual client, making
    forensics useless.

`get_client_ip(request)` reads the leftmost trusted entry from
`X-Forwarded-For` when the immediate peer is in the configurable trusted-
proxy allowlist (ROBOSCOPE_TRUSTED_PROXIES=comma-separated CIDRs, default
empty = never trust XFF). If the peer is NOT in the allowlist, we ignore
XFF entirely — a hostile direct client cannot spoof the client IP.

Rationale for the leftmost-trusted-after-proxies algorithm:
  - XFF values are appended by each hop; leftmost is the original client.
  - But a client can send their own XFF value before hitting the proxy;
    only trust the proxy's contribution.
  - Walk from rightmost (proxy closest to us) backwards while IPs are in
    the trusted set; the first non-trusted entry (or the leftmost entry
    if all are trusted) is the real client.
"""

from __future__ import annotations

import ipaddress
import os

from fastapi import Request

_TRUSTED_PROXIES_ENV = "ROBOSCOPE_TRUSTED_PROXIES"


def _parse_cidrs(raw: str) -> list[ipaddress.IPv4Network | ipaddress.IPv6Network]:
    nets: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            nets.append(ipaddress.ip_network(part, strict=False))
        except ValueError:
            continue
    return nets


def _trusted_proxies() -> list[ipaddress.IPv4Network | ipaddress.IPv6Network]:
    return _parse_cidrs(os.environ.get(_TRUSTED_PROXIES_ENV, ""))


def _is_trusted(ip_str: str, nets: list) -> bool:
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return False
    return any(ip in n for n in nets)


def get_client_ip(request: Request) -> str | None:
    """Return the best-guess real client IP, honouring trusted proxies.

    Fallback (no trusted proxy configured OR peer not in trusted set):
    returns `request.client.host`. This matches the pre-Phase-4 behavior
    so deployments without a reverse proxy see no change.
    """
    peer = request.client.host if request.client else None
    nets = _trusted_proxies()

    if not nets or peer is None or not _is_trusted(peer, nets):
        return peer

    xff = request.headers.get("x-forwarded-for", "")
    if not xff:
        return peer

    # Walk right-to-left past trusted proxies.
    entries = [e.strip() for e in xff.split(",") if e.strip()]
    if not entries:
        return peer

    for entry in reversed(entries):
        if _is_trusted(entry, nets):
            continue
        return entry

    # All entries were trusted — the leftmost IS the original client.
    return entries[0]
