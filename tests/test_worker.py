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
    assert s["counters"] == {"claim": 0, "complete": 0, "fail": 0, "replay": 0}
    # Flat SSE field aliases (task-7 contract) — must exist alongside nested.
    assert "sse_connected" in s and s["sse_connected"] is False
    assert "sse_last_event_at" in s and s["sse_last_event_at"] is None
    assert "sse_reconnect_count" in s and s["sse_reconnect_count"] == 0
    assert "sse" in s and set(s["sse"].keys()) == {
        "connected", "last_event_at", "reconnect_count", "consecutive_failures",
    }
    # Flat and nested views must agree.
    assert s["sse_connected"] == s["sse"]["connected"]
    assert s["sse_last_event_at"] == s["sse"]["last_event_at"]
    assert s["sse_reconnect_count"] == s["sse"]["reconnect_count"]


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
async def test_journal_appends_records(_isolated_data_dir):
    """journal.append must persist line-delimited JSON to DATA_DIR."""
    import journal
    journal.append("claim", job_id="job-1", worker_id="agent-x")
    journal.append("complete", job_id="job-1", kbs_reference="REF-9")
    records = journal.tail(10)
    assert len(records) == 2
    assert records[0]["event"] == "claim"
    assert records[0]["job_id"] == "job-1"
    assert records[1]["event"] == "complete"
    assert records[1]["kbs_reference"] == "REF-9"
    assert "ts" in records[0]


@pytest.mark.asyncio
async def test_complete_writes_pending_then_ack_journal_pair(_isolated_data_dir, monkeypatch):
    """Successful job must journal pending_complete BEFORE PMS, then complete_ack."""
    import worker
    import journal
    import pms_client

    _save_session(monkeypatch)

    async def fake_list_queue(*a, **kw):
        return {"jobs": [{"id": "J", "payload": {"x": 1}}], "stats": {}}

    async def fake_claim(*a, **kw):
        return {"job": {"id": "J"}}

    async def fake_complete(url, token, job_id, worker_id, kbs_reference, **kw):
        # Idempotency-Key MUST be passed through
        assert kw.get("idem_key"), "complete_job called without idem_key"
        return {"job": {"id": job_id, "status": "done"}}

    for mod in (pms_client, worker):
        monkeypatch.setattr(mod, "list_queue", fake_list_queue)
        monkeypatch.setattr(mod, "claim_job", fake_claim)
        monkeypatch.setattr(mod, "complete_job", fake_complete)
    monkeypatch.setattr(worker, "submit_guest", lambda payload, config=None: "REF-OK")

    await worker._poll_once(worker.get_state())

    events = [r["event"] for r in journal.tail(50)]
    assert "pending_complete" in events
    assert "complete_ack" in events
    # pending_complete must come BEFORE complete_ack
    assert events.index("pending_complete") < events.index("complete_ack")
    # No leftover unacked entries
    assert journal.find_unacked() == []


@pytest.mark.asyncio
async def test_idem_keys_stable_within_lifecycle(_isolated_data_dir, monkeypatch):
    """Worker MUST send the same persisted Idempotency-Key for both claim and
    complete of a job; cleanup runs only after the terminal complete_ack."""
    import worker
    import idem
    import pms_client

    _save_session(monkeypatch)
    # Snapshot what idem would generate so we can assert worker passes the same.
    expected_claim = idem.get_or_create("STABLE", "claim")
    expected_complete = idem.get_or_create("STABLE", "complete")
    captured: dict[str, str] = {}

    async def fake_list_queue(*a, **kw):
        return {"jobs": [{"id": "STABLE", "payload": {"x": 1}}], "stats": {}}

    async def fake_claim(url, token, job_id, worker_id, **kw):
        captured["claim"] = kw.get("idem_key")
        return {"job": {"id": job_id}}

    async def fake_complete(url, token, job_id, worker_id, ref, **kw):
        captured["complete"] = kw.get("idem_key")
        return {"job": {"id": job_id}}

    for mod in (pms_client, worker):
        monkeypatch.setattr(mod, "list_queue", fake_list_queue)
        monkeypatch.setattr(mod, "claim_job", fake_claim)
        monkeypatch.setattr(mod, "complete_job", fake_complete)
    monkeypatch.setattr(worker, "submit_guest", lambda p, c=None: "REF")

    await worker._poll_once(worker.get_state())

    assert captured["claim"] == expected_claim
    assert captured["complete"] == expected_complete
    assert captured["claim"] != captured["complete"]
    assert "STABLE" not in idem.list_jobs()  # cleaned after complete_ack


@pytest.mark.asyncio
async def test_replay_resends_unacked_complete(_isolated_data_dir, monkeypatch):
    """A pending_complete left over from a crash must be replayed on next poll."""
    import worker
    import journal
    import idem
    import pms_client

    _save_session(monkeypatch)

    # Seed the journal as if we crashed mid-complete
    journal.append("pending_complete", job_id="ghost", kbs_reference="REF-GHOST")
    # Pre-create the idem key so replay reuses it (matches real flow)
    pre_key = idem.get_or_create("ghost", "complete")

    replayed = []

    async def fake_list_queue(*a, **kw):
        return {"jobs": [], "stats": {}}

    async def fake_complete(url, token, job_id, worker_id, ref, **kw):
        replayed.append((job_id, ref, kw.get("idem_key")))
        return {"job": {"id": job_id, "status": "done"}}

    for mod in (pms_client, worker):
        monkeypatch.setattr(mod, "list_queue", fake_list_queue)
        monkeypatch.setattr(mod, "complete_job", fake_complete)

    state = worker.get_state()
    await worker._poll_once(state)

    assert replayed == [("ghost", "REF-GHOST", pre_key)]
    assert state.replay_count == 1
    # Journal now has a complete_ack → no longer unacked
    assert journal.find_unacked() == []
    # Idem keys for ghost cleaned up
    assert "ghost" not in idem.list_jobs()


@pytest.mark.asyncio
async def test_replay_pending_fail_success(_isolated_data_dir, monkeypatch):
    """A pending_fail left over from a crash must be replayed via fail_job."""
    import worker
    import journal
    import idem
    import pms_client

    _save_session(monkeypatch)
    journal.append("pending_fail", job_id="badjob", retry=False, error="schema oops")

    called = []

    async def fake_list_queue(*a, **kw):
        return {"jobs": [], "stats": {}}

    async def fake_fail(url, token, job_id, worker_id, error, retry, **kw):
        called.append({"job_id": job_id, "error": error, "retry": retry, "key": kw.get("idem_key")})
        return {"will_retry": False}

    for mod in (pms_client, worker):
        monkeypatch.setattr(mod, "list_queue", fake_list_queue)
        monkeypatch.setattr(mod, "fail_job", fake_fail)

    state = worker.get_state()
    await worker._poll_once(state)

    assert len(called) == 1 and called[0]["job_id"] == "badjob"
    assert called[0]["retry"] is False
    assert called[0]["key"]
    assert journal.find_unacked() == []
    assert "badjob" not in idem.list_jobs()  # cleaned: will_retry=False


@pytest.mark.asyncio
async def test_replay_401_clears_session(_isolated_data_dir, monkeypatch):
    """A 401 during replay must clear session and mark it invalid."""
    import worker
    import journal
    import session
    import pms_client

    _save_session(monkeypatch)
    journal.append("pending_complete", job_id="g", kbs_reference="R")
    assert session.load_session() is not None

    async def fake_list_queue(*a, **kw):
        return {"jobs": [], "stats": {}}

    async def fake_complete(*a, **kw):
        raise pms_client.PMSError(status_code=401, detail="token gone")

    for mod in (pms_client, worker):
        monkeypatch.setattr(mod, "list_queue", fake_list_queue)
        monkeypatch.setattr(mod, "complete_job", fake_complete)

    state = worker.get_state()
    await worker._poll_once(state)

    assert state.session_status == "invalid"
    assert session.load_session() is None
    # The pending_complete is still unacked (we never got an ack), so a future
    # session will replay it.
    assert len(journal.find_unacked()) == 1


@pytest.mark.asyncio
async def test_replay_retries_unresolved_on_next_poll(_isolated_data_dir, monkeypatch):
    """If replay hits transient PMS 5xx, next poll must retry — not silently strand."""
    import worker
    import journal
    import pms_client

    _save_session(monkeypatch)
    journal.append("pending_complete", job_id="flaky", kbs_reference="RX")

    call_count = {"n": 0}

    async def fake_list_queue(*a, **kw):
        return {"jobs": [], "stats": {}}

    async def fake_complete(*a, **kw):
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise pms_client.PMSError(status_code=503, detail="upstream down")
        return {"job": {"id": "flaky", "status": "done"}}

    for mod in (pms_client, worker):
        monkeypatch.setattr(mod, "list_queue", fake_list_queue)
        monkeypatch.setattr(mod, "complete_job", fake_complete)

    state = worker.get_state()
    # First poll — replay hits 503 → entry stays unacked, _last_replayed_token NOT set
    await worker._poll_once(state)
    assert call_count["n"] == 1
    assert len(journal.find_unacked()) == 1
    assert state._last_replayed_token is None  # not marked done yet

    # Second poll — replay runs AGAIN and succeeds
    await worker._poll_once(state)
    assert call_count["n"] == 2
    assert journal.find_unacked() == []
    assert state._last_replayed_token is not None  # now marked done


@pytest.mark.asyncio
async def test_replay_409_treated_as_already_done(_isolated_data_dir, monkeypatch):
    """If PMS replies 409 to a replayed complete, treat as already-done."""
    import worker
    import journal
    import pms_client

    _save_session(monkeypatch)
    journal.append("pending_complete", job_id="dup", kbs_reference="X")

    async def fake_list_queue(*a, **kw):
        return {"jobs": [], "stats": {}}

    async def fake_complete(*a, **kw):
        raise pms_client.PMSError(status_code=409, detail="already done")

    for mod in (pms_client, worker):
        monkeypatch.setattr(mod, "list_queue", fake_list_queue)
        monkeypatch.setattr(mod, "complete_job", fake_complete)

    state = worker.get_state()
    await worker._poll_once(state)
    assert state.replay_count == 1
    assert journal.find_unacked() == []


@pytest.mark.asyncio
async def test_real_mode_refuses_to_start_without_wsdl(_isolated_data_dir, monkeypatch):
    """KBS_MODE=real + missing KBS_WSDL_URL → worker refuses to start, no fake refs."""
    import sys
    monkeypatch.setenv("KBS_MODE", "real")
    monkeypatch.delenv("KBS_WSDL_URL", raising=False)
    # Reload worker to pick up the new env
    if "worker" in sys.modules:
        del sys.modules["worker"]
    import worker
    worker._state = None
    worker._task = None

    worker.start()
    state = worker.get_state()
    assert state.session_status == "refused"
    assert state.running is False
    assert "KBS_WSDL_URL" in (state.last_error or "")
    # The polling task must not have been scheduled
    assert worker._task is None


@pytest.mark.asyncio
async def test_real_mode_refuses_processing_until_soap_implemented(_isolated_data_dir, monkeypatch):
    """KBS_MODE=real + complete config + flag off → refuse, do NOT call fail_job.

    This is the data-loss guard: while is_real_ready() is False, we must not
    let _send_real raise KBSConfigError → fail_job(retry=False) → dead-letter.
    """
    import sys
    monkeypatch.setenv("KBS_MODE", "real")
    monkeypatch.setenv("KBS_WSDL_URL", "file:///fake.wsdl")
    if "worker" in sys.modules:
        del sys.modules["worker"]
    import worker
    import session
    import kbs_client
    import pms_client
    worker._state = None

    # Sanity: SOAP is NOT implemented yet
    assert kbs_client.is_real_ready() is False

    # Save session with FULL kbs_* config — looks ready, but flag says no
    session.save_session({
        "pms_url": "https://pms.x.com",
        "access_token": "tok",
        "user": {"email": "u@x", "tenant_id": "h1"},
        "hotel_id": "h1",
        "kbs_tesis_kodu": "12345",
        "kbs_kullanici_adi": "kbs_user",
        "kbs_sifre": "kbs_pw",
        "kbs_servis_url": "https://kbs.gov.tr/svc",
        "kbs_kurum": "polis",
    })

    async def must_not_call(*a, **kw):
        raise AssertionError("worker must NOT call PMS while SOAP unimplemented")

    for mod in (pms_client, worker):
        monkeypatch.setattr(mod, "list_queue", must_not_call)
        monkeypatch.setattr(mod, "claim_job", must_not_call)
        monkeypatch.setattr(mod, "complete_job", must_not_call)
        monkeypatch.setattr(mod, "fail_job", must_not_call)

    state = worker.get_state()
    await worker._poll_once(state)
    assert state.session_status == "kbs_not_ready"
    assert "henuz aktif degil" in (state.last_error or "").lower()
    assert state.fail_count == 0  # CRITICAL: no dead-lettering happened


@pytest.mark.asyncio
async def test_real_mode_skips_polling_when_session_kbs_incomplete(_isolated_data_dir, monkeypatch):
    """KBS_MODE=real + SOAP ready but session missing kbs_kurum etc → status=kbs_not_configured."""
    import sys
    monkeypatch.setenv("KBS_MODE", "real")
    monkeypatch.setenv("KBS_WSDL_URL", "file:///fake.wsdl")
    if "worker" in sys.modules:
        del sys.modules["worker"]
    import worker
    import kbs_client
    # Pretend Phase B is activated for this test
    monkeypatch.setattr(kbs_client, "REAL_SOAP_IMPLEMENTED", True)
    monkeypatch.setattr(worker, "is_real_ready", lambda: True)
    worker._state = None

    _save_session(monkeypatch)  # session WITHOUT kbs_* fields

    state = worker.get_state()
    await worker._poll_once(state)
    assert state.session_status == "kbs_not_configured"
    assert "kbs_tesis_kodu" in (state.last_error or "")


@pytest.mark.asyncio
async def test_is_due():
    import worker
    assert worker._is_due(None) is True
    assert worker._is_due("") is True
    assert worker._is_due("not-a-date") is True  # bad format → treat as due
    assert worker._is_due("2099-01-01T00:00:00Z") is False
    assert worker._is_due("2000-01-01T00:00:00Z") is True
