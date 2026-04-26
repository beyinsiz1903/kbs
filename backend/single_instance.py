"""Single-instance guard for the agent.

Windows: uses a named mutex (win32event.CreateMutex). If another instance
holds the mutex, the second process exits cleanly with a non-zero code.

Non-Windows (Linux/macOS dev): uses an exclusive flock on
<DATA_DIR>/.agent.lock. The lock auto-releases if the process dies.

Usage:
    from single_instance import acquire_or_exit
    acquire_or_exit()  # call once at process startup
"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Optional

log = logging.getLogger("kbs-bridge.single_instance")

MUTEX_NAME = "Global\\SyroceKBSAgent.Mutex.v1"

_handle = None  # holds mutex (win) or fd (unix) — must outlive the process


def acquire_or_exit(data_dir: Optional[Path] = None) -> None:
    """Acquire the single-instance lock or exit(2) if another instance holds it."""
    if sys.platform == "win32":
        _acquire_windows()
    else:
        _acquire_unix(data_dir or Path(os.environ.get("DATA_DIR", "/tmp")))


def _acquire_windows() -> None:  # pragma: no cover - Windows-only
    global _handle
    try:
        import win32api  # type: ignore[import-not-found]
        import win32event  # type: ignore[import-not-found]
        import winerror  # type: ignore[import-not-found]
    except ImportError:
        log.warning("pywin32 yok, single-instance kilidi atlandi")
        return
    # CreateMutex always returns a handle. Duplicate-instance is signaled by
    # GetLastError()==ERROR_ALREADY_EXISTS — and that lives on win32api, not
    # win32event. Read it IMMEDIATELY after CreateMutex to avoid losing it.
    _handle = win32event.CreateMutex(None, False, MUTEX_NAME)
    last_err = win32api.GetLastError()
    if last_err == winerror.ERROR_ALREADY_EXISTS:
        log.error("Baska bir SyroceKBSAgent instance'i zaten calisiyor. Cikiliyor.")
        sys.exit(2)


def _acquire_unix(data_dir: Path) -> None:
    global _handle
    try:
        import fcntl
    except ImportError:
        return
    data_dir.mkdir(parents=True, exist_ok=True)
    lock_path = data_dir / ".agent.lock"
    fd = os.open(str(lock_path), os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        os.close(fd)
        log.error("Baska bir SyroceKBSAgent instance'i zaten calisiyor. Cikiliyor.")
        sys.exit(2)
    _handle = fd  # keep open for process lifetime
