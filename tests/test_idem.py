"""Idempotency-Key persistence: keys stay stable across reads, get cleaned."""
import json
from pathlib import Path

import pytest


def test_get_or_create_returns_same_key_across_calls(_isolated_data_dir):
    import idem
    k1 = idem.get_or_create("job-1", "claim")
    k2 = idem.get_or_create("job-1", "claim")
    assert k1 == k2
    assert len(k1) >= 32  # uuid4 string


def test_get_or_create_different_actions_different_keys(_isolated_data_dir):
    import idem
    claim = idem.get_or_create("job-1", "claim")
    complete = idem.get_or_create("job-1", "complete")
    fail = idem.get_or_create("job-1", "fail")
    assert len({claim, complete, fail}) == 3


def test_get_or_create_persists_to_disk(_isolated_data_dir):
    import idem
    k = idem.get_or_create("job-99", "complete")
    p = Path(_isolated_data_dir) / "idem" / "job-99.json"
    assert p.exists()
    data = json.loads(p.read_text())
    assert data["complete"] == k


def test_get_or_create_survives_simulated_restart(_isolated_data_dir):
    """Keys must come back identical after the process forgets in-memory state."""
    import importlib
    import idem
    k_before = idem.get_or_create("job-7", "complete")
    # Simulate a fresh import (worker restart)
    import sys
    del sys.modules["idem"]
    idem2 = importlib.import_module("idem")
    k_after = idem2.get_or_create("job-7", "complete")
    assert k_before == k_after


def test_cleanup_removes_file(_isolated_data_dir):
    import idem
    idem.get_or_create("job-x", "claim")
    p = Path(_isolated_data_dir) / "idem" / "job-x.json"
    assert p.exists()
    idem.cleanup("job-x")
    assert not p.exists()
    # cleanup is idempotent — calling on a missing job must not raise
    idem.cleanup("job-x")


def test_invalid_action_rejected(_isolated_data_dir):
    import idem
    with pytest.raises(ValueError):
        idem.get_or_create("job-1", "wat")


def test_unsafe_job_id_sanitised(_isolated_data_dir):
    """Path traversal characters in job_id must not escape the idem dir."""
    import idem
    k = idem.get_or_create("../escape", "claim")
    files = list((Path(_isolated_data_dir) / "idem").iterdir())
    # Only one file, and inside the idem dir (no escape)
    assert len(files) == 1
    assert files[0].parent.name == "idem"
    assert k  # got a key back
