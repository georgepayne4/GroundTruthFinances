"""api/banking/encryption.py — Token encryption at rest (v6.0-02).

Uses Fernet symmetric encryption (from the cryptography library) to protect
OAuth access and refresh tokens stored in the database.

The encryption key is sourced from GROUNDTRUTH_TOKEN_KEY env var.
Generate one with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
"""

from __future__ import annotations

import logging
import os

from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)

_fernet: Fernet | None = None


def _get_fernet() -> Fernet:
    """Lazy-initialise the Fernet cipher from the environment key."""
    global _fernet
    if _fernet is None:
        key = os.environ.get("GROUNDTRUTH_TOKEN_KEY")
        if not key:
            raise RuntimeError(
                "GROUNDTRUTH_TOKEN_KEY environment variable is not set. "
                "Generate one with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
            )
        _fernet = Fernet(key.encode())
    return _fernet


def encrypt_token(plaintext: str) -> str:
    """Encrypt a token string. Returns a base64-encoded ciphertext."""
    return _get_fernet().encrypt(plaintext.encode()).decode()


def decrypt_token(ciphertext: str) -> str:
    """Decrypt a token string. Raises RuntimeError on failure."""
    try:
        return _get_fernet().decrypt(ciphertext.encode()).decode()
    except InvalidToken as exc:
        raise RuntimeError("Failed to decrypt token — key may have changed") from exc


def reset_fernet() -> None:
    """Reset the cached Fernet instance. Used in tests."""
    global _fernet
    _fernet = None
