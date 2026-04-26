"""On non-Windows the eventlog module must be a silent no-op."""
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


@pytest.mark.skipif(sys.platform == "win32", reason="non-Windows fallback test")
def test_register_source_returns_false():
    import eventlog
    assert eventlog.register_source() is False


@pytest.mark.skipif(sys.platform == "win32", reason="non-Windows fallback test")
def test_warn_dead_job_does_not_raise():
    import eventlog
    eventlog.warn_dead_job("job-1", error="boom")
    eventlog.warn_replay_failure("job-2", "transient")
    eventlog.info_kbs_refused("not ready yet")
