"""APScheduler background job: refresh OIDC discovery cache for all enabled IdPs."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from src.auth.idp_service import list_identity_providers
from src.auth.oidc_discovery import DISCOVERY_CACHE_TTL_HOURS, probe_idp_discovery
from src.database import get_sync_session

logger = logging.getLogger("roboscope.auth.discovery_refresh")


def refresh_discovery_cache(force_all: bool = False) -> dict:
    """Refresh OIDC discovery cache for all enabled, stale IdPs.

    Skips disabled IdPs and (unless force_all=True) freshly-cached IdPs.
    Per-IdP failures are caught and tallied without aborting the batch.
    Returns {"status": "completed", "refreshed": N, "failed": M, "skipped": K}.
    """
    import src.auth.models  # noqa: F401 — required for FK resolution in background thread

    refreshed = 0
    failed = 0
    skipped = 0
    stale_cutoff = datetime.now(timezone.utc) - timedelta(hours=DISCOVERY_CACHE_TTL_HOURS)

    with get_sync_session() as session:
        idps = list_identity_providers(session)
        for idp in idps:
            if not idp.is_enabled:
                skipped += 1
                continue

            if not force_all:
                cached_at = idp.discovery_cached_at
                if cached_at is not None:
                    # SQLite stores naive datetimes — strip tz for comparison
                    cached_naive = cached_at.replace(tzinfo=None) if cached_at.tzinfo else cached_at
                    cutoff_naive = stale_cutoff.replace(tzinfo=None)
                    if cached_naive > cutoff_naive:
                        skipped += 1
                        continue

            try:
                probe_idp_discovery(session, idp)
                session.commit()
                refreshed += 1
                logger.info("Discovery cache refreshed for IdP '%s' (id=%d)", idp.name, idp.id)
            except Exception:
                session.rollback()
                logger.warning(
                    "Discovery cache refresh failed for IdP '%s' (id=%d)",
                    idp.name,
                    idp.id,
                    exc_info=True,
                )
                failed += 1

    logger.info(
        "Discovery cache refresh complete: refreshed=%d, failed=%d, skipped=%d",
        refreshed,
        failed,
        skipped,
    )
    return {"status": "completed", "refreshed": refreshed, "failed": failed, "skipped": skipped}
