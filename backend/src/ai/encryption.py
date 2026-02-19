"""Fernet encryption for API keys.

Uses the application SECRET_KEY as the basis for deriving a Fernet key.
"""

import base64
import hashlib

from cryptography.fernet import Fernet

from src.config import settings


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
    return f.decrypt(ciphertext.encode()).decode()
