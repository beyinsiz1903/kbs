"""Behavior tests for the polling worker.

We monkeypatch `pms_client` and `kbs_client` so the worker runs against a
fake PMS + KBS. Each test exercises one end-to-end scenario from Phase A.
"""
import asyncio
import pytest


@pytest.mark.asyncio
async def test_worker_id_persists_across_runs(_isolated_data_dir):
    import worker
    wid1 = worker._read_or_create_worker_id()
    # Simulate a restart by re-running creator
    worker._state = None
    wid2 = worker._read_or_create_worker_id()
    assert wid1 == wid2
    assert "agent-" in wid1


@pytest.mark.asyncio
async def test_state_to_dict_shape(_isolated_data_dir):
    import worker
    s = worker.get_state().to_dict()
    assert {"worker_id", "running", "poll_interval", "session_status",
            "queue_stats", "counters", "recent_jobs"} <= set(s.keys())
    assert s["counters"] == {"claim": 0, "complete": 0, "fail": 0}


def _save_session(monkeypatch):
    """Helper: write a fake authed session into the encrypted store."""
    import session
    session.save_session({
        "pms_url": "https://pms.x.com",
        "access_token": "tok-1",
        "user": {"email": "u@x", "tenant_id": "h1"},
        "hotel_id": "h1",
    })


@pytest.mark.asyncio
async def test_poll_once_no_session_marks_no_session(_isolated_data_dir):
    import worker
    state = worker.get_state()
    await worker._poll_once(state)
    assert state.session_status == "no_session"
    assert state.last_poll_ok is True


@pytest.mark.asyncio
async def test_poll_once_happy_path_completes_job(_isolated_data_dir, monkeypatch):
    import worker
    import pms_client
    import kbs_client

    _save_session(monkeypatch)

    queue = {
        "jobs": [{"id": "j1", "payload": {"guest_name": "A"}, "next_retry_at": None}],
        "stats": {"pending": 1, "in_progress": 0, "done": 0, "failed": 0, "dead": 0},
    }
    completed = []

    async def fake_list_queue(url, token, **kw):
        return queue

    async def fake_claim(url, token, job_id, worker_id, **kw):
        return {"job": {"id": job_id, "status": "in_progress"}}

    async def fake_complete(url, token, job_id, worker_id, kbs_reference, **kw):
        completed.append((job_id, kbs_reference))
        return {"job": {"id": job_id, "status": "done"}}

    async def fake_fail(*a, **kw):
        raise AssertionError("fail() should not be called on happy path")

    monkeypatch.setattr(pms_client, "list_queue", fake_list_queue)
    monkeypatch.setattr(pms_client, "claim_job", fake_claim)
    monkeypatch.setattr(pms_client, "complete_job", fake_complete)
    monkeypatch.setattr(pms_client, "fail_job", fake_fail)
    monkeypatch.setattr(worker, "list_queue", fake_list_queue)
    monkeypatch.setattr(worker, "claim_job", fake_claim)
    monkeypatch.setattr(worker, "complete_job", fake_complete)
    monkeypatch.setattr(worker, "fail_job", fake_fail)
    # Skip the simulated 0.4s sleep — patch the symbol the worker captured at import
    monkeypatch.setattr(worker, "submit_guest", lambda payload, config=None: "REF-OK")

    state = worker.get_state()
    await worker._poll_once(state)

    assert state.session_status == "ok"
    assert completed == [("j1", "REF-OK")]
    assert state.complete_count == 1
    assert state.fail_count == 0


@pytest.mark.asyncio
async def test_poll_once_kbs_retryable_calls_fail_with_retry_true(_isolated_data_dir, monkeypatch):
    import worker
    import pms_client
    import kbs_client

    _save_session(monkeypatch)

    failed = []

    async def fake_list_queue(*a, **kw):
        return {"jobs": [{"id": "j1", "payload": {"x": 1}}], "stats": {}}

    async def fake_claim(*a, **kw):
        return {"job": {"id": "j1"}}

    async def fake_complete(*a, **kw):
        raise AssertionError("complete should not run when KBS fails")

    async def fake_fail(url, token, job_id, worker_id, error, retry, **kw):
        failed.append((job_id, retry, error[:50]))
        return {"will_retry": retry}

    def kbs_explode(payload, config=None):
        raise kbs_client.KBSRetryableError("upstream 503")

    for mod in (pms_client, worker):
        monkeypatch.setattr(mod, "list_queue", fake_list_queue)
        monkeypatch.setattr(mod, "claim_job", fake_claim)
        monkeypatch.setattr(mod, "complete_job", fake_complete)
        monkeypatch.setattr(mod, "fail_job", fake_fail)
    monkeypatch.setattr(worker, "submit_guest", kbs_explode)

    state = worker.get_state()
    await worker._poll_once(state)

    assert len(failed) == 1
    assert failed[0][1] is True  # retry=True
    assert "upstream 503" in failed[0][2]
    assert state.fail_count == 1


@pytest.mark.asyncio
async def test_poll_once_kbs_fatal_calls_fail_with_retry_false(_isolated_data_dir, monkeypatch):
    import worker
    import pms_client
    import kbs_client

    _save_session(monkeypatch)
    failed = []

    async def fake_list_queue(*a, **kw):
        return {"jobs": [{"id": "j1", "payload": {"x": 1}}], "stats": {}}

    async def fake_claim(*a, **kw):
        return {"job": {"id": "j1"}}

    async def fake_fail(url, token, job_id, worker_id, error, retry, **kw):
        failed.append((job_id, retry))
        return {"will_retry": False}

    for mod in (pms_client, worker):
        monkeypatch.setattr(mod, "list_queue", fake_list_queue)
        monkeypatch.setattr(mod, "claim_job", fake_claim)
        monkeypatch.setattr(mod, "fail_job", fake_fail)

    def kbs_fatal(payload, config=None):
        raise kbs_client.KBSFatalError("schema invalid")

    monkeypatch.setattr(worker, "submit_guest", kbs_fatal)

    state = worker.get_state()
    await worker._poll_once(state)

    assert failed == [("j1", False)]


@pytest.mark.asyncio
async def test_poll_once_401_clears_session(_isolated_data_dir, monkeypatch):
    import worker
    import pms_client
    import session

    _save_session(monkeypatch)
    assert session.load_session() is not None

    async def fake_list_queue(*a, **kw):
        raise pms_client.PMSError(status_code=401, detail="token expired")

    monkeypatch.setattr(pms_client, "list_queue", fake_list_queue)
    monkeypatch.setattr(worker, "list_queue", fake_list_queue)

    state = worker.get_state()
    await worker._poll_once(state)

    assert state.session_status == "invalid"
    assert session.load_session() is None


@pytest.mark.asyncio
async def test_poll_once_skips_jobs_not_yet_due(_isolated_data_dir, monkeypatch):
    import worker
    import pms_client

    _save_session(monkeypatch)
    claimed = []

    async def fake_list_queue(*a, **kw):
        return {
            "jobs": [{
                "id": "future",
                "payload": {"x": 1},
                "next_retry_at": "2099-01-01T00:00:00Z",
            }],
            "stats": {},
        }

    async def fake_claim(url, token, job_id, *a, **kw):
        claimed.append(job_id)
        return {"job": {"id": job_id}}

    for mod in (pms_client, worker):
        monkeypatch.setattr(mod, "list_queue", fake_list_queue)
        monkeypatch.setattr(mod, "claim_job", fake_claim)

    state = worker.get_state()
    await worker._poll_once(state)
    assert claimed == []  # didn't claim a job whose next_retry_at is in the future


@pytest.mark.asyncio
async def test_poll_once_skips_409_claim(_isolated_data_dir, monkeypatch):
    import worker
    import pms_client

    _save_session(monkeypatch)

    async def fake_list_queue(*a, **kw):
        return {"jobs": [{"id": "j1", "payload": {}}], "stats": {}}

    async def fake_claim(*a, **kw):
        raise pms_client.PMSError(status_code=409, detail="already taken")

    async def fake_complete(*a, **kw):
        raise AssertionError("must not complete after failed claim")

    for mod in (pms_client, worker):
        monkeypatch.setattr(mod, "list_queue", fake_list_queue)
        monkeypatch.setattr(mod, "claim_job", fake_claim)
        monkeypatch.setattr(mod, "complete_job", fake_complete)

    state = worker.get_state()
    await worker._poll_once(state)
    assert state.claim_count == 0
    assert any(r["outcome"].startswith("skip") for r in state.recent_jobs)


@pytest.mark.asyncio
async def test_sleep_until_event_or_timeout_no_task_leak(_isolated_data_dir):
    """The wait helper must clean up its child tasks every iteration."""
    import worker
    stop = asyncio.Event()
    poll_now = asyncio.Event()

    before = len(asyncio.all_tasks())
    # Stop immediately so wait returns fast
    stop.set()
    await worker._sleep_until_event_or_timeout(stop, poll_now, timeout=5)
    # Give the loop a chance to GC anything pending
    await asyncio.sleep(0)
    after = len(asyncio.all_tasks())
    # Allow the +1 for the test's own task; must not grow further
    assert after <= before + 1


@pytest.mark.asyncio
async def test_sleep_until_event_or_timeout_wakes_on_poll_now(_isolated_data_dir):
    import worker
    import time
    stop = asyncio.Event()
    poll_now = asyncio.Event()
    poll_now.set()

    t0 = time.monotonic()
    await worker._sleep_until_event_or_timeout(stop, poll_now, timeout=10)
    assert time.monotonic() - t0 < 1.0  # didn't wait the full 10s


@pytest.mark.asyncio
async def test_is_due():
    import worker
    assert worker._is_due(None) is True
    assert worker._is_due("") is True
    assert worker._is_due("not-a-date") is True  # bad format → treat as due
    assert worker._is_due("2099-01-01T00:00:00Z") is False
    assert worker._is_due("2000-01-01T00:00:00Z") is True
