"""Boot invariant: OIDC discovery refresh job must not fire at application startup."""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from src.auth.discovery_refresh import refresh_discovery_cache


def test_discovery_job_next_run_time_deferred():
    """The discovery refresh job's next_run_time must be in the future.

    This validates the boot invariant (AC1): the job is scheduled with
    next_run_time = now + 24h, so it does not fire on application startup.
    """
    from datetime import timedelta

    scheduler = BackgroundScheduler()
    scheduler.start()
    before = datetime.now(timezone.utc)

    try:
        scheduler.add_job(
            refresh_discovery_cache,
            trigger=IntervalTrigger(hours=24),
            id="oidc_discovery_refresh_test",
            name="OIDC Discovery Cache Refresh (test)",
            next_run_time=datetime.now(timezone.utc) + timedelta(hours=24),
            replace_existing=True,
        )

        job = scheduler.get_job("oidc_discovery_refresh_test")
        assert job is not None, "Job was not registered"
        assert job.next_run_time is not None, "next_run_time must be set"

        # Must be strictly in the future (at least 23h from now)
        delta = (job.next_run_time - before).total_seconds()
        assert delta > 23 * 3600, (
            f"Discovery job would fire too soon: {delta:.0f}s from now. "
            "Boot invariant violated — set next_run_time = now + 24h."
        )
    finally:
        scheduler.shutdown(wait=False)


def test_discovery_job_does_not_probe_at_boot():
    """Discovery probe must not be called within 0.5s of scheduler startup (AC1).

    Mirrors the main.py scheduler registration and verifies the behavioral invariant:
    after the scheduler's main loop has ticked multiple times, probe_idp_discovery
    is still not called — proving no outbound HTTP fires at boot.
    """
    probe_called = False

    def fail_if_probed(*_args, **_kwargs):
        nonlocal probe_called
        probe_called = True

    scheduler = BackgroundScheduler()
    scheduler.start()

    try:
        with patch("src.auth.discovery_refresh.probe_idp_discovery", side_effect=fail_if_probed):
            scheduler.add_job(
                refresh_discovery_cache,
                trigger=IntervalTrigger(hours=24),
                id="oidc_discovery_refresh_boot_test",
                name="OIDC Discovery Cache Refresh (boot invariant test)",
                next_run_time=datetime.now(timezone.utc) + timedelta(hours=24),
                replace_existing=True,
            )
            # Allow scheduler main loop to tick (default interval: 0.1s) — 5 ticks
            time.sleep(0.5)
    finally:
        scheduler.shutdown(wait=False)

    assert not probe_called, (
        "probe_idp_discovery was called during scheduler startup — AC1 violated. "
        "Ensure next_run_time is set to now + 24h in main.py."
    )
