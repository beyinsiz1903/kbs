"""Append-only durable journal for worker events.

Each line is one JSON record (UTF-8). Used so:
  * the worker's actions can be audited offline,
  * Phase B (real EGM SOAP + Idempotency-Key) can reconstruct or de-dup
    in-flight submissions after a crash by replaying the tail.

Single file, line-delimited JSON, no external dependencies. Best-effort I/O —
journal failures must never break the worker loop, so disk errors are
swallowed (and logged at debug level by the caller if desired).
"""
from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Any


def _journal_file() -> Path:
    """Resolve at call time so tests can override DATA_DIR per-test."""
    data_dir = Path(os.environ.get("DATA_DIR", "/data"))
    return data_dir / "submissions.jsonl"


_lock = threading.Lock()


def append(event: str, **fields: Any) -> None:
    """Append one record to the journal. Never raises."""
    record: dict[str, Any] = {"ts": time.time(), "event": event}
    record.update(fields)
    line = json.dumps(record, ensure_ascii=False, default=str)
    path = _journal_file()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with _lock:
            with path.open("a", encoding="utf-8") as f:
                f.write(line + "\n")
    except OSError:
        # Journal is best-effort; never break the worker.
        pass


def tail(n: int = 50) -> list[dict]:
    """Return the last n records (most recent last). Best-effort."""
    path = _journal_file()
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8") as f:
            lines = f.readlines()
    except OSError:
        return []
    out: list[dict] = []
    for line in lines[-n:]:
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


# Pending → ack pairs used by the worker for crash-recovery replay:
#   pending_complete  ↔  complete_ack
#   pending_fail      ↔  fail_ack
_PENDING_TO_ACK: dict[str, str] = {
    "pending_complete": "complete_ack",
    "pending_fail": "fail_ack",
}


def find_unacked(scan_records: int = 2000) -> list[dict]:
    """Scan the tail of the journal and return pending events with no ack.

    Used at worker startup to replay PMS calls that crashed in-flight. PMS
    de-dupes via the Idempotency-Key header, so replaying is safe even if
    the original call actually succeeded but our process died before logging
    the ack.

    Returns the LAST pending entry per job_id (most recent intent wins).
    """
    records = tail(scan_records)
    pending: dict[str, dict] = {}
    for r in records:
        ev = r.get("event")
        jid = r.get("job_id")
        if not jid:
            continue
        if ev in _PENDING_TO_ACK:
            pending[jid] = r
            continue
        # If we see an ack, drop the matching pending intent (it succeeded).
        for pend_ev, ack_ev in _PENDING_TO_ACK.items():
            if ev == ack_ev:
                cur = pending.get(jid)
                if cur and cur.get("event") == pend_ev:
                    pending.pop(jid, None)
                break
    return list(pending.values())
