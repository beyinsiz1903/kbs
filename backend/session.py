"""Session storage — encrypted via DPAPI on Windows, Fernet on Linux dev.

Stores the active PMS session (token + user info + KBS config + PMS URL) in a
single file at <DATA_DIR>/.session.enc. On Windows production the cipher is
bound to the Windows user account (DPAPI); on Linux dev a Fernet key from
SESSION_ENCRYPTION_KEY is used as a fallback.

Single-user model: this app runs on the hotel's reception PC; only one
session exists at a time.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Optional

from secure_storage import SecureStorageError, decrypt, encrypt

DATA_DIR = Path(os.environ.get("DATA_DIR", "/data"))
SESSION_FILE = DATA_DIR / ".session.enc"
SETTINGS_FILE = DATA_DIR / "settings.json"

INACTIVITY_LIMIT_SECONDS = 30 * 60  # 30 dakika


def _ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


# ---------- Session (encrypted) ----------

def save_session(data: dict) -> None:
    """Encrypt and persist the session dict."""
    _ensure_data_dir()
    data = dict(data)
    data["last_active"] = time.time()
    payload = json.dumps(data).encode()
    SESSION_FILE.write_bytes(encrypt(payload))
    try:
        os.chmod(SESSION_FILE, 0o600)
    except OSError:
        pass


def load_session() -> Optional[dict]:
    """Load session if valid + not expired by inactivity. Returns None otherwise."""
    if not SESSION_FILE.exists():
        return None
    try:
        ciphertext = SESSION_FILE.read_bytes()
        data = json.loads(decrypt(ciphertext).decode())
    except (SecureStorageError, ValueError, OSError):
        clear_session()
        return None

    last_active = data.get("last_active", 0)
    if time.time() - last_active > INACTIVITY_LIMIT_SECONDS:
        clear_session()
        return None

    return data


def touch_session() -> None:
    """Update last_active to now to slide the inactivity window."""
    data = load_session()
    if data is not None:
        save_session(data)


def clear_session() -> None:
    if SESSION_FILE.exists():
        try:
            SESSION_FILE.unlink()
        except OSError:
            pass


# ---------- Settings (plaintext, non-sensitive only) ----------
# KBS credentials are stored ENCRYPTED inside the session, not here.
# settings.json holds only the PMS URL so the login screen can prefill it.

def save_settings(settings: dict) -> None:
    _ensure_data_dir()
    SETTINGS_FILE.write_text(json.dumps(settings, indent=2))


def load_settings() -> dict:
    if not SETTINGS_FILE.exists():
        return {}
    try:
        return json.loads(SETTINGS_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        return {}
