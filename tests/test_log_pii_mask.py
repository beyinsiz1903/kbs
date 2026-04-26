"""PII masking filter must scrub TC, passport, dates, and field-name patterns."""
import logging
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


def test_mask_tc():
    from log_setup import mask_pii
    out = mask_pii("Misafir TC: 12345678901 girisi")
    assert "12345678901" not in out
    assert "***" in out


def test_mask_does_not_touch_short_or_long_runs():
    from log_setup import mask_pii
    # 10 digits → not TC (job id, phone, etc.)
    assert "1234567890" in mask_pii("ref 1234567890 booking")
    # 13 digits → not TC
    assert "1234567890123" in mask_pii("ref 1234567890123 booking")


def test_mask_passport():
    from log_setup import mask_pii
    out = mask_pii("Pasaport: U12345678 ile giris")
    assert "U12345678" not in out
    assert "***" in out


def test_mask_does_not_touch_uuid_jobs():
    from log_setup import mask_pii
    # Job UUIDs are lowercase + hyphenated → must NOT be passport-masked
    jid = "550e8400-e29b-41d4-a716-446655440000"
    assert jid in mask_pii(f"Job {jid} processed")


def test_mask_birth_date():
    from log_setup import mask_pii
    out = mask_pii("dogum 1985-04-12 ev")
    assert "1985-04-12" not in out
    assert "***" in out


def test_mask_json_field():
    from log_setup import mask_pii
    payload = '{"ad": "Ahmet", "soyad": "Yilmaz", "tc_kimlik": "12345678901"}'
    out = mask_pii(payload)
    assert "Ahmet" not in out and "Yilmaz" not in out
    assert "12345678901" not in out
    assert out.count("***") >= 3


def test_mask_kv_field():
    from log_setup import mask_pii
    out = mask_pii("Login isteği password=hunter2 user=ali")
    assert "hunter2" not in out
    assert "***" in out


def test_filter_masks_args(tmp_path):
    """The PIIMaskingFilter must scrub %s args BEFORE formatting."""
    from log_setup import PIIMaskingFilter

    rec = logging.LogRecord(
        name="t", level=logging.INFO, pathname=__file__, lineno=1,
        msg="Misafir kayit edildi: TC=%s ad=%s",
        args=("12345678901", "Mehmet"),
        exc_info=None,
    )
    PIIMaskingFilter().filter(rec)
    # After filter, args should be replaced (TC) but plain non-PII strings
    # like "Mehmet" remain unless they match a field-name pattern at format
    # time. The TC must be gone.
    assert "12345678901" not in str(rec.args)


def test_configure_writes_log_file(tmp_path):
    from log_setup import configure
    log_path = configure(log_dir=tmp_path, enable_console=False)
    logger = logging.getLogger("kbs-bridge.test")
    logger.warning("Misafir TC=12345678901 kayit edildi")
    # Flush handlers so the rotating file actually has bytes
    for h in logging.getLogger().handlers:
        try:
            h.flush()
        except Exception:
            pass
    assert log_path.exists()
    content = log_path.read_text(encoding="utf-8")
    assert "12345678901" not in content
    assert "***" in content
