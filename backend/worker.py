"""Autonomous polling worker.

Runs as an asyncio task started during FastAPI startup. Every POLL_INTERVAL
seconds it:
  1. Reads the active session (PMS URL + access_token + worker_id).
  2. Asks the PMS for pending jobs (`list_queue?status=pending`).
  3. For each job whose `next_retry_at` is past (or null), tries to claim it,
     submit the guest to KBS (Phase A: simulated), and report complete/fail.

Error classification (Phase A spec):
  - 5xx / timeout / network         → fail(retry=True)
  - 4xx (incl. schema/validation)   → fail(retry=False)
  - 429 (rate limited)              → fail(retry=True) + warn log
  - Unexpected exception            → fail(retry=True) + traceback log

The PMS decides actual retry timing (exponential backoff) and dead state once
`attempts >= max_attempts`. The worker only reports.
"""
from __future__ import annotations

import asyncio
import logging
import os
import socket
import time
import traceback
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from kbs_client import (
    KBSConfigError,
    KBSFatalError,
    KBSRetryableError,
    submit_guest,
)
from pms_client import (
    PMSError,
    claim_job,
    complete_job,
    fail_job,
    list_queue,
)
import journal
from session import DATA_DIR, clear_session, load_session

log = logging.getLogger("kbs-bridge.worker")

POLL_INTERVAL_DEFAULT = 15  # seconds
LEASE_SECONDS = 300  # 5 minutes
WORKER_ID_FILE = DATA_DIR / "worker_id"


# ---------- Worker identity ----------

def _read_or_create_worker_id() -> str:
    """Persist a stable worker_id across restarts: `<host>-<uuid4>`."""
    try:
        if WORKER_ID_FILE.exists():
            wid = WORKER_ID_FILE.read_text().strip()
            if wid:
                return wid
    except OSError as e:
        log.warning("worker_id okunamadi: %s", e)
    host = (socket.gethostname() or "agent").replace(" ", "-")[:40]
    wid = f"agent-{host}-{uuid.uuid4()}"
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        WORKER_ID_FILE.write_text(wid)
        try:
            os.chmod(WORKER_ID_FILE, 0o600)
        except OSError:
            pass
    except OSError as e:
        log.warning("worker_id kaydedilemedi: %s", e)
    return wid


# ---------- Worker state (in-memory, exposed via /api/worker/status) ----------

class WorkerState:
    """Minimal in-memory snapshot for the UI status panel."""

    def __init__(self, worker_id: str, poll_interval: int) -> None:
        self.worker_id = worker_id
        self.poll_interval = poll_interval
        self.started_at: Optional[str] = None
        self.last_poll_at: Optional[str] = None
        self.last_poll_ok: Optional[bool] = None
        self.last_error: Optional[str] = None
        self.session_status: str = "no_session"  # no_session | ok | invalid
        self.queue_stats: dict[str, int] = {}
        self.claim_count: int = 0
        self.complete_count: int = 0
        self.fail_count: int = 0
        self.recent_jobs: list[dict] = []  # newest first, capped
        self.running: bool = False

    def record_recent(self, job_id: str, action: str, outcome: str, detail: str = "") -> None:
        self.recent_jobs.insert(0, {
            "ts": datetime.now(timezone.utc).isoformat(),
            "job_id": job_id,
            "action": action,
            "outcome": outcome,
            "detail": detail,
        })
        del self.recent_jobs[20:]

    def to_dict(self) -> dict:
        return {
            "worker_id": self.worker_id,
            "running": self.running,
            "poll_interval": self.poll_interval,
            "started_at": self.started_at,
            "last_poll_at": self.last_poll_at,
            "last_poll_ok": self.last_poll_ok,
            "last_error": self.last_error,
            "session_status": self.session_status,
            "queue_stats": self.queue_stats,
            "counters": {
                "claim": self.claim_count,
                "complete": self.complete_count,
                "fail": self.fail_count,
            },
            "recent_jobs": self.recent_jobs,
        }


_state: Optional[WorkerState] = None
_task: Optional[asyncio.Task] = None
_stop_event: Optional[asyncio.Event] = None
_poll_now_event: Optional[asyncio.Event] = None


def get_state() -> WorkerState:
    """Lazy-init for tests / status endpoint before the worker is started."""
    global _state
    if _state is None:
        _state = WorkerState(
            worker_id=_read_or_create_worker_id(),
            poll_interval=int(os.environ.get("POLL_INTERVAL", POLL_INTERVAL_DEFAULT)),
        )
    return _state


# ---------- Job processing ----------

def _is_due(next_retry_at: Optional[str]) -> bool:
    """True if the job has no next_retry_at or it's already in the past."""
    if not next_retry_at:
        return True
    try:
        dt = datetime.fromisoformat(next_retry_at.replace("Z", "+00:00"))
    except ValueError:
        return True
    return dt <= datetime.now(timezone.utc)


def _classify_pms_error(exc: PMSError) -> tuple[bool, str]:
    """Map a PMSError to (retry, log_level_warn). Used when claim/complete/fail
    themselves fail mid-flight."""
    if exc.status_code in (401, 403):
        return False, "auth"
    if exc.status_code in (404, 409):
        return False, "skip"  # job gone or already taken/closed
    if exc.status_code == 429:
        return True, "rate_limit"
    if 500 <= exc.status_code < 600 or exc.status_code in (503, 504):
        return True, "server"
    if 400 <= exc.status_code < 500:
        return False, "client"
    return True, "unknown"


async def _claim_then_process(
    pms_url: str,
    token: str,
    worker_id: str,
    job: dict,
    state: WorkerState,
) -> None:
    """Claim a single job and run the simulated KBS submission."""
    job_id = job["id"]
    payload = job.get("payload") or {}

    # ----- claim -----
    try:
        claim_resp = await claim_job(
            pms_url, token, job_id, worker_id, lease_seconds=LEASE_SECONDS
        )
        state.claim_count += 1
        state.record_recent(job_id, "claim", "ok")
        journal.append("claim", job_id=job_id, worker_id=worker_id)
    except PMSError as e:
        if e.status_code in (404, 409):
            log.info("Job %s skip (claim %s): %s", job_id, e.status_code, e.detail)
            state.record_recent(job_id, "claim", f"skip-{e.status_code}", str(e.detail)[:200])
            journal.append("claim_skip", job_id=job_id, status=e.status_code)
            return
        if e.status_code == 401:
            raise  # bubble up so the loop marks session invalid
        log.warning("Job %s claim hatasi (%s): %s", job_id, e.status_code, e.detail)
        state.record_recent(job_id, "claim", "error", str(e.detail)[:200])
        return

    claimed = (claim_resp or {}).get("job") or job

    # ----- submit to KBS (Phase A: simulated) -----
    kbs_reference: Optional[str] = None
    error_msg: Optional[str] = None
    retry: bool = True

    try:
        # submit_guest is sync (Phase A simulation uses time.sleep; Phase B will
        # replace with httpx-async). Offload to a thread so the polling loop
        # stays responsive — keeps poll-now and shutdown signals snappy.
        kbs_reference = await asyncio.to_thread(submit_guest, payload, None)
    except KBSConfigError as e:
        # Genuine config error (e.g. Phase B not yet wired) → permanent
        error_msg = f"KBSConfigError: {e}"
        retry = False
        log.error(error_msg)
    except KBSFatalError as e:
        error_msg = f"KBSFatalError: {e}"
        retry = False
        log.error("Job %s fatal: %s", job_id, e)
    except KBSRetryableError as e:
        error_msg = f"KBSRetryableError: {e}"
        retry = True
        log.warning("Job %s retryable: %s", job_id, e)
    except Exception as e:  # pragma: no cover - defensive
        error_msg = f"{e.__class__.__name__}: {e}"
        retry = True
        log.exception("Job %s beklenmeyen hata", job_id)
        error_msg += "\n" + traceback.format_exc()[:1500]

    # ----- report back to PMS -----
    if kbs_reference:
        try:
            await complete_job(pms_url, token, job_id, worker_id, kbs_reference)
            state.complete_count += 1
            state.record_recent(job_id, "complete", "ok", kbs_reference)
            journal.append("complete", job_id=job_id, kbs_reference=kbs_reference)
            log.info("Job %s done. ref=%s", job_id, kbs_reference)
        except PMSError as e:
            if e.status_code == 409:
                # Already closed (e.g. duplicate complete after retry) → treat as ok
                state.record_recent(job_id, "complete", "already-done", kbs_reference)
                log.info("Job %s already closed on PMS (409). ref=%s", job_id, kbs_reference)
            elif e.status_code == 401:
                raise
            else:
                log.error("Job %s complete hatasi (%s): %s", job_id, e.status_code, e.detail)
                state.record_recent(job_id, "complete", "pms-error", str(e.detail)[:200])
        return

    # KBS failed → fail the job
    try:
        await fail_job(pms_url, token, job_id, worker_id, error_msg or "Bilinmeyen KBS hatasi", retry)
        state.fail_count += 1
        outcome = "retry" if retry else "dead"
        state.record_recent(job_id, "fail", outcome, (error_msg or "")[:200])
        journal.append("fail", job_id=job_id, retry=retry, error=(error_msg or "")[:500])
    except PMSError as e:
        if e.status_code == 401:
            raise
        log.error("Job %s fail() hatasi (%s): %s", job_id, e.status_code, e.detail)
        state.record_recent(job_id, "fail", "pms-error", str(e.detail)[:200])


# ---------- Main loop ----------

async def _poll_once(state: WorkerState) -> None:
    """One pass: load session, ask PMS for pending jobs, process them."""
    sess = load_session()
    if not sess:
        state.session_status = "no_session"
        state.queue_stats = {}
        state.last_poll_at = datetime.now(timezone.utc).isoformat()
        state.last_poll_ok = True
        state.last_error = None
        return

    pms_url = sess.get("pms_url")
    token = sess.get("access_token")
    if not pms_url or not token:
        state.session_status = "no_session"
        state.last_poll_at = datetime.now(timezone.utc).isoformat()
        state.last_poll_ok = True
        return

    try:
        data = await list_queue(pms_url, token, status="pending", limit=20)
    except PMSError as e:
        state.last_poll_at = datetime.now(timezone.utc).isoformat()
        state.last_poll_ok = False
        state.last_error = f"list_queue {e.status_code}: {e.detail}"
        if e.status_code == 401:
            log.warning("Session invalid (401), oturum temizleniyor")
            clear_session()
            state.session_status = "invalid"
        return

    state.session_status = "ok"
    state.queue_stats = data.get("stats") or {}
    state.last_poll_at = datetime.now(timezone.utc).isoformat()
    state.last_poll_ok = True
    state.last_error = None

    jobs = data.get("jobs") or []
    for job in jobs:
        if not _is_due(job.get("next_retry_at")):
            continue
        try:
            await _claim_then_process(pms_url, token, state.worker_id, job, state)
        except PMSError as e:
            if e.status_code == 401:
                log.warning("Job islerken 401, oturum gecersiz")
                clear_session()
                state.session_status = "invalid"
                state.last_error = "Oturum gecersiz (401)"
                return
            # Other PMSErrors already logged inside _claim_then_process
        except Exception:  # pragma: no cover - defensive
            log.exception("Job islerken beklenmeyen hata: %s", job.get("id"))


async def _sleep_until_event_or_timeout(
    stop: asyncio.Event, poll_now: asyncio.Event, timeout: float
) -> None:
    """Wait up to `timeout` seconds, returning early on stop or poll_now.

    Cancels and awaits the pending wait task so we don't leak it across
    iterations (otherwise long uptimes accumulate orphaned coroutines).
    Note: caller is responsible for clearing `poll_now` once consumed.
    """
    stop_task = asyncio.create_task(stop.wait())
    poll_task = asyncio.create_task(poll_now.wait())
    try:
        await asyncio.wait(
            {stop_task, poll_task},
            timeout=timeout,
            return_when=asyncio.FIRST_COMPLETED,
        )
    finally:
        for t in (stop_task, poll_task):
            if not t.done():
                t.cancel()
        # Drain cancellations cleanly
        await asyncio.gather(stop_task, poll_task, return_exceptions=True)


async def _loop(state: WorkerState, stop: asyncio.Event, poll_now: asyncio.Event) -> None:
    log.info(
        "worker started: %s polling every %ds", state.worker_id, state.poll_interval
    )
    state.started_at = datetime.now(timezone.utc).isoformat()
    state.running = True
    try:
        while not stop.is_set():
            # Consume any prior poll-now trigger so it fires at most once per cycle.
            poll_now.clear()
            try:
                await _poll_once(state)
            except Exception:  # pragma: no cover - defensive
                log.exception("_poll_once beklenmeyen hata")
                state.last_poll_ok = False
                state.last_error = traceback.format_exc()[-500:]

            await _sleep_until_event_or_timeout(stop, poll_now, state.poll_interval)
    finally:
        state.running = False
        log.info("worker stopped: %s", state.worker_id)


def start(loop_factory=_loop) -> None:
    """Idempotent: launch the polling loop on the running event loop."""
    global _task, _stop_event, _poll_now_event
    if _task is not None and not _task.done():
        log.info("worker zaten calisiyor, atlanildi")
        return
    state = get_state()
    _stop_event = asyncio.Event()
    _poll_now_event = asyncio.Event()
    _task = asyncio.create_task(loop_factory(state, _stop_event, _poll_now_event))


async def stop() -> None:
    """Cancel the loop cleanly. Safe to call multiple times."""
    global _task, _stop_event
    if _stop_event is not None:
        _stop_event.set()
    if _task is not None:
        try:
            await asyncio.wait_for(_task, timeout=5)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            _task.cancel()
        _task = None


def trigger_poll_now() -> bool:
    """Wake up the loop early. Returns False if worker isn't running."""
    if _poll_now_event is None or _task is None or _task.done():
        return False
    _poll_now_event.set()
    return True
