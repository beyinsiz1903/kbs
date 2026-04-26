"""Windows Event Log writer (Application channel).

Used to surface dead-letter (failed-permanently) jobs to the hotel's IT
support who routinely check Event Viewer. On non-Windows or when pywin32 is
unavailable, every function is a no-op so dev/CI never breaks.

Event source: "SyroceKBSAgent". The source must be registered ONCE per
machine (admin rights). `register_source()` is idempotent and safely fails on
ImportError or PermissionError — we never crash startup over Event Log.
"""
from __future__ import annotations

import logging
import sys
from typing import Optional

log = logging.getLogger("kbs-bridge.eventlog")

EVENT_SOURCE = "SyroceKBSAgent"

# Event IDs are local to the source; we use a stable scheme so log queries
# can filter on a known ID. Values are arbitrary but should not change.
EID_DEAD_JOB = 1001
EID_REPLAY_FAIL = 1002
EID_KBS_REFUSED = 1003

IS_WINDOWS = sys.platform == "win32"


def _safe_import_eventlog():
    if not IS_WINDOWS:
        return None
    try:
        import win32evtlog  # type: ignore[import-not-found]
        import win32evtlogutil  # type: ignore[import-not-found]
        return win32evtlog, win32evtlogutil
    except ImportError:
        return None


def register_source() -> bool:
    """Register the event source. Idempotent. Returns True iff successful."""
    mods = _safe_import_eventlog()
    if mods is None:
        return False
    _, win32evtlogutil = mods
    try:
        # AddSourceToRegistry is idempotent — no-op if already present.
        win32evtlogutil.AddSourceToRegistry(
            appName=EVENT_SOURCE,
            msgDLL=None,
            eventLogType="Application",
        )
        return True
    except Exception as e:  # pragma: no cover - Windows-only
        log.warning("Event Log kaynak kaydi basarisiz (admin haklari?): %s", e)
        return False


def _write(level_const: int, event_id: int, message: str) -> None:
    mods = _safe_import_eventlog()
    if mods is None:
        return  # silent no-op off Windows
    win32evtlog, win32evtlogutil = mods
    try:
        win32evtlogutil.ReportEvent(
            EVENT_SOURCE,
            event_id,
            eventCategory=0,
            eventType=level_const,
            strings=[message],
            data=b"",
        )
    except Exception as e:  # pragma: no cover - Windows-only
        log.warning("Event Log yazma basarisiz: %s", e)


def warn_dead_job(job_id: str, error: Optional[str] = None) -> None:
    """Write a WARNING entry for a job that PMS marked dead."""
    msg = f"KBS islemi basarisiz - dead-letter. job_id={job_id}"
    if error:
        msg += f" hata={error[:200]}"
    mods = _safe_import_eventlog()
    if mods is None:
        return
    win32evtlog, _ = mods
    _write(win32evtlog.EVENTLOG_WARNING_TYPE, EID_DEAD_JOB, msg)


def warn_replay_failure(job_id: str, error: str) -> None:
    msg = f"Replay basarisiz, sonraki tur tekrar denenecek. job_id={job_id} hata={error[:200]}"
    mods = _safe_import_eventlog()
    if mods is None:
        return
    win32evtlog, _ = mods
    _write(win32evtlog.EVENTLOG_WARNING_TYPE, EID_REPLAY_FAIL, msg)


def info_kbs_refused(reason: str) -> None:
    msg = f"KBS gonderimi reddedildi: {reason[:300]}"
    mods = _safe_import_eventlog()
    if mods is None:
        return
    win32evtlog, _ = mods
    _write(win32evtlog.EVENTLOG_INFORMATION_TYPE, EID_KBS_REFUSED, msg)
