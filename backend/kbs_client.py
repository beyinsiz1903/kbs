"""KBS (Konaklama Bildirim Sistemi) client.

Currently runs in SIMULATION mode — generates a fake submission reference.
The real implementation will replace `_send_real()` with SOAP/XML calls to
the EGM/Jandarma KBS endpoint defined in `kbs_config`.

Required `kbs_config` keys (provided by user via Settings ekrani):
  - tesis_kodu       : Otelin EGM tesis kodu
  - kullanici_adi    : KBS web servisi kullanici adi
  - sifre            : KBS web servisi sifresi
  - servis_url       : SOAP/XML endpoint URL (genelde Emniyet'in verdigi)
"""
from __future__ import annotations

import os
import secrets
import time
from datetime import datetime, timezone
from typing import Iterable

# Toggle with env var: KBS_MODE=real|simulation
KBS_MODE = os.environ.get("KBS_MODE", "simulation").lower()


class KBSConfigError(ValueError):
    pass


def _validate_config(cfg: dict) -> None:
    missing = [k for k in ("tesis_kodu", "kullanici_adi", "sifre", "servis_url")
               if not cfg.get(k)]
    if missing:
        raise KBSConfigError(
            "KBS ayarlari eksik. Settings ekranindan doldurun: " + ", ".join(missing)
        )


def submit(guests: list[dict], kbs_config: dict, notes: str = "") -> dict:
    """Send guests to KBS. Returns a submission reference + summary.

    Each guest dict should already be PMS-shape (TC/passport, ad, soyad, dogum,
    milliyet, etc.). The mapping to KBS XML is left to `_send_real()`.
    """
    _validate_config(kbs_config)
    if not guests:
        raise ValueError("Gonderilecek misafir listesi bos")

    if KBS_MODE == "real":
        reference = _send_real(guests, kbs_config, notes)
    else:
        reference = _send_simulated(guests, kbs_config, notes)

    return {
        "submission_reference": reference,
        "submitted_at": datetime.now(timezone.utc).isoformat(),
        "guest_count": len(guests),
        "mode": KBS_MODE,
    }


# ---------- Simulation ----------

def _send_simulated(guests: list[dict], cfg: dict, notes: str) -> str:
    # Hafif gecikme ile gercek SOAP cagrisini taklit et
    time.sleep(0.4)
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    return f"SIM-{cfg['tesis_kodu']}-{today}-{secrets.token_hex(4).upper()}"


# ---------- Real (placeholder) ----------

def _send_real(guests: list[dict], cfg: dict, notes: str) -> str:
    """SOAP/XML POST to cfg['servis_url'] using cfg credentials.

    TODO: Emniyet/Jandarma KBS web servisi WSDL'ine gore doldurun.
    Genel sablon:
        - SOAP envelope hazirla
        - Her misafir icin <Konaklayan> elemani ekle (TC/Pasaport, ad, soyad,
          dogum, cinsiyet, milliyet, baba/anne adi, dogum yeri, oda no,
          giris/cikis tarihleri)
        - WS-Security header'a kullanici_adi/sifre koy (veya servis nasil
          istiyorsa)
        - response'tan donen TakipNo / IslemKodu'nu submission_reference
          olarak dondur
    """
    raise NotImplementedError(
        "Gercek KBS gonderimi henuz aktif degil. KBS_MODE=simulation kullanin "
        "veya kbs_client._send_real() fonksiyonunu Emniyet WSDL'ine gore doldurun."
    )
