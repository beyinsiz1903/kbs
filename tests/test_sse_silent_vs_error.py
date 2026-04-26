"""Task #11 — SSE drop cause classification (silent vs error).

These tests verify that `_sse_supervisor` keeps two diagnostic counters:
  - `sse_silent_drops`: heartbeat-watchdog timeouts and clean server-side
    EOFs. The TCP socket may have been fine; the stream just went quiet.
  - `sse_error_drops`: real exceptions (connect refused, mid-stream
    RemoteProtocolError, etc.). Something actually failed.

The pre-existing `sse_reconnect_count` rollup is unchanged for backward
compatibility (UI in #8 reads it). The two new fields are additive.

Each test uses a fake `open_stream` so we don't depend on httpx-sse and
can simulate exact failure modes deterministically.
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
async def test_silent_heartbeat_timeout_increments_silent_only(_isolated_data_dir, monkeypatch):
    """Heartbeat watchdog firing must bump `sse_silent_drops`, not error_drops."""
    monkeypatch.setenv("WORKER_MODE", "sse")
    import worker
    monkeypatch.setattr(worker, "SSE_HEARTBEAT_TIMEOUT", 0.05)

    _save_session()
    state = worker.get_state()

    stop = asyncio.Event()
    poll_now = asyncio.Event()
    opens = {"n": 0}

    @asynccontextmanager
    async def silent_then_block(pms_url, token, *, last_event_id=None):
        opens["n"] += 1
        async def gen():
            # First connection: stays totally silent → watchdog must fire.
            # Subsequent reconnects: park forever (test cancels supervisor
            # directly to avoid phantom silent drops on cleanup).
            if opens["n"] == 1:
                await asyncio.sleep(10)
            else:
                await asyncio.Event().wait()
            yield  # unreachable — keeps this an async generator

        yield gen()

    async def fast_sleep(stop_arg, t):
        # Don't burn real time on backoff between iterations.
        await asyncio.sleep(0)

    monkeypatch.setattr(worker, "_sleep_with_stop", fast_sleep)

    sup = asyncio.create_task(
        worker._sse_supervisor(state, stop, poll_now, open_stream=silent_then_block)
    )

    # Wait for the watchdog to fire AND the second open to succeed
    # (proves the silent drop was registered before reconnect).
    for _ in range(200):
        await asyncio.sleep(0.01)
        if state.sse_silent_drops >= 1 and state.sse_connected:
            break

    sup.cancel()
    await asyncio.gather(sup, return_exceptions=True)

    assert state.sse_silent_drops >= 1, "watchdog timeout must bump silent_drops"
    assert state.sse_error_drops == 0, "no exception → error_drops must stay 0"
    # Rollup must also include silent drops for UI backward compatibility.
    assert state.sse_reconnect_count >= 1


@pytest.mark.asyncio
async def test_connect_failure_increments_error_only(_isolated_data_dir, monkeypatch):
    """SSEConnectError before stream opens must bump `sse_error_drops`."""
    monkeypatch.setenv("WORKER_MODE", "sse")
    import worker
    import sse_client

    _save_session()
    state = worker.get_state()

    stop = asyncio.Event()
    poll_now = asyncio.Event()
    attempts = {"n": 0}

    @asynccontextmanager
    async def refusing_stream(pms_url, token, *, last_event_id=None):
        attempts["n"] += 1
        # Simulate "PMS unreachable" — fail before yielding the events
        # iterator, so sse_connected never flips True. error_drops should
        # still increment (it covers pre-connect failures too).
        raise sse_client.SSEConnectError("simulated refused")
        yield  # pragma: no cover

    async def fast_sleep(stop_arg, t):
        if attempts["n"] >= 2:
            stop_arg.set()
        await asyncio.sleep(0)

    monkeypatch.setattr(worker, "_sleep_with_stop", fast_sleep)

    sup = asyncio.create_task(
        worker._sse_supervisor(state, stop, poll_now, open_stream=refusing_stream)
    )
    await asyncio.wait_for(sup, timeout=2)

    assert state.sse_error_drops >= 2, "every connect failure must bump error_drops"
    assert state.sse_silent_drops == 0, "no silent stream → silent_drops must stay 0"
    # Pre-connect failures don't bump reconnect_count (we never had a
    # connection to lose) — that's the documented behavior.
    assert state.sse_reconnect_count == 0


@pytest.mark.asyncio
async def test_midstream_exception_increments_error_only(_isolated_data_dir, monkeypatch):
    """An exception raised after stream open must classify as 'error', not 'silent'."""
    monkeypatch.setenv("WORKER_MODE", "sse")
    import worker
    monkeypatch.setattr(worker, "SSE_HEARTBEAT_TIMEOUT", 5.0)  # don't trip watchdog

    _save_session()
    state = worker.get_state()

    stop = asyncio.Event()
    poll_now = asyncio.Event()
    opens = {"n": 0}

    @asynccontextmanager
    async def crashing_stream(pms_url, token, *, last_event_id=None):
        opens["n"] += 1
        async def gen():
            # First connection: emit one event, then raise mid-stream like a
            # real httpx.RemoteProtocolError would. Subsequent reconnects:
            # park forever (test will cancel the supervisor task directly,
            # avoiding any extra StopAsyncIteration that would be miscounted
            # as a phantom silent drop).
            if opens["n"] == 1:
                yield _ev("heartbeat", "{}")
                raise RuntimeError("simulated mid-stream protocol error")
            else:
                await asyncio.Event().wait()
                yield  # unreachable

        yield gen()

    async def fast_sleep(stop_arg, t):
        await asyncio.sleep(0)

    monkeypatch.setattr(worker, "_sleep_with_stop", fast_sleep)

    sup = asyncio.create_task(
        worker._sse_supervisor(state, stop, poll_now, open_stream=crashing_stream)
    )

    for _ in range(200):
        await asyncio.sleep(0.01)
        if state.sse_error_drops >= 1 and state.sse_connected:
            break

    sup.cancel()
    await asyncio.gather(sup, return_exceptions=True)

    assert state.sse_error_drops >= 1, "mid-stream exception must bump error_drops"
    assert state.sse_silent_drops == 0, "exception path → silent_drops must stay 0"
    # We DID connect before crashing → reconnect_count must have bumped too.
    assert state.sse_reconnect_count >= 1


@pytest.mark.asyncio
async def test_clean_server_eof_classifies_as_silent(_isolated_data_dir, monkeypatch):
    """A stream that ends cleanly (StopAsyncIteration, no exception) is silent."""
    monkeypatch.setenv("WORKER_MODE", "sse")
    import worker
    monkeypatch.setattr(worker, "SSE_HEARTBEAT_TIMEOUT", 5.0)  # don't trip watchdog

    _save_session()
    state = worker.get_state()

    stop = asyncio.Event()
    poll_now = asyncio.Event()
    opens = {"n": 0}

    @asynccontextmanager
    async def closes_cleanly(pms_url, token, *, last_event_id=None):
        opens["n"] += 1
        async def gen():
            if opens["n"] == 1:
                yield _ev("heartbeat", "{}")
                # Generator returns → StopAsyncIteration → 'silent' branch.
                return
            else:
                # Park forever; test will cancel supervisor.
                await asyncio.Event().wait()
                yield  # unreachable

        yield gen()

    async def fast_sleep(stop_arg, t):
        await asyncio.sleep(0)

    monkeypatch.setattr(worker, "_sleep_with_stop", fast_sleep)

    sup = asyncio.create_task(
        worker._sse_supervisor(state, stop, poll_now, open_stream=closes_cleanly)
    )

    for _ in range(200):
        await asyncio.sleep(0.01)
        if state.sse_silent_drops >= 1 and state.sse_connected:
            break

    sup.cancel()
    await asyncio.gather(sup, return_exceptions=True)

    assert state.sse_silent_drops >= 1, "clean EOF must bump silent_drops"
    assert state.sse_error_drops == 0, "no exception → error_drops must stay 0"


def test_to_dict_exposes_split_counters(_isolated_data_dir, monkeypatch):
    """`/api/worker/status` consumers must see both new counters in `sse:{...}`."""
    import worker
    state = worker.WorkerState(worker_id="agent-x", poll_interval=15)
    state.sse_silent_drops = 7
    state.sse_error_drops = 2

    d = state.to_dict()
    assert "silent_drops" in d["sse"], "contract must expose sse.silent_drops"
    assert "error_drops" in d["sse"], "contract must expose sse.error_drops"
    assert d["sse"]["silent_drops"] == 7
    assert d["sse"]["error_drops"] == 2
    # Backward compat: the rollup field must still be present.
    assert "reconnect_count" in d["sse"]
    assert "consecutive_failures" in d["sse"]
