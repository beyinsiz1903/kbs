"""Shared uvicorn runtime configuration.

Keeps `host`, `port`, log config, and the FastAPI app import in one place so
both the service mode (`backend/service.py`) and the tray/standalone mode
(`backend/__main__.py`) start the server identically.

Bind hardening: defaults to 127.0.0.1 (loopback only). Refuses 0.0.0.0
unless the operator explicitly passes `KBS_ALLOW_PUBLIC_BIND=1` — protects
against accidentally exposing the API to the hotel LAN.
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
    host = (os.environ.get("HOST") or DEFAULT_HOST).strip() or DEFAULT_HOST
    if not _is_loopback(host):
        if os.environ.get("KBS_ALLOW_PUBLIC_BIND") != "1":
            log.error(
                "HOST=%s reddedildi. Yalnizca 127.0.0.1/localhost/::1 izinli; "
                "loopback disindaki bind'lar otel agina aciktir. "
                "Gerekirse KBS_ALLOW_PUBLIC_BIND=1 ile zorla.",
                host,
            )
            sys.exit(3)
        log.warning(
            "HOST=%s loopback disinda ama KBS_ALLOW_PUBLIC_BIND=1 ile aciliyor. "
            "Otel agina maruz kalacak.",
            host,
        )
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
