"""Shared uvicorn runtime configuration.

Keeps `host`, `port`, log config, and the FastAPI app import in one place so
both the service mode (`backend/service.py`) and the tray/standalone mode
(`backend/__main__.py`) start the server identically.

Bind hardening: defaults to 127.0.0.1 (loopback only). Refuses any non-
loopback host (0.0.0.0, ::, *, LAN IPs, hostnames) with exit(3). There is
no escape hatch — Phase C policy. Operators who need LAN access must put
a reverse proxy in front, not change this binding.
"""
from __future__ import annotations

import logging
import os
import sys

log = logging.getLogger("kbs-bridge.runtime")

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765


_LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}


def _is_loopback(host: str) -> bool:
    """True iff the host is a literal loopback address (no DNS resolution).

    We deliberately do NOT call socket.gethostbyname here — DNS could be
    poisoned to map an arbitrary name to 127.0.0.1, and we want a transparent,
    text-based decision the operator can audit.
    """
    return host.strip().lower() in _LOOPBACK_HOSTS


def _resolved_host() -> str:
    """Return the bind host. STRICT loopback policy — no public bind override.

    Phase C constraint: 0.0.0.0 / LAN IPs / hostnames are forbidden because
    binding outside the loopback exposes the API to the hotel network. There
    is no escape hatch — operators who genuinely need LAN access must put a
    reverse proxy in front, not change this binding.
    """
    host = (os.environ.get("HOST") or DEFAULT_HOST).strip() or DEFAULT_HOST
    if not _is_loopback(host):
        log.error(
            "HOST=%s reddedildi. Yalnizca 127.0.0.1/localhost/::1 izinli; "
            "loopback disindaki bind'lar otel agina aciktir.",
            host,
        )
        sys.exit(3)
    return host


def _resolved_port() -> int:
    try:
        return int(os.environ.get("PORT", str(DEFAULT_PORT)))
    except ValueError:
        log.error("PORT env degeri sayi olmali, %r reddedildi", os.environ.get("PORT"))
        sys.exit(3)


def build_uvicorn_server():
    """Return a uvicorn.Server configured to serve the FastAPI app."""
    import uvicorn

    config = uvicorn.Config(
        "server:app",
        host=_resolved_host(),
        port=_resolved_port(),
        log_config=None,  # we configure logging ourselves (log_setup)
        access_log=False,  # too noisy for production tray; rely on our logs
        loop="asyncio",
    )
    return uvicorn.Server(config)


def run_blocking() -> None:
    """Run uvicorn until shutdown — used by 'server' and 'tray' modes."""
    server = build_uvicorn_server()
    server.run()
