"""Logging setup with rotating files + PII masking.

Production goal:
  - Console + RotatingFileHandler at %LOCALAPPDATA%\\SyroceKBSAgent\\logs\\agent.log
    on Windows, ~/.local/share/SyroceKBSAgent/logs/agent.log on Linux.
  - 10 MB per file, keep 5 rotations.
  - PII masking: TC kimlik (11 digits), passport-like (8-12 alphanumeric upper),
    ISO birth dates, and explicit field-name based masking for `ad`, `soyad`,
    `tc_kimlik`, `pasaport_no`, `dogum_tarihi` substrings inside log messages.

PII masking is applied as a logging.Filter so it works for `log.info("...%s...", x)`
calls — both the format string and arguments are inspected before formatting.
Job IDs and booking IDs are NOT masked (we need to grep them in support).
"""
from __future__ import annotations

import logging
import logging.handlers
import os
import re
import sys
from pathlib import Path
from typing import Optional

# ---------- Paths ----------

def default_log_dir() -> Path:
    """Platform-appropriate log directory under the user profile."""
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
        return Path(base) / "SyroceKBSAgent" / "logs"
    base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    return Path(base) / "SyroceKBSAgent" / "logs"


# ---------- PII masking ----------

# TC Kimlik: exactly 11 digits, not part of a longer digit run.
_RE_TC = re.compile(r"(?<!\d)\d{11}(?!\d)")
# Passport-like: 8-12 uppercase alphanumeric token surrounded by non-alnum
# (catches U12345678, P87654321, etc.). Avoid catching pure-digit job UUIDs by
# requiring at least one letter.
_RE_PASSPORT = re.compile(r"(?<![A-Za-z0-9])(?=[A-Z0-9]{8,12}(?![A-Z0-9]))(?=[A-Z0-9]*[A-Z])[A-Z0-9]{8,12}")
# ISO date YYYY-MM-DD (we never log dates outside birth/booking; safer to mask).
_RE_DATE = re.compile(r"(?<!\d)(19|20)\d{2}-\d{2}-\d{2}(?!\d)")
# JSON-ish "field": "value" or field=value pairs we always want masked.
_FIELD_NAMES = ("tc_kimlik", "tc_kimlik_no", "pasaport_no", "ad", "soyad",
                "isim", "dogum_tarihi", "kbs_sifre", "password", "access_token")
_RE_FIELD_JSON = re.compile(
    r'"(' + "|".join(_FIELD_NAMES) + r')"\s*:\s*"[^"]*"',
    re.IGNORECASE,
)
_RE_FIELD_KV = re.compile(
    r'\b(' + "|".join(_FIELD_NAMES) + r')\s*=\s*[^\s,;)]+',
    re.IGNORECASE,
)

MASK = "***"


def mask_pii(text: str) -> str:
    """Replace TC, passports, dates, and field-name patterns with ***."""
    if not text:
        return text
    text = _RE_FIELD_JSON.sub(lambda m: f'"{m.group(1)}": "{MASK}"', text)
    text = _RE_FIELD_KV.sub(lambda m: f"{m.group(1)}={MASK}", text)
    text = _RE_TC.sub(MASK, text)
    text = _RE_PASSPORT.sub(MASK, text)
    text = _RE_DATE.sub(MASK, text)
    return text


class PIIMaskingFilter(logging.Filter):
    """logging.Filter that masks PII in both the format string and args."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            if isinstance(record.msg, str):
                record.msg = mask_pii(record.msg)
            if record.args:
                if isinstance(record.args, dict):
                    record.args = {k: self._mask_arg(v) for k, v in record.args.items()}
                else:
                    record.args = tuple(self._mask_arg(a) for a in record.args)
        except Exception:  # pragma: no cover - never let logging crash the app
            pass
        return True

    @staticmethod
    def _mask_arg(value):
        if isinstance(value, str):
            return mask_pii(value)
        return value


# ---------- Setup ----------

_configured = False


def configure(
    log_dir: Optional[Path] = None,
    level: int = logging.INFO,
    max_bytes: int = 10 * 1024 * 1024,
    backup_count: int = 5,
    enable_console: bool = True,
) -> Path:
    """Configure the root logger. Idempotent. Returns the active log file path."""
    global _configured
    target_dir = (log_dir or default_log_dir()).resolve()
    target_dir.mkdir(parents=True, exist_ok=True)
    log_path = target_dir / "agent.log"

    root = logging.getLogger()
    root.setLevel(level)

    fmt = logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    pii_filter = PIIMaskingFilter()

    # Remove handlers we previously installed (idempotent re-config).
    for h in list(root.handlers):
        if getattr(h, "_kbs_managed", False):
            root.removeHandler(h)

    file_handler = logging.handlers.RotatingFileHandler(
        log_path, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8"
    )
    file_handler.setFormatter(fmt)
    file_handler.addFilter(pii_filter)
    file_handler._kbs_managed = True  # type: ignore[attr-defined]
    root.addHandler(file_handler)

    if enable_console:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(fmt)
        console_handler.addFilter(pii_filter)
        console_handler._kbs_managed = True  # type: ignore[attr-defined]
        root.addHandler(console_handler)

    _configured = True
    return log_path


def is_configured() -> bool:
    return _configured
