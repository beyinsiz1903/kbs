"""Phase D — worker_id format & persistence.

The new format is `agent-<host>-<mac4>-<uuid4>`. Existing pre-Phase-D files
must be honored AS-IS (no forced regeneration), otherwise an upgrade in the
field would spam PMS with phantom-new-agent confusion.
"""
import re

import worker


def test_short_mac_returns_4_hex_or_noMAC():
    val = worker._short_mac()
    assert val == "noMAC" or re.fullmatch(r"[0-9a-f]{4}", val)


def test_short_mac_handles_random_node(monkeypatch):
    """When uuid.getnode() can't read a real MAC, bit 0x010000000000 is set."""
    monkeypatch.setattr(worker.uuid, "getnode", lambda: 0x010000000001)
    assert worker._short_mac() == "noMAC"


def test_short_mac_extracts_low_16_bits(monkeypatch):
    monkeypatch.setattr(worker.uuid, "getnode", lambda: 0x001122334455)
    assert worker._short_mac() == "4455"


def test_create_format_includes_host_mac_uuid(monkeypatch, tmp_path):
    """Fresh install: ID matches `agent-<host>-<mac>-<uuid>`."""
    monkeypatch.setattr(worker, "WORKER_ID_FILE", tmp_path / "worker_id")
    monkeypatch.setattr(worker.socket, "gethostname", lambda: "RECEPTION-A")
    monkeypatch.setattr(worker.uuid, "getnode", lambda: 0x001122334455)

    wid = worker._read_or_create_worker_id()
    assert wid.startswith("agent-RECEPTION-A-4455-")
    # UUID4 hex is 32 chars + 4 dashes = 36
    suffix = wid.rsplit("-", 5)[-5:]
    assert len(suffix) == 5  # uuid4 has 4 internal dashes


def test_existing_id_is_honored_as_is(monkeypatch, tmp_path):
    """An old `agent-HOST-uuid` file must NOT be regenerated."""
    legacy = "agent-OLDHOST-deadbeef-0000-0000-0000-000000000001"
    f = tmp_path / "worker_id"
    f.write_text(legacy)
    monkeypatch.setattr(worker, "WORKER_ID_FILE", f)

    wid = worker._read_or_create_worker_id()
    assert wid == legacy


def test_hostname_with_spaces_is_sanitized(monkeypatch, tmp_path):
    monkeypatch.setattr(worker, "WORKER_ID_FILE", tmp_path / "worker_id")
    monkeypatch.setattr(worker.socket, "gethostname", lambda: "Front Desk PC")
    monkeypatch.setattr(worker.uuid, "getnode", lambda: 0x001122334455)

    wid = worker._read_or_create_worker_id()
    assert "Front-Desk-PC" in wid
    assert " " not in wid


def test_hostname_truncated_to_40_chars(monkeypatch, tmp_path):
    monkeypatch.setattr(worker, "WORKER_ID_FILE", tmp_path / "worker_id")
    monkeypatch.setattr(worker.socket, "gethostname", lambda: "X" * 100)
    monkeypatch.setattr(worker.uuid, "getnode", lambda: 0x001122334455)

    wid = worker._read_or_create_worker_id()
    # Format: agent-<host[:40]>-<mac4>-<uuid>
    parts = wid.split("-")
    assert parts[0] == "agent"
    # The host portion is exactly 40 X's
    assert parts[1] == "X" * 40
