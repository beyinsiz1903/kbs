"""Phase D — WORKER_MODE policy.

`poll` (default) and `auto` start normally. `sse` is reserved for a future
PMS push endpoint and refuses loudly. Anything else also refuses.
"""
import asyncio

import pytest

import worker


@pytest.fixture
def _reset():
    worker._state = None
    worker._task = None
    worker._stop_event = None
    worker._poll_now_event = None
    yield
    worker._state = None
    worker._task = None


@pytest.mark.asyncio
async def test_poll_mode_starts(_reset, monkeypatch):
    monkeypatch.setenv("WORKER_MODE", "poll")
    started = asyncio.Event()

    async def fake_loop(state, stop, poll_now):
        started.set()
        await stop.wait()

    worker.start(loop_factory=fake_loop)
    await asyncio.wait_for(started.wait(), timeout=1)
    await worker.stop()


@pytest.mark.asyncio
async def test_auto_mode_starts(_reset, monkeypatch):
    """`auto` should fall back to poll until SSE is available."""
    monkeypatch.setenv("WORKER_MODE", "auto")
    started = asyncio.Event()

    async def fake_loop(state, stop, poll_now):
        started.set()
        await stop.wait()

    worker.start(loop_factory=fake_loop)
    await asyncio.wait_for(started.wait(), timeout=1)
    await worker.stop()


@pytest.mark.asyncio
async def test_sse_mode_refuses(_reset, monkeypatch):
    monkeypatch.setenv("WORKER_MODE", "sse")
    monkeypatch.setenv("KBS_MODE", "simulation")

    async def fake_loop(state, stop, poll_now):  # pragma: no cover - should not start
        raise AssertionError("loop must NOT start in sse mode")

    worker.start(loop_factory=fake_loop)
    state = worker.get_state()
    assert state.session_status == "refused"
    assert state.running is False
    assert "WORKER_MODE=sse henuz desteklenmiyor" in (state.last_error or "")


@pytest.mark.asyncio
async def test_unknown_mode_refuses(_reset, monkeypatch):
    monkeypatch.setenv("WORKER_MODE", "garbage")

    async def fake_loop(state, stop, poll_now):  # pragma: no cover
        raise AssertionError("loop must NOT start with unknown mode")

    worker.start(loop_factory=fake_loop)
    state = worker.get_state()
    assert state.session_status == "refused"
    assert state.running is False
    assert "garbage" in (state.last_error or "")
