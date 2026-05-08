"""OIDC discovery probe for Identity Provider dry-run validation."""

from __future__ import annotations

import json
import os
import ssl
import time
from datetime import datetime, timezone
from typing import Literal

import httpx
from sqlalchemy.orm import Session

from src.auth.models import IdentityProvider
from src.auth.schemas import DryRunCheckRow, DryRunProbeResponse

DISCOVERY_CACHE_TTL_HOURS = 24

_REQUIRED_DISCOVERY_KEYS = {
    "authorization_endpoint",
    "token_endpoint",
    "jwks_uri",
}

# AC2: total probe must complete within 10s. Two network phases run
# sequentially, so cap each at 4s to leave headroom for JSON parse + DB I/O.
_TIMEOUT_SECONDS = 4.0
_PHASE_TIMEOUT = httpx.Timeout(_TIMEOUT_SECONDS, connect=_TIMEOUT_SECONDS)

# Cap response bodies at 1 MB — real OIDC discovery docs and JWKS are <10 KB.
_MAX_RESPONSE_SIZE = 1_000_000

# HTTPS-only unless operator opts in via env flag (for internal/test IdPs).
# When True: http:// issuer URLs are accepted and _TLS_CONTEXT is not applied.
# Certificate verification is NOT disabled — an HTTPS IdP with a self-signed cert
# will still fail. Operators needing self-signed HTTPS should add the CA to the
# system trust store rather than relying on this flag.
_ALLOW_INSECURE_IDP = (
    os.getenv("ALLOW_INSECURE_IDP", "false").lower() == "true"
)

# NFR13: outbound IdP calls negotiate TLS 1.2 or newer; older versions fail at the client.
_TLS_CONTEXT = ssl.create_default_context()
_TLS_CONTEXT.minimum_version = ssl.TLSVersion.TLSv1_2


def _validate_https(url: str, target: str) -> str | None:
    """Return failure detail if url is http:// and insecure IdPs disabled."""
    if _ALLOW_INSECURE_IDP:
        return None
    if url.lower().startswith("http://"):
        return (
            f"{target} must use https:// "
            f"(set ALLOW_INSECURE_IDP=true to bypass)"
        )
    return None


def _fetch_json_object(
    url: str,
) -> tuple[int, dict | None, str | None]:
    """Fetch `url` and return (status_code, parsed_object, error_detail).

    - (status, {...}, None)  on 200 + valid JSON object
    - (status, None, err)    on 200 + non-JSON / non-object / oversize body
    - (status, None, None)   on non-200 (caller emits status-specific detail)

    Raises httpx.TimeoutException or httpx.HTTPError on network failure.
    """
    if _ALLOW_INSECURE_IDP:
        client_ctx = httpx.Client(timeout=_PHASE_TIMEOUT)
    else:
        client_ctx = httpx.Client(timeout=_PHASE_TIMEOUT, verify=_TLS_CONTEXT)
    with client_ctx as client:
        resp = client.get(url)
    if len(resp.content) > _MAX_RESPONSE_SIZE:
        return resp.status_code, None, (
            f"Response body exceeded {_MAX_RESPONSE_SIZE} bytes"
        )
    if resp.status_code != 200:
        return resp.status_code, None, None
    try:
        parsed = resp.json()
    except (json.JSONDecodeError, ValueError) as exc:
        return resp.status_code, None, f"Invalid JSON response: {exc}"
    if not isinstance(parsed, dict):
        return resp.status_code, None, "Response was not a JSON object"
    return resp.status_code, parsed, None


def probe_idp_discovery(
    db: Session, idp: IdentityProvider
) -> DryRunProbeResponse:
    """Probe an IdP's OIDC discovery and JWKS endpoints.

    Returns a structured report with three check rows:
    issuer_reachable, discovery_valid, jwks_fetched.
    Updates the IdP's dry-run status and discovery cache fields.
    """
    checks: list[DryRunCheckRow] = []
    start = time.monotonic()
    discovery_doc: dict | None = None

    # Phase 1: Fetch discovery document
    https_err = _validate_https(idp.issuer_url, "issuer_url")
    if https_err is not None:
        checks.append(DryRunCheckRow(
            check_name="issuer_reachable",
            status="failed",
            detail=https_err,
        ))
    else:
        discovery_url = (
            f"{idp.issuer_url.rstrip('/')}"
            "/.well-known/openid-configuration"
        )
        try:
            status, doc, err = _fetch_json_object(discovery_url)
            if err is not None:
                checks.append(DryRunCheckRow(
                    check_name="issuer_reachable",
                    status="failed",
                    detail=err,
                ))
            elif status != 200:
                checks.append(DryRunCheckRow(
                    check_name="issuer_reachable",
                    status="failed",
                    detail=f"Discovery endpoint returned HTTP {status}",
                ))
            else:
                discovery_doc = doc
                checks.append(DryRunCheckRow(
                    check_name="issuer_reachable",
                    status="passed",
                    detail="Discovery document fetched successfully",
                ))
        except httpx.TimeoutException:
            checks.append(DryRunCheckRow(
                check_name="issuer_reachable",
                status="failed",
                detail=(
                    f"timeout:discovery — {idp.issuer_url} did not"
                    f" respond within {_TIMEOUT_SECONDS:.0f}s"
                ),
            ))
        except httpx.HTTPError:
            checks.append(DryRunCheckRow(
                check_name="issuer_reachable",
                status="failed",
                detail=(
                    f"Cannot reach {idp.issuer_url}."
                    " Check firewall and egress rules."
                ),
            ))

    # Phase 2: Validate discovery document
    if discovery_doc is not None:
        missing = _REQUIRED_DISCOVERY_KEYS - discovery_doc.keys()
        if missing:
            checks.append(DryRunCheckRow(
                check_name="discovery_valid",
                status="failed",
                detail=(
                    f"Missing required keys: {', '.join(sorted(missing))}"
                ),
            ))
            discovery_doc = None
        else:
            checks.append(DryRunCheckRow(
                check_name="discovery_valid",
                status="passed",
                detail="Discovery document contains all required keys",
            ))
    else:
        checks.append(DryRunCheckRow(
            check_name="discovery_valid",
            status="failed",
            detail="Skipped — discovery document not available",
        ))

    # Phase 3: Fetch JWKS
    if discovery_doc is not None:
        jwks_uri = discovery_doc.get("jwks_uri")
        if not isinstance(jwks_uri, str) or not jwks_uri:
            checks.append(DryRunCheckRow(
                check_name="jwks_fetched",
                status="failed",
                detail="Discovery doc has invalid jwks_uri (not a string)",
            ))
        else:
            https_err = _validate_https(jwks_uri, "jwks_uri")
            if https_err is not None:
                checks.append(DryRunCheckRow(
                    check_name="jwks_fetched",
                    status="failed",
                    detail=https_err,
                ))
            else:
                try:
                    status, jwks_data, err = _fetch_json_object(jwks_uri)
                    if err is not None:
                        checks.append(DryRunCheckRow(
                            check_name="jwks_fetched",
                            status="failed",
                            detail=err,
                        ))
                    elif status != 200:
                        checks.append(DryRunCheckRow(
                            check_name="jwks_fetched",
                            status="failed",
                            detail=(
                                f"JWKS endpoint returned HTTP {status}"
                            ),
                        ))
                    elif jwks_data is None or not isinstance(jwks_data.get("keys"), list):
                        checks.append(DryRunCheckRow(
                            check_name="jwks_fetched",
                            status="warning",
                            detail=(
                                "JWKS response missing or invalid"
                                " 'keys' array"
                            ),
                        ))
                    else:
                        keys = jwks_data["keys"]
                        checks.append(DryRunCheckRow(
                            check_name="jwks_fetched",
                            status="passed",
                            detail=(
                                f"JWKS fetched with {len(keys)} key(s)"
                            ),
                        ))
                except httpx.TimeoutException:
                    checks.append(DryRunCheckRow(
                        check_name="jwks_fetched",
                        status="failed",
                        detail=(
                            f"timeout:jwks — {jwks_uri} did not respond"
                            f" within {_TIMEOUT_SECONDS:.0f}s"
                        ),
                    ))
                except httpx.HTTPError:
                    checks.append(DryRunCheckRow(
                        check_name="jwks_fetched",
                        status="failed",
                        detail=f"Cannot reach JWKS endpoint at {jwks_uri}",
                    ))
    else:
        checks.append(DryRunCheckRow(
            check_name="jwks_fetched",
            status="failed",
            detail="Skipped — discovery validation failed",
        ))

    elapsed_ms = int((time.monotonic() - start) * 1000)
    all_passed = all(c.status == "passed" for c in checks)
    overall: Literal["passed", "failed"] = "passed" if all_passed else "failed"

    # Update IdP dry-run tracking fields
    now = datetime.now(timezone.utc)
    idp.last_dry_run_at = now
    idp.last_dry_run_status = overall

    # Only cache discovery on success
    if overall == "passed" and discovery_doc is not None:
        idp.discovery_cache_json = json.dumps(discovery_doc)
        idp.discovery_cached_at = now

    db.flush()

    return DryRunProbeResponse(
        overall_status=overall,
        checks=checks,
        elapsed_ms=elapsed_ms,
    )


def get_or_fetch_discovery(
    db: Session, idp: IdentityProvider
) -> dict | None:
    """Return cached OIDC discovery doc if fresh; otherwise fetch and cache it.

    Returns the parsed discovery document dict, or None if fetch fails.
    This is the single call-point for login-flow code (Story 2-1) — no
    inline fetching in the OIDC initiation route.
    """
    cached_at = idp.discovery_cached_at
    if cached_at is not None and idp.discovery_cache_json:
        now_naive = datetime.now(timezone.utc).replace(tzinfo=None)
        cached_naive = cached_at.replace(tzinfo=None) if cached_at.tzinfo else cached_at
        if (now_naive - cached_naive).total_seconds() < DISCOVERY_CACHE_TTL_HOURS * 3600:
            try:
                return json.loads(idp.discovery_cache_json)
            except (json.JSONDecodeError, ValueError):
                pass  # fall through to re-fetch

    try:
        result = probe_idp_discovery(db, idp)
        # Flush (not commit) so callers own transaction boundaries. Committing
        # here used to destroy the outer SAVEPOINT in test fixtures and leak
        # partial state if the surrounding handler later rolled back. The
        # SSO initiation + callback handlers both db.commit() on success,
        # and failure paths rollback() — either way the cache row lands
        # durably without an inner commit.
        db.flush()
        if result.overall_status == "passed" and idp.discovery_cache_json:
            return json.loads(idp.discovery_cache_json)
        return None
    except Exception:
        import logging as _logging
        _logging.getLogger("roboscope.auth.oidc_discovery").warning(
            "get_or_fetch_discovery failed for IdP '%s' (id=%d)",
            idp.name,
            idp.id,
            exc_info=True,
        )
        return None
