"""KBS (Konaklama Bildirim Sistemi) client.

Phase A: SIMULATION mode only — `submit_guest()` returns a fake reference
without any network call. The real EGM/Jandarma SOAP integration lands in
Phase B and replaces the body of `_send_real()`.

Required `kbs_config` keys (Phase B will validate these strictly):
  - tesis_kodu       : Otelin EGM tesis kodu
  - kullanici_adi    : KBS web servisi kullanici adi
  - sifre            : KBS web servisi sifresi
  - servis_url       : SOAP/XML endpoint URL (genelde Emniyet'in verdigi)
  - kurum            : "polis" | "jandarma" (Phase B)
"""
from __future__ import annotations

import os
import secrets
import time
from datetime import datetime, timezone


# Toggle with env var: KBS_MODE=real|simulation
KBS_MODE = os.environ.get("KBS_MODE", "simulation").lower()


class KBSError(Exception):
    """Base class for KBS-side errors."""


class KBSConfigError(KBSError):
    """Configuration is missing or invalid; worker should stop."""


class KBSRetryableError(KBSError):
    """Transient failure (timeout, 5xx, network); worker should ask PMS to retry."""


class KBSFatalError(KBSError):
    """Permanent failure (4xx, schema, validation); worker should ask PMS to mark dead."""


def submit_guest(payload: dict, config: dict | None = None) -> str:
    """Submit a single guest to the KBS web service. Returns the KBS reference.

    Phase A behavior:
      - If `KBS_MODE=real`, raise `KBSConfigError` (Phase B not yet implemented).
      - Otherwise, sleep briefly to mimic latency and return `SIM-...` reference.

    Phase B will:
      - Validate `config` strictly (raise `KBSConfigError` on missing fields).
      - Build SOAP envelope from `payload` per EGM/Jandarma WSDL.
      - Send via `zeep` over mTLS, parse `referans_no` from response.
      - Raise `KBSRetryableError` for 5xx/timeout/network and `KBSFatalError`
        for 4xx/schema validation.
    """
    if not isinstance(payload, dict) or not payload:
        raise KBSFatalError("KBS payload bos veya gecersiz")

    if KBS_MODE == "real":
        return _send_real(payload, config or {})
    return _send_simulated(payload, config or {})


# ---------- Simulation ----------

def _send_simulated(payload: dict, cfg: dict) -> str:
    """Phase A stub: pretend to call SOAP, return a fake reference."""
    time.sleep(0.4)
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    tesis = (cfg.get("tesis_kodu") or "DEMO").strip() or "DEMO"
    return f"SIM-{tesis}-{today}-{secrets.token_hex(4).upper()}"


# ---------- Real (placeholder until Phase B) ----------

def _send_real(payload: dict, cfg: dict) -> str:
    """Real EGM/Jandarma SOAP call. Implemented in Phase B."""
    raise KBSConfigError(
        "Gercek KBS gonderimi henuz aktif degil (Phase B). "
        "KBS_MODE=simulation kullanin veya WSDL/sertifika geldiginde Phase B'yi tamamlayin."
    )
