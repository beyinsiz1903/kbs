"""Loopback bind hardening — strict policy: only 127.0.0.1/localhost/::1.

Anything else (wildcards or LAN IPs) requires KBS_ALLOW_PUBLIC_BIND=1.
"""
import os
import sys

import pytest


@pytest.fixture(autouse=True)
def _backend_path():
    here = os.path.dirname(os.path.abspath(__file__))
    backend = os.path.join(os.path.dirname(here), "backend")
    if backend not in sys.path:
        sys.path.insert(0, backend)
    yield


def test_default_is_loopback(monkeypatch):
    monkeypatch.delenv("HOST", raising=False)
    monkeypatch.delenv("KBS_ALLOW_PUBLIC_BIND", raising=False)
    import app_runtime
    assert app_runtime._resolved_host() == "127.0.0.1"


@pytest.mark.parametrize("host", ["127.0.0.1", "localhost", "LocalHost", "::1"])
def test_explicit_loopback_allowed(monkeypatch, host):
    monkeypatch.setenv("HOST", host)
    monkeypatch.delenv("KBS_ALLOW_PUBLIC_BIND", raising=False)
    import app_runtime
    assert app_runtime._resolved_host() == host


@pytest.mark.parametrize("host", ["0.0.0.0", "::", "*", "192.168.1.10", "10.0.0.5", "myhotel.local"])
def test_non_loopback_rejected_no_override(monkeypatch, host):
    """STRICT policy — no escape hatch. Even KBS_ALLOW_PUBLIC_BIND=1 is ignored."""
    monkeypatch.setenv("HOST", host)
    monkeypatch.delenv("KBS_ALLOW_PUBLIC_BIND", raising=False)
    import app_runtime
    with pytest.raises(SystemExit) as exc:
        app_runtime._resolved_host()
    assert exc.value.code == 3


@pytest.mark.parametrize("host", ["0.0.0.0", "192.168.1.10"])
def test_non_loopback_rejected_even_with_override(monkeypatch, host):
    """Phase C: there is NO public-bind override. The flag is ignored."""
    monkeypatch.setenv("HOST", host)
    monkeypatch.setenv("KBS_ALLOW_PUBLIC_BIND", "1")
    import app_runtime
    with pytest.raises(SystemExit) as exc:
        app_runtime._resolved_host()
    assert exc.value.code == 3


def test_invalid_port_exits(monkeypatch):
    monkeypatch.setenv("PORT", "not-a-number")
    import app_runtime
    with pytest.raises(SystemExit) as exc:
        app_runtime._resolved_port()
    assert exc.value.code == 3


def test_default_port(monkeypatch):
    monkeypatch.delenv("PORT", raising=False)
    import app_runtime
    assert app_runtime._resolved_port() == 8765
