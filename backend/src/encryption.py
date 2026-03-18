"""Fernet encryption for secrets (API keys, environment variables).

Uses the application SECRET_KEY as the basis for deriving a Fernet key.
Shared across modules that need encryption (AI API keys, environment secrets).
"""

import base64
import hashlib
import logging

from cryptography.fernet import Fernet, InvalidToken

from src.config import settings

logger = logging.getLogger("roboscope.encryption")


def _derive_key() -> bytes:
    """Derive a 32-byte Fernet key from SECRET_KEY."""
    digest = hashlib.sha256(settings.SECRET_KEY.encode()).digest()
    return base64.urlsafe_b64encode(digest)


def encrypt_value(plaintext: str) -> str:
    """Encrypt a string value and return the ciphertext."""
    f = Fernet(_derive_key())
    return f.encrypt(plaintext.encode()).decode()


def decrypt_value(ciphertext: str) -> str:
    """Decrypt a ciphertext string back to plaintext."""
    f = Fernet(_derive_key())
    return f.decrypt(ciphertext.encode()).decode()


def is_encrypted(value: str) -> bool:
    """Check if a value looks like a Fernet-encrypted token."""
    try:
        f = Fernet(_derive_key())
        f.decrypt(value.encode())
        return True
    except (InvalidToken, Exception):
        return False
