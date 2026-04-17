"""Session storage with Fernet encryption.

Stores the active PMS session (token + user info + KBS config + PMS URL) in a
single encrypted file at /data/.session.enc. Only the holder of
SESSION_ENCRYPTION_KEY can read/write it.

Single-user model: this app runs on the hotel's reception PC; only one
session exists at a time.
"""
import json
import os
import time
from pathlib import Path
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

DATA_DIR = Path(os.environ.get("DATA_DIR", "/data"))
SESSION_FILE = DATA_DIR / ".session.enc"
SETTINGS_FILE = DATA_DIR / "settings.json"

INACTIVITY_LIMIT_SECONDS = 30 * 60  # 30 dakika

_fernet: Optional[Fernet] = None


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        key = os.environ.get("SESSION_ENCRYPTION_KEY")
        if not key:
            raise RuntimeError(
                "SESSION_ENCRYPTION_KEY ortam degiskeni eksik. "
                "Yeni anahtar uretmek icin: "
                "python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
            )
        _fernet = Fernet(key.encode() if isinstance(key, str) else key)
    return _fernet


def _ensure_data_dir():
    DATA_DIR.mkdir(parents=True, exist_ok=True)


# ---------- Session (encrypted) ----------

def save_session(data: dict) -> None:
    """Encrypt and persist the session dict."""
    _ensure_data_dir()
    data = dict(data)
    data["last_active"] = time.time()
    payload = json.dumps(data).encode()
    encrypted = _get_fernet().encrypt(payload)
    SESSION_FILE.write_bytes(encrypted)
    try:
        os.chmod(SESSION_FILE, 0o600)
    except OSError:
        pass


def load_session() -> Optional[dict]:
    """Load session if valid + not expired by inactivity. Returns None otherwise."""
    if not SESSION_FILE.exists():
        return None
    try:
        encrypted = SESSION_FILE.read_bytes()
        data = json.loads(_get_fernet().decrypt(encrypted).decode())
    except (InvalidToken, ValueError, OSError):
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
