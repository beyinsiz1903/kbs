"""Unit tests for backend/sse_client.py.

We spin up a minimal aiohttp.web SSE server on a free localhost port, then
connect via the real httpx-sse client. This exercises the wire format end
to end (event:, data:, id:, multi-line, blank-line framing) instead of
mocking the parser.

The SSE client validates the PMS URL with the same SSRF guard as
pms_client; loopback hosts are normally rejected. Tests temporarily allow
loopback by patching the forbidden-hosts set so we can talk to 127.0.0.1.
"""
import asyncio
import json

import pytest
from aiohttp import web

import sse_client


@pytest.fixture
def _allow_loopback(monkeypatch):
    """Drop loopback from the SSRF block-list for tests only."""
    monkeypatch.setattr(sse_client, "_FORBIDDEN_HOSTS", set())


async def _start_sse_server(handler) -> tuple[str, web.AppRunner]:
    """Start an aiohttp app on a random local port; return (base_url, runner)."""
    app = web.Application()
    app.router.add_get(sse_client.STREAM_PATH, handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]
    return f"http://127.0.0.1:{port}", runner


async def _stop(runner: web.AppRunner) -> None:
    await runner.cleanup()


@pytest.mark.asyncio
async def test_open_stream_reads_new_job_event(_allow_loopback):
    captured_auth: list[str] = []

    async def handler(request: web.Request) -> web.StreamResponse:
        captured_auth.append(request.headers.get("Authorization", ""))
        resp = web.StreamResponse(status=200, headers={
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-cache",
        })
        await resp.prepare(request)
        await resp.write(
            b"event: new_job\n"
            b'data: {"job_id": "j-1", "tenant_id": "h1"}\n'
            b"id: 1\n\n"
        )
        await resp.write_eof()
        return resp

    base_url, runner = await _start_sse_server(handler)
    try:
        events = []
        async with sse_client.open_stream(base_url, "tok-xyz") as stream:
            async for ev in stream:
                events.append(ev)
        assert captured_auth == ["Bearer tok-xyz"]
        assert len(events) == 1
        assert events[0].event == "new_job"
        assert events[0].id == "1"
        assert sse_client.parse_event_data(events[0]) == {
            "job_id": "j-1", "tenant_id": "h1",
        }
    finally:
        await _stop(runner)


@pytest.mark.asyncio
async def test_open_stream_sends_last_event_id_on_resume(_allow_loopback):
    captured: dict[str, str | None] = {}

    async def handler(request: web.Request) -> web.StreamResponse:
        captured["last_event_id"] = request.headers.get("Last-Event-ID")
        resp = web.StreamResponse(status=200, headers={
            "Content-Type": "text/event-stream",
        })
        await resp.prepare(request)
        await resp.write(b"event: heartbeat\ndata: {}\n\n")
        await resp.write_eof()
        return resp

    base_url, runner = await _start_sse_server(handler)
    try:
        async with sse_client.open_stream(base_url, "tok", last_event_id="42") as stream:
            async for _ in stream:
                pass
        assert captured["last_event_id"] == "42"
    finally:
        await _stop(runner)


@pytest.mark.asyncio
async def test_open_stream_401_raises_auth_error(_allow_loopback):
    async def handler(request: web.Request) -> web.Response:
        return web.Response(status=401, text="bad token")

    base_url, runner = await _start_sse_server(handler)
    try:
        with pytest.raises(sse_client.SSEAuthError):
            async with sse_client.open_stream(base_url, "bad") as stream:
                async for _ in stream:
                    pass
    finally:
        await _stop(runner)


@pytest.mark.asyncio
async def test_open_stream_503_raises_connect_error(_allow_loopback):
    async def handler(request: web.Request) -> web.Response:
        return web.Response(status=503, text="upstream down")

    base_url, runner = await _start_sse_server(handler)
    try:
        with pytest.raises(sse_client.SSEConnectError):
            async with sse_client.open_stream(base_url, "tok") as stream:
                async for _ in stream:
                    pass
    finally:
        await _stop(runner)


@pytest.mark.asyncio
async def test_open_stream_refuses_loopback_url():
    """Without the test override, loopback PMS URL is rejected (SSRF guard)."""
    with pytest.raises(sse_client.SSEConnectError):
        async with sse_client.open_stream("http://127.0.0.1:1", "tok") as stream:
            async for _ in stream:
                pass


@pytest.mark.asyncio
async def test_open_stream_refuses_own_public_hostname(monkeypatch):
    """PUBLIC_HOSTNAME match is rejected (parity with pms_client)."""
    monkeypatch.setenv("PUBLIC_HOSTNAME", "agent.hotel.local")
    with pytest.raises(sse_client.SSEConnectError, match="kendi adresi"):
        async with sse_client.open_stream(
            "https://agent.hotel.local", "tok",
        ) as stream:
            async for _ in stream:
                pass


@pytest.mark.asyncio
async def test_parse_event_data_handles_garbage(_allow_loopback):
    """Malformed data must not raise — supervisor relies on this."""
    class _Fake:
        data = "not json"
        event = "new_job"
        id = None

    assert sse_client.parse_event_data(_Fake()) == {}

    class _Empty:
        data = ""
        event = "new_job"
        id = None

    assert sse_client.parse_event_data(_Empty()) == {}

    class _ListPayload:
        data = "[1, 2, 3]"  # valid JSON but not a dict
        event = "new_job"
        id = None

    assert sse_client.parse_event_data(_ListPayload()) == {}
