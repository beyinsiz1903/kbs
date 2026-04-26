"""Tests for backend/secure_storage.py — Fernet fallback path (Linux dev).

The DPAPI path can only be tested on Windows; here we exercise the
non-Windows fallback.
"""
import os
import sys

import pytest
from cryptography.fernet import Fernet


@pytest.fixture(autouse=True)
def _backend_path():
    here = os.path.dirname(os.path.abspath(__file__))
    backend = os.path.join(os.path.dirname(here), "backend")
    if backend not in sys.path:
        sys.path.insert(0, backend)
    yield


@pytest.fixture
def _key(monkeypatch):
    monkeypatch.setenv("SESSION_ENCRYPTION_KEY", Fernet.generate_key().decode())
    import secure_storage
    secure_storage.reset_for_tests()
    yield
    secure_storage.reset_for_tests()


def test_roundtrip(_key):
    import secure_storage
    blob = secure_storage.encrypt(b"hello world")
    assert blob != b"hello world"
    assert secure_storage.decrypt(blob) == b"hello world"


def test_decrypt_with_wrong_key_fails(monkeypatch):
    import secure_storage
    monkeypatch.setenv("SESSION_ENCRYPTION_KEY", Fernet.generate_key().decode())
    secure_storage.reset_for_tests()
    blob = secure_storage.encrypt(b"data")
    # Rotate to a different key
    monkeypatch.setenv("SESSION_ENCRYPTION_KEY", Fernet.generate_key().decode())
    secure_storage.reset_for_tests()
    with pytest.raises(secure_storage.SecureStorageError):
        secure_storage.decrypt(blob)


def test_missing_key_raises(monkeypatch):
    import secure_storage
    monkeypatch.delenv("SESSION_ENCRYPTION_KEY", raising=False)
    secure_storage.reset_for_tests()
    with pytest.raises(secure_storage.SecureStorageError):
        secure_storage.encrypt(b"x")


def test_type_validation(_key):
    import secure_storage
    with pytest.raises(TypeError):
        secure_storage.encrypt("string-not-bytes")  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        secure_storage.decrypt("string-not-bytes")  # type: ignore[arg-type]


def test_backend_name_is_fernet_on_linux(_key):
    import secure_storage
    # On the Replit Linux runner this must always be 'fernet'
    assert secure_storage.backend_name() == "fernet"


def test_corrupted_ciphertext_fails(_key):
    import secure_storage
    with pytest.raises(secure_storage.SecureStorageError):
        secure_storage.decrypt(b"not-a-valid-fernet-token")
