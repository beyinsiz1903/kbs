"""Phase D follow-up — SSE supervisor inside the worker.

These tests exercise `_sse_supervisor` directly with a fake `open_stream`
context manager so we don't depend on httpx-sse or aiohttp here. The
supervisor is the part that:
  - triggers `poll_now` on every `job.available` event
  - reconnects with exponential backoff on disconnect
  - in `auto` mode, idles after 3 consecutive failures so the poll loop
    can carry the load
  - clears the session on SSEAuthError (matches polling 401 behavior)

Note: `worker` is imported INSIDE each test (not at module top) because
conftest reloads the module per-test under a fresh DATA_DIR. A top-level
import would freeze a stale reference.
"""
import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest


def _save_session():
    import session
    session.save_session({
        "pms_url": "https://pms.x.com",
        "access_token": "tok-1",
        "user": {"email": "u@x", "tenant_id": "h1"},
        "hotel_id": "h1",
    })


def _ev(event_type: str, data: str = "{}", id_: str | None = None) -> SimpleNamespace:
    return SimpleNamespace(event=event_type, data=data, id=id_)


@pytest.mark.asyncio
async def test_sse_event_triggers_poll_now(_isolated_data_dir, monkeypatch):
    """A `job.available` SSE event must set the poll_now event so the loop wakes."""
    monkeypatch.setenv("WORKER_MODE", "sse")
    import worker
    _save_session()
    state = worker.get_state()
    stop = asyncio.Event()
    poll_now = asyncio.Event()

    @asynccontextmanager
    async def fake_open_stream(pms_url, token, *, last_event_id=None):
        async def gen():
            yield _ev("job.available", '{"job_id": "j-1"}', id_="1")
            # Keep the stream open until the test cancels us so the
            # supervisor doesn't tear down + reconnect mid-test.
            await stop.wait()

        yield gen()

    sup = asyncio.create_task(
        worker._sse_supervisor(state, stop, poll_now, open_stream=fake_open_stream)
    )

    await asyncio.wait_for(poll_now.wait(), timeout=2)
    assert state.sse_connected is True
    assert state.sse_last_event_at is not None
    assert state.sse_consecutive_failures == 0

    stop.set()
    await asyncio.gather(sup, return_exceptions=True)
    assert state.sse_connected is False


@pytest.mark.asyncio
async def test_sse_reconnects_with_backoff(_isolated_data_dir, monkeypatch):
    """When the stream EOFs, supervisor must reconnect; backoff stays in [1, 30]."""
    monkeypatch.setenv("WORKER_MODE", "sse")
    import worker
    _save_session()
    state = worker.get_state()

    sleeps: list[float] = []

    async def fast_sleep(stop, t):
        sleeps.append(t)
        await asyncio.sleep(0)

    monkeypatch.setattr(worker, "_sleep_with_stop", fast_sleep)

    attempts = {"n": 0}
    stop = asyncio.Event()
    poll_now = asyncio.Event()

    @asynccontextmanager
    async def flaky_open(pms_url, token, *, last_event_id=None):
        attempts["n"] += 1

        async def gen():
            # One heartbeat then EOF — supervisor should treat this as a
            # disconnect and back off.
            yield _ev("heartbeat", "{}")

        yield gen()

    sup = asyncio.create_task(
        worker._sse_supervisor(state, stop, poll_now, open_stream=flaky_open)
    )

    # Let it cycle a few times then stop.
    for _ in range(80):
        await asyncio.sleep(0)
        if attempts["n"] >= 4:
            break

    stop.set()
    await asyncio.gather(sup, return_exceptions=True)

    assert attempts["n"] >= 4, f"expected >=4 attempts, got {attempts['n']}"
    # Each successful connect resets the backoff to 1s; since these "succeed"
    # then EOF immediately, every cycle starts at 1s.
    assert all(1.0 <= s <= 30.0 for s in sleeps if s > 0), sleeps
    # sse_reconnect_count tracks completed disconnects after an OK connect.
    assert state.sse_reconnect_count >= 3


@pytest.mark.asyncio
async def test_sse_auth_error_clears_session(_isolated_data_dir, monkeypatch):
    """SSEAuthError → session cleared, status=invalid (matches polling 401)."""
    monkeypatch.setenv("WORKER_MODE", "sse")
    import worker
    import sse_client
    _save_session()
    import session
    assert session.load_session() is not None

    state = worker.get_state()
    stop = asyncio.Event()
    poll_now = asyncio.Event()

    async def no_sleep(stop_arg, t):
        # After the session is cleared, the next loop sees no session and
        # would idle 5s; we cancel the supervisor instead.
        if session.load_session() is None:
            stop_arg.set()
        await asyncio.sleep(0)

    monkeypatch.setattr(worker, "_sleep_with_stop", no_sleep)

    @asynccontextmanager
    async def auth_fail(pms_url, token, *, last_event_id=None):
        raise sse_client.SSEAuthError("401")
        yield  # pragma: no cover - unreachable

    sup = asyncio.create_task(
        worker._sse_supervisor(state, stop, poll_now, open_stream=auth_fail)
    )
    await asyncio.wait_for(sup, timeout=2)

    assert session.load_session() is None
    assert state.session_status == "invalid"


@pytest.mark.asyncio
async def test_auto_mode_idles_after_three_failures(_isolated_data_dir, monkeypatch):
    """In `auto` mode, after 3 consecutive failures we wait the LONG idle
    interval, not the short backoff, so the poll loop carries the load."""
    monkeypatch.setenv("WORKER_MODE", "auto")
    import worker
    import sse_client
    _save_session()
    state = worker.get_state()
    assert state.worker_mode == "auto"

    sleeps: list[float] = []
    stop = asyncio.Event()
    poll_now = asyncio.Event()

    async def record_sleep(stop_arg, t):
        sleeps.append(t)
        if t >= worker.SSE_AUTO_RETRY_INTERVAL:
            stop_arg.set()
        await asyncio.sleep(0)

    monkeypatch.setattr(worker, "_sleep_with_stop", record_sleep)

    @asynccontextmanager
    async def always_fail(pms_url, token, *, last_event_id=None):
        raise sse_client.SSEConnectError("refused")
        yield  # pragma: no cover

    sup = asyncio.create_task(
        worker._sse_supervisor(state, stop, poll_now, open_stream=always_fail)
    )
    await asyncio.wait_for(sup, timeout=2)

    # Failures 1 and 2 use exponential backoff (1s, 2s); failure 3 trips
    # the auto threshold and we wait the long idle interval instead.
    short_backoffs = [s for s in sleeps if 0 < s < worker.SSE_AUTO_RETRY_INTERVAL]
    assert len(short_backoffs) == 2, f"expected exactly 2 short backoffs, got {sleeps}"
    assert short_backoffs == [1.0, 2.0], f"expected [1, 2], got {short_backoffs}"
    assert worker.SSE_AUTO_RETRY_INTERVAL in sleeps, (
        f"expected auto fallback idle in {sleeps}"
    )


@pytest.mark.asyncio
async def test_sse_silent_stream_triggers_heartbeat_watchdog(
    _isolated_data_dir, monkeypatch,
):
    """A stream that connects but then sends NOTHING (no events, no
    heartbeats) for SSE_HEARTBEAT_TIMEOUT seconds must be torn down and
    reconnected. Without this, the supervisor would happily report
    `sse_connected=true` for hours while operators silently fall back to
    the 15s poll loop and lose the push advantage.
    """
    monkeypatch.setenv("WORKER_MODE", "sse")
    import worker

    # Tiny timeout so the test runs in milliseconds, not minutes. The
    # supervisor reads the module global at call time, so monkeypatching
    # `worker.SSE_HEARTBEAT_TIMEOUT` is sufficient.
    monkeypatch.setattr(worker, "SSE_HEARTBEAT_TIMEOUT", 0.05)

    sleeps: list[float] = []

    async def fast_sleep(stop_arg, t):
        sleeps.append(t)
        await asyncio.sleep(0)

    monkeypatch.setattr(worker, "_sleep_with_stop", fast_sleep)

    _save_session()
    state = worker.get_state()

    attempts = {"n": 0}
    stop = asyncio.Event()
    poll_now = asyncio.Event()

    @asynccontextmanager
    async def silent_stream(pms_url, token, *, last_event_id=None):
        attempts["n"] += 1

        async def gen():
            # Open the stream but never emit anything — simulates a NAT/proxy
            # that holds the TCP socket open but swallows server events.
            await asyncio.sleep(60)
            yield  # pragma: no cover - unreachable

        yield gen()

    sup = asyncio.create_task(
        worker._sse_supervisor(state, stop, poll_now, open_stream=silent_stream)
    )

    # Wait for at least 2 silent-disconnect cycles so we can prove the
    # watchdog is repeatable, not a one-shot.
    for _ in range(200):
        await asyncio.sleep(0.01)
        if state.sse_reconnect_count >= 2 and attempts["n"] >= 2:
            break

    stop.set()
    await asyncio.gather(sup, return_exceptions=True)

    assert attempts["n"] >= 2, (
        f"watchdog should force reconnect; got only {attempts['n']} attempt(s)"
    )
    assert state.sse_reconnect_count >= 2, (
        f"sse_reconnect_count should increment on each silent disconnect, "
        f"got {state.sse_reconnect_count}"
    )
    assert state.sse_connected is False


@pytest.mark.asyncio
async def test_sse_heartbeat_resets_watchdog(_isolated_data_dir, monkeypatch):
    """A stream that DOES send periodic heartbeats (faster than the watchdog
    timeout) must NOT be considered silent — the watchdog only fires on
    actual silence."""
    monkeypatch.setenv("WORKER_MODE", "sse")
    import worker

    monkeypatch.setattr(worker, "SSE_HEARTBEAT_TIMEOUT", 0.2)

    _save_session()
    state = worker.get_state()

    stop = asyncio.Event()
    poll_now = asyncio.Event()
    beats = {"n": 0}

    @asynccontextmanager
    async def beating_stream(pms_url, token, *, last_event_id=None):
        async def gen():
            # Emit heartbeats faster than the watchdog timeout. If the
            # watchdog incorrectly counted heartbeats as silence, the
            # stream would tear down before we reach the target count.
            for _ in range(10):
                await asyncio.sleep(0.02)
                beats["n"] += 1
                yield _ev("heartbeat", "{}")
            await stop.wait()

        yield gen()

    sup = asyncio.create_task(
        worker._sse_supervisor(state, stop, poll_now, open_stream=beating_stream)
    )

    for _ in range(200):
        await asyncio.sleep(0.01)
        if beats["n"] >= 5:
            break

    assert beats["n"] >= 5
    assert state.sse_connected is True
    assert state.sse_reconnect_count == 0
    assert state.sse_last_event_at is not None

    stop.set()
    await asyncio.gather(sup, return_exceptions=True)


@pytest.mark.asyncio
async def test_sse_supervisor_waits_when_no_session(_isolated_data_dir, monkeypatch):
    """No session → supervisor must idle politely without opening the stream."""
    monkeypatch.setenv("WORKER_MODE", "sse")
    import worker
    state = worker.get_state()
    stop = asyncio.Event()
    poll_now = asyncio.Event()
    opened = {"n": 0, "sleep": 0}

    async def no_sleep(stop_arg, t):
        opened["sleep"] += 1
        if opened["sleep"] >= 2:
            stop_arg.set()
        await asyncio.sleep(0)

    monkeypatch.setattr(worker, "_sleep_with_stop", no_sleep)

    @asynccontextmanager
    async def must_not_open(pms_url, token, *, last_event_id=None):
        opened["n"] += 1
        raise AssertionError("must NOT open stream without a session")
        yield  # pragma: no cover

    sup = asyncio.create_task(
        worker._sse_supervisor(state, stop, poll_now, open_stream=must_not_open)
    )
    await asyncio.wait_for(sup, timeout=2)
    assert opened["n"] == 0


@pytest.mark.asyncio
async def test_loop_spawns_sse_supervisor_in_sse_mode(_isolated_data_dir, monkeypatch):
    """End-to-end: starting the worker in `sse` mode launches the supervisor
    task alongside the poll loop, and stop() tears both down cleanly."""
    monkeypatch.setenv("WORKER_MODE", "sse")
    import worker
    _save_session()

    sup_started = asyncio.Event()

    async def fake_supervisor(state, stop, poll_now, open_stream=None):
        sup_started.set()
        await stop.wait()

    monkeypatch.setattr(worker, "_sse_supervisor", fake_supervisor)

    async def noop_poll(state):
        state.last_poll_ok = True

    monkeypatch.setattr(worker, "_poll_once", noop_poll)

    worker.start()
    await asyncio.wait_for(sup_started.wait(), timeout=2)
    await worker.stop()


@pytest.mark.asyncio
async def test_loop_skips_sse_supervisor_in_poll_mode(_isolated_data_dir, monkeypatch):
    """`poll` mode must NOT spawn the SSE supervisor."""
    monkeypatch.setenv("WORKER_MODE", "poll")
    import worker
    _save_session()

    spawned = {"n": 0}

    async def fake_supervisor(state, stop, poll_now, open_stream=None):  # pragma: no cover
        spawned["n"] += 1
        await stop.wait()

    monkeypatch.setattr(worker, "_sse_supervisor", fake_supervisor)

    async def noop_poll(state):
        state.last_poll_ok = True

    monkeypatch.setattr(worker, "_poll_once", noop_poll)

    worker.start()
    await asyncio.sleep(0.05)
    await worker.stop()
    assert spawned["n"] == 0
