"""Cross-platform credential encryption.

On Windows (production target): uses DPAPI (Data Protection API) via
`win32crypt.CryptProtectData` / `CryptUnprotectData`. The ciphertext is bound
to the **current Windows user account** — even another user on the same
machine cannot decrypt it. No key management on our side.

On non-Windows (Linux/macOS dev): uses `cryptography.fernet` with a key
loaded from `SESSION_ENCRYPTION_KEY`. This is a DEVELOPMENT-ONLY fallback —
production deployments must run on Windows.

Usage:
    from secure_storage import encrypt, decrypt
    blob = encrypt(b"my-secret")
    plain = decrypt(blob)

Both functions raise `SecureStorageError` on failure (wrong user, missing
env var, corrupted blob, etc.).
"""
from __future__ import annotations

import os
import sys
from typing import Optional

IS_WINDOWS = sys.platform == "win32"


class SecureStorageError(RuntimeError):
    """Raised when encrypt/decrypt fails."""


# ---------- Backend selection ----------

def _backend_name() -> str:
    return "dpapi" if IS_WINDOWS else "fernet"


# ---------- Windows DPAPI ----------

# A constant byte string used as the "additional entropy" parameter in DPAPI.
# Adds a small amount of app-specific binding so a blob protected by another
# Windows process for the same user can't be decrypted by ours unless the
# entropy matches. It is NOT a secret.
_DPAPI_ENTROPY = b"SyroceKBSAgent.v1"


def _dpapi_encrypt(plaintext: bytes) -> bytes:
    try:
        import win32crypt  # type: ignore[import-not-found]
    except ImportError as e:  # pragma: no cover - Windows-only
        raise SecureStorageError(
            "win32crypt eksik. pywin32 yuklu mu? (pip install pywin32)"
        ) from e
    try:
        # Returns CRYPTPROTECT_LOCAL_MACHINE=False by default → user-bound.
        return win32crypt.CryptProtectData(
            plaintext, "SyroceKBSAgent", _DPAPI_ENTROPY, None, None, 0
        )
    except Exception as e:  # pragma: no cover - Windows-only
        raise SecureStorageError(f"DPAPI encrypt hatasi: {e}") from e


def _dpapi_decrypt(ciphertext: bytes) -> bytes:
    try:
        import win32crypt  # type: ignore[import-not-found]
    except ImportError as e:  # pragma: no cover - Windows-only
        raise SecureStorageError(
            "win32crypt eksik. pywin32 yuklu mu? (pip install pywin32)"
        ) from e
    try:
        # CryptUnprotectData returns (description, plaintext) tuple.
        _, plaintext = win32crypt.CryptUnprotectData(
            ciphertext, _DPAPI_ENTROPY, None, None, 0
        )
        return plaintext
    except Exception as e:  # pragma: no cover - Windows-only
        # Most likely cause: another Windows user trying to decrypt. We do NOT
        # reveal which.
        raise SecureStorageError(
            "DPAPI decrypt basarisiz: cipher bozuk veya farkli Windows kullanicisi"
        ) from e


# ---------- Fernet fallback (dev only) ----------

_fernet_cache = None


def _get_fernet():
    global _fernet_cache
    if _fernet_cache is not None:
        return _fernet_cache
    try:
        from cryptography.fernet import Fernet
    except ImportError as e:
        raise SecureStorageError("cryptography paketi gerekli (Fernet fallback)") from e
    key = os.environ.get("SESSION_ENCRYPTION_KEY")
    if not key:
        raise SecureStorageError(
            "SESSION_ENCRYPTION_KEY ortam degiskeni eksik. "
            "Yeni anahtar uretmek icin: "
            "python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )
    try:
        _fernet_cache = Fernet(key.encode() if isinstance(key, str) else key)
    except Exception as e:
        raise SecureStorageError(f"Gecersiz SESSION_ENCRYPTION_KEY: {e}") from e
    return _fernet_cache


def _fernet_encrypt(plaintext: bytes) -> bytes:
    return _get_fernet().encrypt(plaintext)


def _fernet_decrypt(ciphertext: bytes) -> bytes:
    try:
        from cryptography.fernet import InvalidToken
    except ImportError as e:
        raise SecureStorageError("cryptography paketi gerekli") from e
    try:
        return _get_fernet().decrypt(ciphertext)
    except InvalidToken as e:
        raise SecureStorageError("Fernet decrypt basarisiz: cipher bozuk veya yanlis anahtar") from e


# ---------- Public API ----------

def encrypt(plaintext: bytes) -> bytes:
    """Encrypt bytes using the platform's secure store."""
    if not isinstance(plaintext, (bytes, bytearray)):
        raise TypeError("plaintext bytes olmali")
    if IS_WINDOWS:
        return _dpapi_encrypt(bytes(plaintext))
    return _fernet_encrypt(bytes(plaintext))


def decrypt(ciphertext: bytes) -> bytes:
    """Decrypt bytes previously returned by encrypt()."""
    if not isinstance(ciphertext, (bytes, bytearray)):
        raise TypeError("ciphertext bytes olmali")
    if IS_WINDOWS:
        return _dpapi_decrypt(bytes(ciphertext))
    return _fernet_decrypt(bytes(ciphertext))


def reset_for_tests() -> None:
    """Force re-read of env vars / fernet key. ONLY for tests."""
    global _fernet_cache
    _fernet_cache = None


def backend_name() -> str:
    """Return 'dpapi' on Windows, 'fernet' elsewhere. Used for /api/health."""
    return _backend_name()
