"""M3 regression: heal _should_retry must fire only on selector-resolution
failures — bare 'timeout'/'locator(' were too broad and healed non-selector
failures (risking a click on the wrong element)."""

from __future__ import annotations

from RoboScopeHeal.library import RoboScopeHeal


def _h() -> RoboScopeHeal:
    return RoboScopeHeal()


def test_retries_on_selector_failures() -> None:
    h = _h()
    assert h._should_retry(Exception("Element not found: css=.foo")) is True
    assert h._should_retry(Exception("locator resolved to 0 elements")) is True
    assert h._should_retry(Exception("strict mode violation: matched 3 elements")) is True
    assert h._should_retry(Exception("Timeout 5000ms exceeded waiting for selector")) is True


def test_does_not_retry_non_selector_failures() -> None:
    h = _h()
    # bare navigation/assertion timeout — not a stale selector
    assert h._should_retry(Exception("Timeout 10000ms exceeded.")) is False
    assert h._should_retry(AssertionError("Values 1 != 2")) is False
    assert h._should_retry(Exception("net::ERR_CONNECTION_REFUSED")) is False
