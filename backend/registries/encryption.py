"""
Fernet-based symmetric encryption helpers for storing registry tokens.

The key is read from ``settings.FIELD_ENCRYPTION_KEY`` and must be a
URL-safe base64-encoded 32-byte key (``cryptography.fernet.Fernet.generate_key()``).
"""

from cryptography.fernet import Fernet
from django.conf import settings


def _get_fernet() -> Fernet:
    key = getattr(settings, "FIELD_ENCRYPTION_KEY", None)
    if not key:
        raise RuntimeError(
            "settings.FIELD_ENCRYPTION_KEY is not set. "
            "Generate one with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt_token(plain_text: str) -> str:
    """Encrypt *plain_text* and return the cipher-text as a UTF-8 string."""
    return _get_fernet().encrypt(plain_text.encode()).decode()


def decrypt_token(cipher_text: str) -> str:
    """Decrypt *cipher_text* and return the original plain-text."""
    return _get_fernet().decrypt(cipher_text.encode()).decode()
