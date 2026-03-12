"""Tests for AI encryption module (Fernet-based API key encryption)."""

import base64
import hashlib
from unittest.mock import patch

import pytest
from cryptography.fernet import InvalidToken

from src.ai.encryption import _derive_key, decrypt_api_key, encrypt_api_key


class TestDeriveKey:
    def test_deterministic_key_derivation(self):
        """Same SECRET_KEY always produces the same derived key."""
        with patch("src.ai.encryption.settings") as mock_settings:
            mock_settings.SECRET_KEY = "test-secret-key"
            key1 = _derive_key()
            key2 = _derive_key()
        assert key1 == key2

    def test_key_is_valid_fernet_key(self):
        """Derived key must be 32 bytes, url-safe base64 encoded."""
        with patch("src.ai.encryption.settings") as mock_settings:
            mock_settings.SECRET_KEY = "any-secret"
            key = _derive_key()
        # Fernet keys are 32 bytes base64-encoded = 44 chars + padding
        decoded = base64.urlsafe_b64decode(key)
        assert len(decoded) == 32

    def test_different_secret_keys_produce_different_derived_keys(self):
        """Different SECRET_KEY values produce different Fernet keys."""
        with patch("src.ai.encryption.settings") as mock_settings:
            mock_settings.SECRET_KEY = "secret-one"
            key1 = _derive_key()

        with patch("src.ai.encryption.settings") as mock_settings:
            mock_settings.SECRET_KEY = "secret-two"
            key2 = _derive_key()

        assert key1 != key2

    def test_key_matches_manual_sha256(self):
        """Derived key matches manual SHA256 + base64 computation."""
        secret = "my-test-secret"
        with patch("src.ai.encryption.settings") as mock_settings:
            mock_settings.SECRET_KEY = secret
            key = _derive_key()

        expected = base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest())
        assert key == expected


class TestEncryptDecryptRoundTrip:
    def test_round_trip_simple_key(self):
        """Encrypting then decrypting returns the original plaintext."""
        with patch("src.ai.encryption.settings") as mock_settings:
            mock_settings.SECRET_KEY = "round-trip-secret"
            plaintext = "sk-abc123def456"
            ciphertext = encrypt_api_key(plaintext)
            result = decrypt_api_key(ciphertext)
        assert result == plaintext

    def test_round_trip_empty_string(self):
        """Empty string can be encrypted and decrypted."""
        with patch("src.ai.encryption.settings") as mock_settings:
            mock_settings.SECRET_KEY = "empty-string-secret"
            ciphertext = encrypt_api_key("")
            result = decrypt_api_key(ciphertext)
        assert result == ""

    def test_round_trip_unicode(self):
        """Unicode characters survive the encrypt/decrypt round-trip."""
        with patch("src.ai.encryption.settings") as mock_settings:
            mock_settings.SECRET_KEY = "unicode-secret"
            plaintext = "api-key-with-umlauts-\u00e4\u00f6\u00fc-\u00df"
            ciphertext = encrypt_api_key(plaintext)
            result = decrypt_api_key(ciphertext)
        assert result == plaintext

    def test_round_trip_long_key(self):
        """Long API keys are handled correctly."""
        with patch("src.ai.encryption.settings") as mock_settings:
            mock_settings.SECRET_KEY = "long-key-secret"
            plaintext = "x" * 10_000
            ciphertext = encrypt_api_key(plaintext)
            result = decrypt_api_key(ciphertext)
        assert result == plaintext


class TestEncryptApiKey:
    def test_ciphertext_differs_from_plaintext(self):
        """Ciphertext must not be the same as the plaintext."""
        with patch("src.ai.encryption.settings") as mock_settings:
            mock_settings.SECRET_KEY = "differ-secret"
            plaintext = "sk-test-key-12345"
            ciphertext = encrypt_api_key(plaintext)
        assert ciphertext != plaintext

    def test_encrypting_same_value_twice_produces_different_ciphertext(self):
        """Fernet uses random IV, so same plaintext -> different ciphertext."""
        with patch("src.ai.encryption.settings") as mock_settings:
            mock_settings.SECRET_KEY = "nonce-secret"
            ct1 = encrypt_api_key("same-key")
            ct2 = encrypt_api_key("same-key")
        assert ct1 != ct2

    def test_different_secret_key_produces_different_ciphertext(self):
        """Encrypting the same plaintext with different secrets yields different output."""
        plaintext = "sk-shared-plaintext"
        with patch("src.ai.encryption.settings") as mock_settings:
            mock_settings.SECRET_KEY = "secret-alpha"
            ct1 = encrypt_api_key(plaintext)

        with patch("src.ai.encryption.settings") as mock_settings:
            mock_settings.SECRET_KEY = "secret-beta"
            ct2 = encrypt_api_key(plaintext)

        # While technically they could collide, it's astronomically unlikely
        assert ct1 != ct2


class TestDecryptApiKey:
    def test_wrong_secret_key_fails(self):
        """Decrypting with a different SECRET_KEY raises InvalidToken."""
        with patch("src.ai.encryption.settings") as mock_settings:
            mock_settings.SECRET_KEY = "encrypt-secret"
            ciphertext = encrypt_api_key("my-api-key")

        with patch("src.ai.encryption.settings") as mock_settings:
            mock_settings.SECRET_KEY = "wrong-secret"
            with pytest.raises(InvalidToken):
                decrypt_api_key(ciphertext)

    def test_tampered_ciphertext_fails(self):
        """Modifying the ciphertext causes decryption to fail."""
        with patch("src.ai.encryption.settings") as mock_settings:
            mock_settings.SECRET_KEY = "tamper-secret"
            ciphertext = encrypt_api_key("my-api-key")

            # Flip a character in the middle of the ciphertext
            mid = len(ciphertext) // 2
            tampered = ciphertext[:mid] + ("A" if ciphertext[mid] != "A" else "B") + ciphertext[mid + 1:]

            with pytest.raises(Exception):  # InvalidToken or binascii.Error
                decrypt_api_key(tampered)

    def test_garbage_input_fails(self):
        """Completely invalid ciphertext raises an error."""
        with patch("src.ai.encryption.settings") as mock_settings:
            mock_settings.SECRET_KEY = "garbage-secret"
            with pytest.raises(Exception):
                decrypt_api_key("not-valid-ciphertext-at-all!!!")

    def test_truncated_ciphertext_fails(self):
        """Truncated ciphertext raises an error."""
        with patch("src.ai.encryption.settings") as mock_settings:
            mock_settings.SECRET_KEY = "truncate-secret"
            ciphertext = encrypt_api_key("my-api-key")

            with pytest.raises(Exception):
                decrypt_api_key(ciphertext[:10])
