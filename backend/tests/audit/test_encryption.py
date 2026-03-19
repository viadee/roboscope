"""Tests for Fernet encryption and environment variable secrets."""

import pytest

from src.encryption import decrypt_value, encrypt_value, is_encrypted


class TestEncryption:
    """Tests for the shared encryption module."""

    def test_encrypt_decrypt_roundtrip(self):
        plaintext = "my-super-secret-api-key-123"
        encrypted = encrypt_value(plaintext)
        assert encrypted != plaintext
        decrypted = decrypt_value(encrypted)
        assert decrypted == plaintext

    def test_encrypted_value_is_detected(self):
        encrypted = encrypt_value("test-value")
        assert is_encrypted(encrypted) is True

    def test_plaintext_is_not_detected_as_encrypted(self):
        assert is_encrypted("plaintext-value") is False
        assert is_encrypted("") is False

    def test_different_values_produce_different_ciphertexts(self):
        enc1 = encrypt_value("value1")
        enc2 = encrypt_value("value2")
        assert enc1 != enc2

    def test_empty_string_roundtrip(self):
        encrypted = encrypt_value("")
        assert decrypt_value(encrypted) == ""

    def test_unicode_roundtrip(self):
        plaintext = "Passwörter & Schlüssel: 日本語"
        encrypted = encrypt_value(plaintext)
        assert decrypt_value(encrypted) == plaintext


class TestEnvironmentVariableEncryption:
    """Tests for secret variable encryption in environments service."""

    def test_secret_variable_is_encrypted_at_rest(self, db_session, admin_user):
        from src.environments.models import Environment, EnvironmentVariable
        from src.environments.service import add_variable
        from src.environments.schemas import EnvVarCreate

        env = Environment(
            name="test-env", python_version="3.12", created_by=admin_user.id,
        )
        db_session.add(env)
        db_session.flush()

        var = add_variable(db_session, env.id, EnvVarCreate(
            key="DB_PASSWORD", value="secret123", is_secret=True,
        ))

        # Value in DB should be encrypted, not plaintext
        assert var.value != "secret123"
        assert is_encrypted(var.value) is True

    def test_non_secret_variable_stored_plaintext(self, db_session, admin_user):
        from src.environments.models import Environment
        from src.environments.service import add_variable
        from src.environments.schemas import EnvVarCreate

        env = Environment(
            name="test-env2", python_version="3.12", created_by=admin_user.id,
        )
        db_session.add(env)
        db_session.flush()

        var = add_variable(db_session, env.id, EnvVarCreate(
            key="APP_NAME", value="roboscope", is_secret=False,
        ))

        assert var.value == "roboscope"

    def test_decrypt_variable_value(self, db_session, admin_user):
        from src.environments.models import Environment
        from src.environments.service import add_variable, decrypt_variable_value
        from src.environments.schemas import EnvVarCreate

        env = Environment(
            name="test-env3", python_version="3.12", created_by=admin_user.id,
        )
        db_session.add(env)
        db_session.flush()

        var = add_variable(db_session, env.id, EnvVarCreate(
            key="SECRET_KEY", value="my-secret", is_secret=True,
        ))

        # Decrypt should return original value
        assert decrypt_variable_value(var) == "my-secret"

    def test_decrypt_non_secret_returns_plaintext(self, db_session, admin_user):
        from src.environments.models import Environment
        from src.environments.service import add_variable, decrypt_variable_value
        from src.environments.schemas import EnvVarCreate

        env = Environment(
            name="test-env4", python_version="3.12", created_by=admin_user.id,
        )
        db_session.add(env)
        db_session.flush()

        var = add_variable(db_session, env.id, EnvVarCreate(
            key="DEBUG", value="true", is_secret=False,
        ))

        assert decrypt_variable_value(var) == "true"

    def test_decrypt_legacy_plaintext_secret(self, db_session, admin_user):
        """Existing plaintext secrets should still work (graceful degradation)."""
        from src.environments.models import Environment, EnvironmentVariable
        from src.environments.service import decrypt_variable_value

        env = Environment(
            name="test-env5", python_version="3.12", created_by=admin_user.id,
        )
        db_session.add(env)
        db_session.flush()

        # Simulate a legacy secret stored as plaintext
        var = EnvironmentVariable(
            environment_id=env.id, key="OLD_SECRET", value="legacy-plain", is_secret=True,
        )
        db_session.add(var)
        db_session.flush()

        # Should return the plaintext value without crashing
        assert decrypt_variable_value(var) == "legacy-plain"
