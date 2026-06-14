"""Fernet encryption for API keys.

Uses the application SECRET_KEY as the basis for deriving a Fernet key.
"""

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from src.config import settings


class ApiKeyDecryptError(RuntimeError):
    """Raised when a stored provider API key can't be decrypted — almost
    always because SECRET_KEY changed since the key was saved (env rotation,
    DB restored from another instance). H3: gives a clear "re-enter the key"
    message instead of an opaque cryptography InvalidToken."""


def _derive_key() -> bytes:
    """Derive a 32-byte Fernet key from SECRET_KEY."""
    digest = hashlib.sha256(settings.SECRET_KEY.encode()).digest()
    return base64.urlsafe_b64encode(digest)


def encrypt_api_key(plaintext: str) -> str:
    """Encrypt an API key and return the ciphertext as a string."""
    f = Fernet(_derive_key())
    return f.encrypt(plaintext.encode()).decode()


def decrypt_api_key(ciphertext: str) -> str:
    """Decrypt an API key from stored ciphertext."""
    f = Fernet(_derive_key())
    try:
        return f.decrypt(ciphertext.encode()).decode()
    except InvalidToken as e:
        raise ApiKeyDecryptError(
            "Stored API key could not be decrypted — the SECRET_KEY has likely "
            "changed since the key was saved. Re-enter the provider's API key "
            "in Settings → AI."
        ) from e
