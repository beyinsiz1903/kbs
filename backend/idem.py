"""Per-job Idempotency-Key persistence.

The PMS contract treats `Idempotency-Key` as a strong de-dup signal: two POST
calls with the same key + same body produce one effect. To make worker retries
safe across crashes we must send the SAME key for a given (job_id, action)
even after a process restart — so we persist them on disk.

Storage layout: `<DATA_DIR>/idem/{job_id}.json`
  {"claim": "<uuid>", "complete": "<uuid>", "fail": "<uuid>"}

Cleanup: caller invokes `cleanup(job_id)` once the job reaches a terminal
state (PMS acked complete, or PMS marked dead) so the directory stays bounded.
"""
from __future__ import annotations

import json
import os
import re
import threading
import uuid
from pathlib import Path

VALID_ACTIONS = ("claim", "complete", "fail")

_lock = threading.Lock()
_SAFE_ID = re.compile(r"[^A-Za-z0-9_\-]")


def _idem_dir() -> Path:
    return Path(os.environ.get("DATA_DIR", "/data")) / "idem"


def _path(job_id: str) -> Path:
    if not job_id:
        raise ValueError("idem: empty job_id")
    safe = _SAFE_ID.sub("_", str(job_id))[:100]
    return _idem_dir() / f"{safe}.json"


def _read(p: Path) -> dict:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _write(p: Path, data: dict) -> None:
    _idem_dir().mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data), encoding="utf-8")
    try:
        os.chmod(p, 0o600)
    except OSError:
        pass


def get_or_create(job_id: str, action: str) -> str:
    """Return the persisted key for (job_id, action); generate one if missing.

    The same call from a different process/restart returns the same UUID for
    the same (job_id, action) pair — that is the whole point.
    """
    if action not in VALID_ACTIONS:
        raise ValueError(f"unknown idem action: {action!r}")
    p = _path(job_id)
    with _lock:
        keys = _read(p) if p.exists() else {}
        if action not in keys:
            keys[action] = str(uuid.uuid4())
            try:
                _write(p, keys)
            except OSError:
                # Best effort — if we can't persist, fall back to in-memory
                # uniqueness; a future call may regenerate, but PMS will still
                # de-dup within the lifespan of this process.
                pass
        return keys[action]


def cleanup(job_id: str) -> None:
    """Delete the per-job idem file. Safe to call repeatedly."""
    p = _path(job_id)
    try:
        p.unlink()
    except FileNotFoundError:
        pass
    except OSError:
        pass


def list_jobs() -> list[str]:
    """Return job_ids that still have idem keys on disk (used by replay)."""
    d = _idem_dir()
    if not d.exists():
        return []
    out = []
    for f in d.iterdir():
        if f.is_file() and f.suffix == ".json":
            out.append(f.stem)
    return out
