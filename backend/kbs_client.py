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
    # Accept both the session-style key (kbs_tesis_kodu) and the bare name
    # (tesis_kodu) so callers can pass either.
    tesis = (cfg.get("kbs_tesis_kodu") or cfg.get("tesis_kodu") or "DEMO").strip() or "DEMO"
    return f"SIM-{tesis}-{today}-{secrets.token_hex(4).upper()}"


# ---------- Real (Phase B activation point) ----------

# Flip to True once `_send_real()` is fully implemented against the real
# WSDL+mTLS materials. The worker uses this as a hard gate: while False, real
# mode REFUSES to process jobs entirely (never calls fail_job → no risk of
# PMS dead-lettering jobs because SOAP isn't wired yet).
REAL_SOAP_IMPLEMENTED = False


def is_real_ready() -> bool:
    """Reports whether real KBS submission is actually wired (Phase B done)."""
    return REAL_SOAP_IMPLEMENTED


REAL_REQUIRED_CONFIG = (
    "kbs_tesis_kodu",
    "kbs_kullanici_adi",
    "kbs_sifre",
    "kbs_servis_url",
    "kbs_kurum",  # "polis" | "jandarma"
)


def _validate_real_config(cfg: dict) -> None:
    """Strict validation; raises KBSConfigError naming exactly what is missing.

    Run this in real mode BEFORE attempting any SOAP call so the operator gets
    a clear message in the worker status panel instead of an opaque transport
    error from zeep / requests.
    """
    missing = [k for k in REAL_REQUIRED_CONFIG if not (cfg.get(k) or "").strip()]
    if missing:
        raise KBSConfigError(
            "Eksik KBS yapilandirmasi: " + ", ".join(missing)
            + " (Ayarlar sayfasindan tamamlayin)."
        )
    if cfg["kbs_kurum"] not in ("polis", "jandarma"):
        raise KBSConfigError(
            f"Gecersiz kbs_kurum: {cfg['kbs_kurum']!r}. 'polis' veya 'jandarma' olmali."
        )
    # Env-side requirements (WSDL + cert). The actual zeep client construction
    # lands once EGM/Jandarma have provided WSDL + mTLS materials.
    if not os.environ.get("KBS_WSDL_URL"):
        raise KBSConfigError(
            "KBS_WSDL_URL ortam degiskeni eksik. Emniyet'in verdigi WSDL URL/dosya yolu."
        )


def _send_real(payload: dict, cfg: dict) -> str:
    """Real EGM/Jandarma SOAP call.

    Phase B activation: replace the body below with zeep-based SOAP envelope
    construction (per the WSDL + XSD field names provided by Emniyet) and
    mTLS transport (KBS_CERT_PATH/KBS_KEY_PATH or KBS_PFX_PATH + CA bundle).

    Until WSDL + mTLS materials are in hand, we explicitly REFUSE to fabricate
    a reference number — submitting a fake "rapor" to the police would be a
    legal/regulatory violation.
    """
    _validate_real_config(cfg)
    raise KBSConfigError(
        "Gercek KBS gonderimi henuz aktif degil. "
        "WSDL + mTLS sertifikasi geldiginde kbs_client._send_real() doldurulacak. "
        "O zamana kadar KBS_MODE=simulation kullanin."
    )
