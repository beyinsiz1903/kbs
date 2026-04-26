"""Shared test setup: makes `backend/` importable and isolates test data dirs."""
import os
import sys
import tempfile
from pathlib import Path

import pytest
from cryptography.fernet import Fernet

# Make `backend/` importable as top-level (server.py does `from session import ...`)
_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT / "backend"))


@pytest.fixture(autouse=True)
def _isolated_data_dir(monkeypatch):
    """Each test gets its own DATA_DIR + Fernet key; module-level state cleared."""
    with tempfile.TemporaryDirectory() as tmp:
        monkeypatch.setenv("DATA_DIR", tmp)
        monkeypatch.setenv("SESSION_ENCRYPTION_KEY", Fernet.generate_key().decode())
        monkeypatch.setenv("KBS_MODE", "simulation")

        # Reload session/worker so they pick up the new DATA_DIR
        for modname in ("session", "worker"):
            if modname in sys.modules:
                del sys.modules[modname]

        # Reset worker singleton state
        import worker as _worker
        _worker._state = None
        _worker._task = None
        _worker._stop_event = None
        _worker._poll_now_event = None

        yield Path(tmp)
