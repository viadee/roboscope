"""Unit tests for return_to URL validation (NFR7 open-redirect defense)."""

from __future__ import annotations

import pytest

from src.auth.return_to import is_valid_return_to, validate_return_to

BASE = "http://localhost:8000"
BASE_HTTPS = "https://app.example.com"


# ---------------------------------------------------------------------------
# Valid cases
# ---------------------------------------------------------------------------


def test_relative_path_is_valid():
    assert is_valid_return_to("/dashboard", BASE) is True


def test_relative_root_is_valid():
    assert is_valid_return_to("/", BASE) is True


def test_relative_with_query_string_is_valid():
    assert is_valid_return_to("/dashboard?id=42&tab=runs", BASE) is True


def test_relative_with_fragment_is_valid():
    assert is_valid_return_to("/reports#section-1", BASE) is True


def test_absolute_same_origin_is_valid():
    assert is_valid_return_to("http://localhost:8000/foo?bar=1", BASE) is True


def test_absolute_same_origin_https_is_valid():
    assert is_valid_return_to("https://app.example.com/foo", BASE_HTTPS) is True


def test_absolute_same_origin_default_port_is_valid():
    # http + :80 implicit == http explicit
    assert is_valid_return_to("http://localhost/foo", "http://localhost:80") is True


def test_absolute_same_origin_https_default_port_is_valid():
    assert is_valid_return_to("https://app.example.com/foo", "https://app.example.com:443") is True


# ---------------------------------------------------------------------------
# Invalid cases
# ---------------------------------------------------------------------------


def test_external_domain_is_rejected():
    assert is_valid_return_to("https://evil.com/", BASE_HTTPS) is False


def test_protocol_relative_is_rejected():
    # //evil.com/ is not a relative path — it's an external URL
    assert is_valid_return_to("//evil.com/steal", BASE) is False


def test_scheme_mismatch_is_rejected():
    # https target but http base → reject
    assert is_valid_return_to("https://localhost:8000/foo", BASE) is False


def test_port_mismatch_is_rejected():
    assert is_valid_return_to("http://localhost:9000/foo", BASE) is False


def test_hostname_mismatch_is_rejected():
    assert is_valid_return_to("http://other-host:8000/foo", BASE) is False


def test_javascript_scheme_is_rejected():
    assert is_valid_return_to("javascript:alert(1)", BASE) is False


def test_data_url_is_rejected():
    assert is_valid_return_to("data:text/html,<script>alert(1)</script>", BASE) is False


# ---------------------------------------------------------------------------
# validate_return_to fallback behavior
# ---------------------------------------------------------------------------


def test_none_returns_default_slash():
    assert validate_return_to(None, BASE) == "/"


def test_empty_string_returns_default_slash():
    assert validate_return_to("", BASE) == "/"


def test_invalid_returns_default_slash():
    assert validate_return_to("https://evil.com", BASE_HTTPS) == "/"


def test_valid_is_returned_as_is():
    assert validate_return_to("/dashboard", BASE) == "/dashboard"


def test_valid_absolute_is_returned_as_is():
    assert validate_return_to("http://localhost:8000/x", BASE) == "http://localhost:8000/x"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad_input",
    [
        "///evil.com",          # triple-slash — still protocol-relative-ish, external
        "http://",              # no host
        "://foo.com",           # no scheme
    ],
)
def test_malformed_urls_are_rejected(bad_input: str):
    assert is_valid_return_to(bad_input, BASE) is False


def test_none_is_not_invalid():
    # Empty return_to is not an error — caller resolves to "/"
    assert is_valid_return_to(None, BASE) is True
    assert is_valid_return_to("", BASE) is True


# ---------------------------------------------------------------------------
# Userinfo (@) component — Python urlparse correctly rejects these
# ---------------------------------------------------------------------------


def test_userinfo_at_evil_host_is_rejected():
    # urlparse("http://localhost:8000@evil.com/").hostname == "evil.com" → rejected
    assert is_valid_return_to("http://localhost:8000@evil.com/foo", BASE) is False


def test_userinfo_at_own_host_is_accepted():
    # urlparse("http://attacker@localhost:8000/").hostname == "localhost" → accepted
    # The userinfo component is irrelevant to origin safety; hostname + port match.
    assert is_valid_return_to("http://attacker@localhost:8000/foo", BASE) is True


# ---------------------------------------------------------------------------
# Length cap (aligned with DB column size on OidcLoginAttempt.return_to)
# ---------------------------------------------------------------------------


def test_oversize_return_to_is_rejected():
    # Longer than MAX_RETURN_TO_LENGTH must be rejected even if otherwise valid.
    long_path = "/" + ("a" * 500)
    assert is_valid_return_to(long_path, BASE) is False


def test_validate_oversize_falls_back_to_default():
    assert validate_return_to("/" + ("a" * 500), BASE) == "/"
