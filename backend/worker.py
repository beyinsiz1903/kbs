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

import httpx

from kbs_client import (
    KBSConfigError,
    KBSFatalError,
    KBSRetryableError,
    is_real_ready,
    submit_guest,
)
from pms_client import (
    PMSError,
    claim_job,
    complete_job,
    fail_job,
    list_queue,
)
import idem
import journal
import eventlog
import sse_client
from session import DATA_DIR, clear_session, load_session

log = logging.getLogger("kbs-bridge.worker")

POLL_INTERVAL_DEFAULT = 15  # seconds
LEASE_SECONDS = 300  # 5 minutes
WORKER_ID_FILE = DATA_DIR / "worker_id"

# Required env vars when KBS_MODE=real (Phase B). The actual values are
# obtained from EGM/Jandarma; until then KBS_MODE stays "simulation".
REAL_MODE_REQUIRED_ENV = ("KBS_WSDL_URL",)


def _missing_real_mode_env() -> list[str]:
    """Return a list of required env vars that are missing in real mode."""
    return [k for k in REAL_MODE_REQUIRED_ENV if not os.environ.get(k)]


def _missing_session_kbs_config(sess: dict) -> list[str]:
    """Return KBS session-side config fields that are missing (real mode only)."""
    return [
        k for k in (
            "kbs_tesis_kodu", "kbs_kullanici_adi", "kbs_sifre",
            "kbs_servis_url", "kbs_kurum",
        )
        if not (sess.get(k) or "").strip()
    ]


# ---------- Worker identity ----------

def _short_mac() -> str:
    """Return last 4 hex chars of the MAC address, or 'noMAC' if unavailable.

    Phase D: when an otel runs two PCs with the same Windows hostname (common
    with image deployments), the hostname-only ID collides. Adding a 4-char
    MAC slug visually disambiguates them in admin tooling without spilling
    the full MAC into PMS logs.

    `uuid.getnode()` returns a random 48-bit value if the MAC can't be read;
    bit 0x010000000000 is set in that case — we detect and fall back.
    """
    try:
        node = uuid.getnode()
    except Exception:
        return "noMAC"
    if node & 0x010000000000:
        # uuid.getnode() couldn't read a real MAC — random fallback per docs.
        return "noMAC"
    return f"{node & 0xFFFF:04x}"


def _read_or_create_worker_id() -> str:
    """Persist a stable worker_id across restarts.

    Format: `agent-<host>-<mac4>-<uuid4>`. Existing pre-Phase-D files are
    honored as-is (no forced regeneration) so an upgrade in the field doesn't
    spam PMS with phantom-new-agent confusion. The host portion is sanitized
    (spaces → '-', truncated to 40 chars) so PMS logs stay legible.
    """
    try:
        if WORKER_ID_FILE.exists():
            wid = WORKER_ID_FILE.read_text().strip()
            if wid:
                return wid
    except OSError as e:
        log.warning("worker_id okunamadi: %s", e)
    host = (socket.gethostname() or "agent").replace(" ", "-")[:40]
    wid = f"agent-{host}-{_short_mac()}-{uuid.uuid4()}"
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
        # Possible values:
        #   no_session, ok, invalid, kbs_not_configured, refused
        self.session_status: str = "no_session"
        self.queue_stats: dict[str, int] = {}
        self.claim_count: int = 0
        self.complete_count: int = 0
        self.fail_count: int = 0
        self.recent_jobs: list[dict] = []  # newest first, capped
        self.running: bool = False
        self.kbs_mode: str = os.environ.get("KBS_MODE", "simulation").lower()
        self.worker_mode: str = os.environ.get("WORKER_MODE", "poll").lower()
        self.replay_count: int = 0
        # Phase D: distinct worker_ids currently holding in_progress claims.
        # We exclude our own. Refreshed every poll from PMS list_queue —
        # operators see at a glance whether a sibling agent is running.
        self.other_workers: list[dict] = []
        # Track which session token we already replayed for so we don't
        # re-scan the journal every poll.
        self._last_replayed_token: Optional[str] = None
        # Phase D follow-up: SSE push channel state.
        # `sse_connected` reflects whether the supervisor currently holds a
        # live stream. `sse_last_event_at` is updated on every event including
        # heartbeats so the operator can see "stream is alive". `auto` mode
        # uses `sse_consecutive_failures` to decide when to fall back.
        self.sse_connected: bool = False
        self.sse_last_event_at: Optional[str] = None
        self.sse_reconnect_count: int = 0
        self.sse_consecutive_failures: int = 0

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
            "kbs_mode": self.kbs_mode,
            "worker_mode": self.worker_mode,
            "queue_stats": self.queue_stats,
            "counters": {
                "claim": self.claim_count,
                "complete": self.complete_count,
                "fail": self.fail_count,
                "replay": self.replay_count,
            },
            "recent_jobs": self.recent_jobs,
            "other_workers": self.other_workers,
            # Flat fields — match the contract in task-7.md so external
            # consumers (status UI, ops dashboards) get the exact names
            # they expect without having to dig into a nested object.
            "sse_connected": self.sse_connected,
            "sse_last_event_at": self.sse_last_event_at,
            "sse_reconnect_count": self.sse_reconnect_count,
            # Nested copy retained for grouping in newer dashboards. Both
            # views read from the same WorkerState fields, so they cannot
            # drift.
            "sse": {
                "connected": self.sse_connected,
                "last_event_at": self.sse_last_event_at,
                "reconnect_count": self.sse_reconnect_count,
                "consecutive_failures": self.sse_consecutive_failures,
            },
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


async def _refresh_other_workers(pms_url: str, token: str, state: WorkerState) -> None:
    """Fetch in_progress jobs and extract distinct OTHER worker_ids.

    The PMS is the source of truth — we never talk to siblings directly. A
    sibling is "active" if it currently holds at least one in_progress lease.
    We expose: worker_id, job_count, lease_expires_at (latest seen).
    """
    try:
        data = await list_queue(pms_url, token, status="in_progress", limit=100)
    except PMSError as e:
        # Non-401 errors here are operational noise — log once at INFO and
        # leave the prior other_workers snapshot alone (better than wiping).
        if e.status_code == 401:
            raise
        log.info("other_workers fetch atlandi (%s): %s", e.status_code, e.detail)
        return

    by_worker: dict[str, dict] = {}
    for job in data.get("jobs") or []:
        wid = (job.get("worker_id") or "").strip()
        if not wid or wid == state.worker_id:
            continue
        rec = by_worker.setdefault(wid, {"worker_id": wid, "job_count": 0, "lease_expires_at": None})
        rec["job_count"] += 1
        lease = job.get("lease_expires_at")
        # Keep the LATEST lease so the operator can see how recent the sibling is.
        if lease and (rec["lease_expires_at"] is None or lease > rec["lease_expires_at"]):
            rec["lease_expires_at"] = lease
    state.other_workers = sorted(by_worker.values(), key=lambda r: r["worker_id"])


async def _claim_then_process(
    pms_url: str,
    token: str,
    worker_id: str,
    job: dict,
    state: WorkerState,
    kbs_cfg: Optional[dict] = None,
) -> None:
    """Claim a single job and run the simulated KBS submission."""
    job_id = job["id"]
    payload = job.get("payload") or {}

    # ----- claim (with persistent idempotency key) -----
    claim_key = idem.get_or_create(job_id, "claim")
    try:
        claim_resp = await claim_job(
            pms_url, token, job_id, worker_id,
            lease_seconds=LEASE_SECONDS, idem_key=claim_key,
        )
        state.claim_count += 1
        state.record_recent(job_id, "claim", "ok")
        journal.append("claim", job_id=job_id, worker_id=worker_id)
    except PMSError as e:
        if e.status_code in (404, 409):
            log.info("Job %s skip (claim %s): %s", job_id, e.status_code, e.detail)
            state.record_recent(job_id, "claim", f"skip-{e.status_code}", str(e.detail)[:200])
            journal.append("claim_skip", job_id=job_id, status=e.status_code)
            # Job is gone or already taken — release the idem keys so a
            # future job with the same id (PMS reuse) starts fresh.
            idem.cleanup(job_id)
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
        kbs_reference = await asyncio.to_thread(submit_guest, payload, kbs_cfg)
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
        # Journal the INTENT before calling PMS. If the call succeeds we'll
        # write a matching complete_ack; if we crash after this line, restart
        # replay will see pending_complete with no ack and re-call PMS using
        # the same idem key (PMS de-dupes).
        journal.append("pending_complete", job_id=job_id, kbs_reference=kbs_reference)
        complete_key = idem.get_or_create(job_id, "complete")
        try:
            await complete_job(
                pms_url, token, job_id, worker_id, kbs_reference,
                idem_key=complete_key,
            )
            state.complete_count += 1
            state.record_recent(job_id, "complete", "ok", kbs_reference)
            journal.append("complete_ack", job_id=job_id, kbs_reference=kbs_reference)
            idem.cleanup(job_id)  # terminal state — release keys
            log.info("Job %s done. ref=%s", job_id, kbs_reference)
        except PMSError as e:
            if e.status_code == 409:
                # Already closed (e.g. duplicate complete after retry) → treat as ok
                state.record_recent(job_id, "complete", "already-done", kbs_reference)
                journal.append("complete_ack", job_id=job_id, kbs_reference=kbs_reference, dup=True)
                idem.cleanup(job_id)
                log.info("Job %s already closed on PMS (409). ref=%s", job_id, kbs_reference)
            elif e.status_code == 401:
                raise
            else:
                log.error("Job %s complete hatasi (%s): %s", job_id, e.status_code, e.detail)
                state.record_recent(job_id, "complete", "pms-error", str(e.detail)[:200])
                # No ack written → replay will retry on next start.
        return

    # KBS failed → fail the job
    journal.append("pending_fail", job_id=job_id, retry=retry, error=(error_msg or "")[:500])
    fail_key = idem.get_or_create(job_id, "fail")
    try:
        fail_resp = await fail_job(
            pms_url, token, job_id, worker_id,
            error_msg or "Bilinmeyen KBS hatasi", retry, idem_key=fail_key,
        )
        state.fail_count += 1
        outcome = "retry" if retry else "dead"
        state.record_recent(job_id, "fail", outcome, (error_msg or "")[:200])
        will_retry = bool((fail_resp or {}).get("will_retry", retry))
        journal.append("fail_ack", job_id=job_id, will_retry=will_retry)
        if not will_retry:
            # PMS marked the job dead — release idem keys + alert IT via Event Log.
            idem.cleanup(job_id)
            eventlog.warn_dead_job(job_id, error=error_msg)
    except PMSError as e:
        if e.status_code == 401:
            raise
        log.error("Job %s fail() hatasi (%s): %s", job_id, e.status_code, e.detail)
        state.record_recent(job_id, "fail", "pms-error", str(e.detail)[:200])
        # No ack written → replay will retry on next start.


# ---------- Crash-recovery replay ----------

async def _replay_unacked(pms_url: str, token: str, worker_id: str, state: WorkerState) -> bool:
    """Replay any complete/fail intent that wasn't acked before a crash.

    PMS de-dupes via Idempotency-Key, so re-calling with the same key after a
    successful-but-unacked first call is safe (PMS returns 409 or the original
    response). We bail on the first 401 so the loop can clear the session.

    Returns True if every unacked entry was either acked or is permanently
    gone (we journaled the ack); False if any entry hit a transient PMS error
    and is still unacked. The caller uses this to decide whether to mark the
    session as "fully replayed" — if we return False, next poll will retry.
    """
    try:
        unacked = journal.find_unacked()
    except Exception:  # pragma: no cover - defensive
        log.exception("journal.find_unacked() basarisiz, replay atlandi")
        return False
    if not unacked:
        return True
    log.info("Replaying %d unacked PMS intent(s) after restart", len(unacked))
    all_resolved = True
    for rec in unacked:
        ev = rec.get("event")
        jid = rec.get("job_id")
        try:
            if ev == "pending_complete":
                ref = rec.get("kbs_reference") or ""
                key = idem.get_or_create(jid, "complete")
                try:
                    await complete_job(pms_url, token, jid, worker_id, ref, idem_key=key)
                    journal.append("complete_ack", job_id=jid, kbs_reference=ref, replay=True)
                    idem.cleanup(jid)
                    state.complete_count += 1
                    state.replay_count += 1
                    state.record_recent(jid, "replay-complete", "ok", ref)
                except PMSError as e:
                    if e.status_code == 409:
                        journal.append("complete_ack", job_id=jid, kbs_reference=ref,
                                        replay=True, dup=True)
                        idem.cleanup(jid)
                        state.replay_count += 1
                        state.record_recent(jid, "replay-complete", "already-done", ref)
                    elif e.status_code == 401:
                        raise
                    else:
                        log.warning("Replay complete %s hata %s: %s", jid, e.status_code, e.detail)
                        state.record_recent(jid, "replay-complete", "pms-error", str(e.detail)[:200])
                        all_resolved = False
            elif ev == "pending_fail":
                err = rec.get("error") or "Bilinmeyen hata"
                want_retry = bool(rec.get("retry", True))
                key = idem.get_or_create(jid, "fail")
                try:
                    fr = await fail_job(pms_url, token, jid, worker_id, err, want_retry, idem_key=key)
                    journal.append("fail_ack", job_id=jid,
                                    will_retry=bool((fr or {}).get("will_retry", want_retry)),
                                    replay=True)
                    state.replay_count += 1
                    state.fail_count += 1
                    if not (fr or {}).get("will_retry", want_retry):
                        idem.cleanup(jid)
                        eventlog.warn_dead_job(jid, error=err)
                    state.record_recent(jid, "replay-fail",
                                         "retry" if want_retry else "dead", err[:200])
                except PMSError as e:
                    if e.status_code == 401:
                        raise
                    log.warning("Replay fail %s hata %s: %s", jid, e.status_code, e.detail)
                    state.record_recent(jid, "replay-fail", "pms-error", str(e.detail)[:200])
                    all_resolved = False
        except PMSError:
            raise
        except Exception:  # pragma: no cover - defensive
            log.exception("Replay job %s islerken hata", jid)
            all_resolved = False
    return all_resolved


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

    # In real KBS mode, the worker MUST refuse to submit until BOTH:
    #   (1) the real SOAP path is actually implemented (kbs_client.is_real_ready)
    #   (2) the operator has supplied the KBS credentials/cert/kurum
    # Otherwise the simulated/missing _send_real raises KBSConfigError, the
    # worker would dead-letter the job, and the guest would silently NOT be
    # reported to EGM. We refuse to process at all instead.
    if state.kbs_mode == "real":
        if not is_real_ready():
            state.session_status = "kbs_not_ready"
            state.last_error = (
                "Gercek KBS gonderimi henuz aktif degil "
                "(WSDL + mTLS sertifikasi gelince kbs_client._send_real() doldurulacak). "
                "Isler PMS kuyrugunda bekletiliyor; dead-letter atilmadi."
            )
            state.last_poll_at = datetime.now(timezone.utc).isoformat()
            state.last_poll_ok = False
            return
        missing = _missing_session_kbs_config(sess)
        if missing:
            state.session_status = "kbs_not_configured"
            state.last_error = "Eksik KBS ayarlari: " + ", ".join(missing)
            state.last_poll_at = datetime.now(timezone.utc).isoformat()
            state.last_poll_ok = False
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

    # Phase D: peek at in_progress jobs to surface SIBLING agents to the
    # operator. We don't act on this — PMS is the coordinator — but seeing
    # "agent-RECEPTION-B" in the status panel reassures (or alerts) staff.
    # Failure here is non-fatal: the main poll cycle continues.
    await _refresh_other_workers(pms_url, token, state)

    # Run crash-recovery replay until every unacked entry is resolved. We only
    # mark the token "fully replayed" when nothing is left pending — otherwise
    # transient PMS 5xx during the first replay would silently strand the
    # unacked entries until the next login or process restart.
    if state._last_replayed_token != token:
        try:
            fully_resolved = await _replay_unacked(pms_url, token, state.worker_id, state)
            if fully_resolved:
                state._last_replayed_token = token
            # else: leave _last_replayed_token unchanged so next poll retries.
        except PMSError as e:
            if e.status_code == 401:
                clear_session()
                state.session_status = "invalid"
                state.last_error = "Replay sirasinda 401, oturum gecersiz"
                return
            # Non-401 errors during replay: log and continue with the normal poll.
            log.warning("Replay sirasinda PMS hatasi: %s %s", e.status_code, e.detail)

    # Build a small KBS config view of the session for submit_guest.
    kbs_cfg = {
        k: sess.get(k, "") for k in (
            "kbs_tesis_kodu", "kbs_kullanici_adi", "kbs_sifre",
            "kbs_servis_url", "kbs_kurum",
        )
    }

    jobs = data.get("jobs") or []
    for job in jobs:
        if not _is_due(job.get("next_retry_at")):
            continue
        try:
            await _claim_then_process(
                pms_url, token, state.worker_id, job, state, kbs_cfg,
            )
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


async def _sleep_with_stop(stop: asyncio.Event, timeout: float) -> None:
    """Sleep up to `timeout` seconds, returning early if stop is set.

    Used by the SSE supervisor between reconnect attempts. Cancels the wait
    task on early return so we don't accumulate orphaned coroutines on long
    uptimes (same hygiene as `_sleep_until_event_or_timeout`).
    """
    if stop.is_set() or timeout <= 0:
        return
    stop_task = asyncio.create_task(stop.wait())
    try:
        await asyncio.wait({stop_task}, timeout=timeout, return_when=asyncio.FIRST_COMPLETED)
    finally:
        if not stop_task.done():
            stop_task.cancel()
        await asyncio.gather(stop_task, return_exceptions=True)


# ---------- SSE supervisor (Phase D follow-up) ----------

# Backoff schedule for SSE reconnect: 1s, 2s, 4s, 8s, 16s, then capped at 30s.
SSE_BACKOFF_INITIAL = 1.0
SSE_BACKOFF_MAX = 30.0

# In `auto` mode, after this many consecutive failures we stop hammering the
# SSE endpoint with backoff and instead idle for SSE_AUTO_RETRY_INTERVAL
# seconds before trying again. The poll loop keeps running the whole time —
# the operator never loses jobs, they just wait up to POLL_INTERVAL seconds.
SSE_AUTO_FAILURE_THRESHOLD = 3
SSE_AUTO_RETRY_INTERVAL = 60.0


async def _sse_supervisor(
    state: WorkerState, stop: asyncio.Event, poll_now: asyncio.Event,
    open_stream=sse_client.open_stream,
) -> None:
    """Maintain a long-lived SSE connection; trigger poll_now on each event.

    Reconnect policy:
      - Successful connect resets backoff to 1s and `sse_consecutive_failures`
        to 0.
      - Each failure (connect refused, mid-stream EOF, auth, parse) increments
        the counter and waits backoff = min(prev * 2, 30s).
      - In `auto` mode, after SSE_AUTO_FAILURE_THRESHOLD consecutive failures
        we wait SSE_AUTO_RETRY_INTERVAL instead of the short backoff. The
        poll loop running in parallel keeps the operator covered.

    Auth errors clear the session (matches the polling loop's 401 behavior),
    then the supervisor idles until `stop` or a new session appears.

    `open_stream` is a parameter so tests can swap in a fake without monkey-
    patching module globals.
    """
    log.info("SSE supervisor started (mode=%s)", state.worker_mode)
    backoff = SSE_BACKOFF_INITIAL
    last_event_id: Optional[str] = None

    try:
        while not stop.is_set():
            sess = load_session()
            token = (sess or {}).get("access_token")
            pms_url = (sess or {}).get("pms_url")
            if not sess or not token or not pms_url:
                # No session yet — wait politely; login handler will eventually
                # populate it. We don't count "no session" as a failure.
                await _sleep_with_stop(stop, 5.0)
                continue

            try:
                async with open_stream(pms_url, token, last_event_id=last_event_id) as events:
                    state.sse_connected = True
                    state.sse_consecutive_failures = 0
                    backoff = SSE_BACKOFF_INITIAL
                    log.info("SSE connected to %s", pms_url)
                    async for ev in events:
                        if stop.is_set():
                            break
                        state.sse_last_event_at = datetime.now(timezone.utc).isoformat()
                        if ev.id:
                            last_event_id = ev.id
                        ev_type = (ev.event or "message").lower()
                        if ev_type == "new_job":
                            # The actual claim/process flow runs in the poll
                            # loop — we just wake it up. This keeps idempotency,
                            # atomic claim semantics, and journal replay
                            # identical between poll and SSE modes.
                            poll_now.set()
                        elif ev_type in ("heartbeat", "ping"):
                            # Server keep-alive — already updated last_event_at.
                            pass
                        elif ev_type == "lease_expired":
                            # Future PMS event: a sibling lost its lease; wake
                            # poll so we can grab the freed job quickly.
                            poll_now.set()
                        else:
                            log.debug("SSE bilinmeyen event: %s", ev_type)
            except sse_client.SSEAuthError as e:
                log.warning("SSE auth hatasi (%s) — oturum temizleniyor", e)
                state.sse_connected = False
                clear_session()
                state.session_status = "invalid"
                state.last_error = "SSE 401/403: oturum gecersiz"
                # Don't burn backoff on a missing session — the next loop
                # iteration will hit the `not sess` branch and idle on 5s.
                continue
            except asyncio.CancelledError:
                raise
            except (sse_client.SSEConnectError, httpx.RequestError, Exception) as e:
                # Mid-stream errors arrive here too (httpx.RemoteProtocolError,
                # ReadError, ConnectionResetError). We never want the
                # supervisor to die — log and back off.
                log.warning("SSE baglanti koptu/hata: %s", e.__class__.__name__)
            finally:
                if state.sse_connected:
                    state.sse_connected = False
                    state.sse_reconnect_count += 1

            state.sse_consecutive_failures += 1
            if (
                state.worker_mode == "auto"
                and state.sse_consecutive_failures >= SSE_AUTO_FAILURE_THRESHOLD
            ):
                # Auto mode: stop pestering the endpoint; rely on poll loop.
                # Try again after a longer idle so a recovered PMS still gets
                # the SSE benefit eventually.
                log.info(
                    "SSE auto fallback: %d ardisik basarisizlik, %ss bekle",
                    state.sse_consecutive_failures, int(SSE_AUTO_RETRY_INTERVAL),
                )
                await _sleep_with_stop(stop, SSE_AUTO_RETRY_INTERVAL)
                # Reset so we get a fresh fast-retry cycle on the next attempt.
                state.sse_consecutive_failures = 0
                backoff = SSE_BACKOFF_INITIAL
            else:
                await _sleep_with_stop(stop, backoff)
                backoff = min(backoff * 2, SSE_BACKOFF_MAX)
    finally:
        state.sse_connected = False
        log.info("SSE supervisor stopped")


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
        "worker started: %s mode=%s polling every %ds",
        state.worker_id, state.worker_mode, state.poll_interval,
    )
    state.started_at = datetime.now(timezone.utc).isoformat()
    state.running = True

    # In `sse` and `auto` modes we run a long-lived SSE supervisor alongside
    # the poll loop. SSE events fire `poll_now`; the actual claim/process
    # flow stays in the poll loop so idempotency, atomic claim semantics,
    # and journal replay are identical between modes (no SSE-only code path
    # to drift). In `sse` mode the poll loop also runs as a safety net at
    # the configured interval — if SSE silently drops or misses an event,
    # the operator never loses jobs, just up to POLL_INTERVAL of latency.
    sse_task: Optional[asyncio.Task] = None
    if state.worker_mode in ("sse", "auto"):
        sse_task = asyncio.create_task(
            _sse_supervisor(state, stop, poll_now), name="sse-supervisor",
        )

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
        if sse_task is not None and not sse_task.done():
            sse_task.cancel()
            await asyncio.gather(sse_task, return_exceptions=True)
        state.running = False
        log.info("worker stopped: %s", state.worker_id)


def start(loop_factory=_loop) -> None:
    """Idempotent: launch the polling loop on the running event loop.

    In real KBS mode, refuses to start if env-level config (e.g. KBS_WSDL_URL)
    is missing. The status endpoint will surface the refusal so the operator
    sees exactly which env var to set instead of getting silent simulated refs.
    """
    global _task, _stop_event, _poll_now_event
    if _task is not None and not _task.done():
        log.info("worker zaten calisiyor, atlanildi")
        return
    state = get_state()

    if state.kbs_mode == "real":
        missing_env = _missing_real_mode_env()
        if missing_env:
            state.session_status = "refused"
            state.running = False
            state.last_error = (
                "KBS_MODE=real ama eksik env: " + ", ".join(missing_env)
                + ". Worker baslatilmadi (sahte basari uretilmez)."
            )
            log.error(state.last_error)
            return

    # Phase D follow-up: SSE is now wired. Valid modes:
    #   poll  — classic 15s polling (no SSE supervisor)
    #   sse   — SSE supervisor + safety-net poll at POLL_INTERVAL
    #   auto  — same as sse, but after 3 consecutive SSE failures the
    #           supervisor idles longer and relies on poll to drain the queue
    if state.worker_mode not in ("poll", "sse", "auto"):
        state.session_status = "refused"
        state.running = False
        state.last_error = (
            f"Bilinmeyen WORKER_MODE={state.worker_mode}. "
            "Gecerli degerler: poll | sse | auto."
        )
        log.error(state.last_error)
        return

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
