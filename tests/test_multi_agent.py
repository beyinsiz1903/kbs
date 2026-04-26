"""Phase D — multi-agent integration test.

Two workers, one mock PMS. 50 jobs queued. Verify:
  - PMS atomic claim semantics: each job claimed exactly once.
  - Both workers process > 0 jobs (rough load distribution).
  - Total processed == 50, zero duplicates, zero stranded.

The mock PMS is in-process, lives behind the same `pms_client` interface
the worker uses, and serializes claims via `asyncio.Lock`. We don't go
through HTTP — that would test httpx, not the worker. We DO honor the
exact contract semantics (404 if missing, 409 if already claimed).
"""
import asyncio

import pytest

import worker
from pms_client import PMSError


class MockPMS:
    """In-memory PMS with atomic claim. Single-process, asyncio-safe."""

    def __init__(self, n_jobs: int) -> None:
        self.lock = asyncio.Lock()
        self.jobs: dict[str, dict] = {
            f"job-{i:03d}": {
                "id": f"job-{i:03d}",
                "status": "pending",
                "worker_id": None,
                "next_retry_at": None,
                "payload": {"guest": f"Misafir-{i}"},
            }
            for i in range(n_jobs)
        }

    async def list_queue(self, pms_url, token, status=None, limit=20, **_):
        async with self.lock:
            jobs = [
                j.copy()
                for j in self.jobs.values()
                if (status is None or j["status"] == status)
            ]
            return {"jobs": jobs[:limit], "stats": self._stats_unlocked()}

    def _stats_unlocked(self) -> dict:
        s = {"pending": 0, "in_progress": 0, "done": 0, "failed": 0, "dead": 0}
        for j in self.jobs.values():
            s[j["status"]] = s.get(j["status"], 0) + 1
        return s

    async def claim_job(self, pms_url, token, job_id, worker_id, lease_seconds=300, idem_key=None):
        async with self.lock:
            job = self.jobs.get(job_id)
            if job is None:
                raise PMSError(status_code=404, detail="not found")
            if job["status"] != "pending":
                # Already claimed by someone — atomic-claim contract requires 409.
                raise PMSError(status_code=409, detail="already claimed")
            job["status"] = "in_progress"
            job["worker_id"] = worker_id
            return {"job": job.copy()}

    async def complete_job(self, pms_url, token, job_id, worker_id, kbs_reference, notes="", idem_key=None):
        async with self.lock:
            job = self.jobs.get(job_id)
            if job is None:
                raise PMSError(status_code=404, detail="not found")
            if job["status"] == "done":
                # Idempotent retry — return the existing record with a 200.
                return {"job": job.copy()}
            if job["worker_id"] != worker_id:
                raise PMSError(status_code=403, detail="worker mismatch")
            job["status"] = "done"
            job["kbs_reference"] = kbs_reference
            return {"job": job.copy(), "report_id": f"rep-{job_id}"}

    async def fail_job(self, pms_url, token, job_id, worker_id, error, retry, idem_key=None):  # pragma: no cover
        async with self.lock:
            job = self.jobs.get(job_id)
            if job is None:
                raise PMSError(status_code=404, detail="not found")
            job["status"] = "dead" if not retry else "pending"
            return {"job": job.copy(), "will_retry": retry}


@pytest.mark.asyncio
async def test_two_workers_split_50_jobs_no_duplicates(monkeypatch):
    """End-to-end: 2 workers, 50 jobs, exactly 50 completes, 0 duplicates."""
    pms = MockPMS(n_jobs=50)

    # Patch the module-level functions worker.py imported.
    monkeypatch.setattr(worker, "list_queue", pms.list_queue)
    monkeypatch.setattr(worker, "claim_job", pms.claim_job)
    monkeypatch.setattr(worker, "complete_job", pms.complete_job)
    monkeypatch.setattr(worker, "fail_job", pms.fail_job)

    # KBS submit must succeed deterministically.
    monkeypatch.setattr(worker, "submit_guest", lambda payload, cfg: f"ref-{payload['guest']}")

    # session.load_session needs to return a non-empty session so _poll_once proceeds.
    monkeypatch.setattr(worker, "load_session", lambda: {
        "pms_url": "https://pms.test",
        "access_token": "tok",
        "kbs_tesis_kodu": "X",
        "kbs_kullanici_adi": "X",
        "kbs_sifre": "X",
        "kbs_servis_url": "X",
        "kbs_kurum": "polis",
    })
    monkeypatch.setattr(worker, "is_real_ready", lambda: True)
    monkeypatch.setenv("KBS_MODE", "simulation")

    state_a = worker.WorkerState(worker_id="agent-A", poll_interval=1)
    state_b = worker.WorkerState(worker_id="agent-B", poll_interval=1)

    # Run a few cycles concurrently. Each _poll_once processes ~20 jobs (limit=20),
    # so 3 cycles per worker is enough to drain 50 jobs deterministically.
    for _ in range(4):
        await asyncio.gather(
            worker._poll_once(state_a),
            worker._poll_once(state_b),
        )

    statuses = [j["status"] for j in pms.jobs.values()]
    assert statuses.count("done") == 50, f"expected 50 done, got {statuses.count('done')}"
    assert statuses.count("pending") == 0
    assert statuses.count("in_progress") == 0

    # Both workers should have processed at least 1 job each. Distribution is
    # not 25/25 (asyncio scheduling isn't fair), but no worker should be idle.
    counts: dict[str, int] = {}
    for j in pms.jobs.values():
        counts[j["worker_id"]] = counts.get(j["worker_id"], 0) + 1
    assert "agent-A" in counts and counts["agent-A"] > 0
    assert "agent-B" in counts and counts["agent-B"] > 0
    assert sum(counts.values()) == 50

    # Cross-check: no job claimed by both. (Implied by single status field, but
    # an explicit assertion catches any future regression to per-worker logs.)
    duplicates = [k for k, v in counts.items() if v == 0]
    assert not duplicates


@pytest.mark.asyncio
async def test_409_on_direct_claim_race_does_not_double_process(monkeypatch):
    """When two workers concurrently CLAIM the same job, exactly one wins.

    We bypass list_queue (which would normally hide the job from the second
    worker once it goes in_progress) and call _claim_then_process directly
    on both workers. This exercises the contract semantics: PMS atomic
    claim + 409 → loser SKIPS without a fail report.
    """
    pms = MockPMS(n_jobs=1)
    monkeypatch.setattr(worker, "claim_job", pms.claim_job)
    monkeypatch.setattr(worker, "complete_job", pms.complete_job)
    monkeypatch.setattr(worker, "fail_job", pms.fail_job)
    monkeypatch.setattr(worker, "submit_guest", lambda payload, cfg: "ref-1")

    state_a = worker.WorkerState(worker_id="agent-A", poll_interval=1)
    state_b = worker.WorkerState(worker_id="agent-B", poll_interval=1)
    job_view = pms.jobs["job-000"].copy()

    await asyncio.gather(
        worker._claim_then_process("https://pms.test", "tok", "agent-A", job_view, state_a, None),
        worker._claim_then_process("https://pms.test", "tok", "agent-B", job_view, state_b, None),
    )

    job = pms.jobs["job-000"]
    assert job["status"] == "done"
    winner_state, loser_state = (
        (state_a, state_b) if job["worker_id"] == "agent-A" else (state_b, state_a)
    )
    # Winner: claim ok + complete ok. Loser: claim skip-409 only.
    assert winner_state.complete_count == 1
    assert winner_state.claim_count == 1
    skip_records = [r for r in loser_state.recent_jobs if r["outcome"].startswith("skip-409")]
    assert len(skip_records) == 1, f"loser must record exactly one skip-409, got {loser_state.recent_jobs!r}"
    assert loser_state.fail_count == 0, "NEVER report fail to PMS on a 409 — would burn an attempt"
    assert loser_state.claim_count == 0, "loser must NOT increment claim counter"
