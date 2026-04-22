"""Email-PII hashing for audit emission."""

from __future__ import annotations

from src.auth.pii_hash import hash_email, is_email_hash


class TestHashEmail:
    def test_shape(self) -> None:
        out = hash_email("alice@example.com")
        assert out is not None
        assert out.startswith("sha256-hmac:")
        assert len(out) == len("sha256-hmac:") + 16

    def test_deterministic(self) -> None:
        assert hash_email("alice@example.com") == hash_email("alice@example.com")

    def test_case_insensitive(self) -> None:
        assert hash_email("Alice@Example.com") == hash_email("alice@example.com")

    def test_whitespace_tolerant(self) -> None:
        assert hash_email("  alice@example.com  ") == hash_email("alice@example.com")

    def test_different_emails_yield_different_hashes(self) -> None:
        assert hash_email("a@b.c") != hash_email("x@y.z")

    def test_none_returns_none(self) -> None:
        assert hash_email(None) is None

    def test_empty_returns_none(self) -> None:
        assert hash_email("") is None
        assert hash_email("   ") is None


class TestIsEmailHash:
    def test_positive(self) -> None:
        assert is_email_hash(hash_email("a@b.c"))

    def test_plain_email_is_not_a_hash(self) -> None:
        assert not is_email_hash("alice@example.com")

    def test_wrong_prefix(self) -> None:
        assert not is_email_hash("sha256:abcdef1234567890")

    def test_wrong_length(self) -> None:
        assert not is_email_hash("sha256-hmac:short")

    def test_none_is_not_a_hash(self) -> None:
        assert not is_email_hash(None)
