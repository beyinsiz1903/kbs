"""Phase D — `other_workers` visibility from PMS in_progress jobs."""
import pytest

import worker
from pms_client import PMSError


@pytest.fixture
def state():
    s = worker.WorkerState(worker_id="me", poll_interval=15)
    return s


@pytest.mark.asyncio
async def test_excludes_self(state, monkeypatch):
    async def fake_list(pms_url, token, status, limit):
        assert status == "in_progress"
        return {"jobs": [
            {"id": "j1", "worker_id": "me", "lease_expires_at": "2026-04-26T12:00:00Z"},
            {"id": "j2", "worker_id": "agent-other-A", "lease_expires_at": "2026-04-26T12:01:00Z"},
        ]}
    monkeypatch.setattr(worker, "list_queue", fake_list)

    await worker._refresh_other_workers("https://pms", "tok", state)

    assert len(state.other_workers) == 1
    assert state.other_workers[0]["worker_id"] == "agent-other-A"
    assert state.other_workers[0]["job_count"] == 1


@pytest.mark.asyncio
async def test_aggregates_count_per_worker(state, monkeypatch):
    async def fake_list(pms_url, token, status, limit):
        return {"jobs": [
            {"id": "j1", "worker_id": "agent-A", "lease_expires_at": "2026-04-26T12:00:00Z"},
            {"id": "j2", "worker_id": "agent-A", "lease_expires_at": "2026-04-26T12:05:00Z"},
            {"id": "j3", "worker_id": "agent-B", "lease_expires_at": "2026-04-26T12:02:00Z"},
        ]}
    monkeypatch.setattr(worker, "list_queue", fake_list)

    await worker._refresh_other_workers("https://pms", "tok", state)

    by_id = {w["worker_id"]: w for w in state.other_workers}
    assert by_id["agent-A"]["job_count"] == 2
    # Latest lease kept
    assert by_id["agent-A"]["lease_expires_at"] == "2026-04-26T12:05:00Z"
    assert by_id["agent-B"]["job_count"] == 1


@pytest.mark.asyncio
async def test_skips_jobs_without_worker_id(state, monkeypatch):
    async def fake_list(pms_url, token, status, limit):
        return {"jobs": [
            {"id": "j1"},  # no worker_id
            {"id": "j2", "worker_id": ""},
            {"id": "j3", "worker_id": "agent-real"},
        ]}
    monkeypatch.setattr(worker, "list_queue", fake_list)

    await worker._refresh_other_workers("https://pms", "tok", state)

    assert [w["worker_id"] for w in state.other_workers] == ["agent-real"]


@pytest.mark.asyncio
async def test_non_401_errors_preserve_prior_snapshot(state, monkeypatch):
    state.other_workers = [{"worker_id": "agent-cached", "job_count": 1, "lease_expires_at": None}]

    async def fake_list(pms_url, token, status, limit):
        raise PMSError(status_code=503, detail="PMS yok")
    monkeypatch.setattr(worker, "list_queue", fake_list)

    await worker._refresh_other_workers("https://pms", "tok", state)

    # Snapshot preserved — better than a flicker to empty.
    assert state.other_workers == [{"worker_id": "agent-cached", "job_count": 1, "lease_expires_at": None}]


@pytest.mark.asyncio
async def test_401_propagates(state, monkeypatch):
    async def fake_list(pms_url, token, status, limit):
        raise PMSError(status_code=401, detail="invalid")
    monkeypatch.setattr(worker, "list_queue", fake_list)

    with pytest.raises(PMSError) as exc:
        await worker._refresh_other_workers("https://pms", "tok", state)
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_to_dict_includes_other_workers_and_worker_mode(state):
    state.other_workers = [{"worker_id": "agent-X", "job_count": 3, "lease_expires_at": None}]
    d = state.to_dict()
    assert d["other_workers"] == state.other_workers
    assert "worker_mode" in d
