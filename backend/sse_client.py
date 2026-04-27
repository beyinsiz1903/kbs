"""Async SSE client for the PMS `/api/kbs/queue/stream` push endpoint.

Phase D continuation: when the PMS exposes a Server-Sent Events stream the
worker can react to new jobs in 1-2 seconds instead of waiting for the next
15-second poll tick. The SSE stream is a *signal channel only* — every
`job.available` event simply triggers an early poll. The actual claim/process
flow stays identical to polling, so we keep idempotency, atomic claim
semantics, and journal replay unchanged.

Contract: see backend/docs/KBS_SSE_CONTRACT.md v1 (PMS repo).
    GET  {pms_url}/api/kbs/queue/stream
    Headers:
        Authorization: Bearer <access_token>
        Accept:        text/event-stream
        Last-Event-ID: <id>            (optional, for resume after disconnect)
    Events:
        event: job.available
        data:  {"job_id": "...", "tenant_id": "..."}

        event: heartbeat              (server keep-alive; ignored)
        data:  {}

This module ONLY proxies. No retries, no backoff — the supervisor in
`worker.py` owns the reconnect policy so it can also coordinate with the
poll loop in `auto` mode.
"""
from __future__ import annotations

import json
import logging
import os
from contextlib import asynccontextmanager
from typing import AsyncIterator, Optional
from urllib.parse import urlparse

import httpx
from httpx_sse import ServerSentEvent, aconnect_sse

log = logging.getLogger("kbs-bridge.sse")

STREAM_PATH = "/api/kbs/queue/stream"

# Connect/read timeouts. `read=None` is intentional: SSE streams may stay
# silent between heartbeats and we MUST NOT treat that as a timeout. The
# supervisor uses heartbeat absence + reconnect counters to detect deadness.
DEFAULT_TIMEOUT = httpx.Timeout(connect=10.0, read=None, write=10.0, pool=5.0)


class SSEAuthError(Exception):
    """Raised when the PMS rejects the SSE auth (401/403). Supervisor should
    bubble this so the worker can clear the session, exactly like polling does."""


class SSEConnectError(Exception):
    """Raised when the stream cannot be opened (DNS, refused, non-200, etc.).
    Supervisor will back off and retry."""


# Hosts the PMS URL must NEVER point at — same SSRF guard as pms_client.
_FORBIDDEN_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "::1"}


def _validate_pms_url(pms_url: str) -> None:
    try:
        u = urlparse(pms_url)
    except Exception as e:
        raise SSEConnectError(f"PMS URL gecersiz: {e}") from e
    if u.scheme not in ("http", "https") or not u.netloc:
        raise SSEConnectError("PMS URL 'https://...' formatinda olmali")
    host = (u.hostname or "").lower()
    if host in _FORBIDDEN_HOSTS:
        raise SSEConnectError("PMS URL bu bilgisayara isaret ediyor (SSRF guard)")
    # Parity with pms_client: also reject the agent's own public hostname so a
    # poisoned session can't redirect the SSE stream into a local loop. The
    # env var is optional in dev — only enforced when set.
    own_host = os.environ.get("PUBLIC_HOSTNAME", "").lower()
    if own_host and host == own_host:
        raise SSEConnectError("PMS URL bu uygulamanin kendi adresi (SSRF guard)")


@asynccontextmanager
async def open_stream(
    pms_url: str,
    token: str,
    *,
    last_event_id: Optional[str] = None,
    timeout: httpx.Timeout = DEFAULT_TIMEOUT,
) -> AsyncIterator[AsyncIterator[ServerSentEvent]]:
    """Async context manager that yields an async iterator of SSE events.

    Raises SSEAuthError on 401/403 and SSEConnectError on every other
    pre-stream failure. Once the stream is open, network errors during
    iteration propagate as `httpx.RequestError` (the supervisor catches and
    backs off).
    """
    _validate_pms_url(pms_url)
    url = pms_url.rstrip("/") + STREAM_PATH
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "text/event-stream",
        # Some proxies buffer SSE without this hint; harmless if ignored.
        "Cache-Control": "no-cache",
    }
    if last_event_id:
        headers["Last-Event-ID"] = last_event_id

    client = httpx.AsyncClient(timeout=timeout, verify=True, follow_redirects=False)
    try:
        try:
            cm = aconnect_sse(client, "GET", url, headers=headers)
            event_source = await cm.__aenter__()
        except httpx.HTTPStatusError as e:
            sc = e.response.status_code
            if sc in (401, 403):
                raise SSEAuthError(f"SSE auth reddedildi (HTTP {sc})") from e
            raise SSEConnectError(f"SSE acilamadi (HTTP {sc})") from e
        except httpx.RequestError as e:
            raise SSEConnectError(f"SSE baglanti hatasi: {e.__class__.__name__}") from e

        # httpx_sse returns 200 for any successful response, but we still
        # need to defensively check the response code in case the server
        # answered 4xx/5xx without aconnect_sse raising.
        resp = event_source.response
        if resp.status_code in (401, 403):
            await cm.__aexit__(None, None, None)
            raise SSEAuthError(f"SSE auth reddedildi (HTTP {resp.status_code})")
        if resp.status_code >= 400:
            await cm.__aexit__(None, None, None)
            raise SSEConnectError(f"SSE acilamadi (HTTP {resp.status_code})")

        try:
            yield event_source.aiter_sse()
        finally:
            await cm.__aexit__(None, None, None)
    finally:
        await client.aclose()


def parse_event_data(event: ServerSentEvent) -> dict:
    """Parse SSE `data:` payload as JSON. Returns {} if blank or invalid.

    We never raise here — a malformed event from a future PMS version should
    NOT take down the worker. The supervisor logs and ignores unknown shapes.
    """
    raw = (event.data or "").strip()
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, ValueError) as e:
        log.warning("SSE data JSON parse hatasi: %s", e)
        return {}
    if not isinstance(parsed, dict):
        log.warning("SSE data dict degil: %r", type(parsed).__name__)
        return {}
    return parsed
