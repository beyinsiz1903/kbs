"""KBS Bridge backend.

Thin proxy between the local KBS thin-client UI and:
  1) the hotel's Syroce PMS (REST API)
  2) the EGM/Jandarma KBS web service (SOAP/XML)

Session state lives in a Fernet-encrypted file under /data — see session.py.
This server has NO database. The PMS is the source of truth.
"""
import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from pydantic import BaseModel, Field
from starlette.middleware.cors import CORSMiddleware

from kbs_client import KBSConfigError, submit as kbs_submit
from pms_client import (
    PMSError,
    get_guests as pms_get_guests,
    get_me as pms_get_me,
    get_report_detail as pms_get_report_detail,
    get_reports as pms_get_reports,
    login as pms_login,
    post_report as pms_post_report,
)
from session import (
    DATA_DIR,
    clear_session,
    load_session,
    load_settings,
    save_session,
    save_settings,
    touch_session,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s - %(message)s")
log = logging.getLogger("kbs-bridge")

app = FastAPI(title="KBS Bridge", version="2.1.0")

# Default to the local frontend only. Hotel deployments override via CORS_ORIGINS.
_default_origins = "http://localhost:5000,http://127.0.0.1:5000"
_origins = [o.strip() for o in os.environ.get("CORS_ORIGINS", _default_origins).split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "X-KBS-Client"],
    allow_credentials=False,
)


# ---------- Models ----------

class SettingsIn(BaseModel):
    pms_url: str
    kbs_tesis_kodu: Optional[str] = ""
    kbs_kullanici_adi: Optional[str] = ""
    kbs_sifre: Optional[str] = None  # None = preserve existing
    kbs_servis_url: Optional[str] = ""


class LoginIn(BaseModel):
    email: str
    password: str
    pms_url: str
    remember_me: bool = False


class ReportIn(BaseModel):
    date: str
    booking_ids: list[str] = Field(min_length=1)
    notes: str = ""


# ---------- Helpers ----------

def _kbs_is_configured(sess: dict) -> bool:
    return all(sess.get(k) for k in ("kbs_tesis_kodu", "kbs_kullanici_adi", "kbs_sifre", "kbs_servis_url"))


def require_session() -> dict:
    sess = load_session()
    if sess is None:
        raise HTTPException(status_code=401, detail="Oturum yok veya suresi doldu")
    touch_session()
    return sess


def require_csrf(x_kbs_client: Optional[str] = Header(default=None)):
    """Block cross-site requests: requires custom header which triggers CORS preflight.

    Browsers won't send X-KBS-Client cross-origin without a successful preflight,
    and our CORS config only allows the local frontend origin. This protects
    against drive-by sites attacking the loopback API while a session exists.
    """
    if x_kbs_client != "kbs-bridge":
        raise HTTPException(status_code=403, detail="Gecersiz istemci")


def _kbs_config_from_session(sess: dict) -> dict:
    return {
        "tesis_kodu": sess.get("kbs_tesis_kodu", ""),
        "kullanici_adi": sess.get("kbs_kullanici_adi", ""),
        "sifre": sess.get("kbs_sifre", ""),
        "servis_url": sess.get("kbs_servis_url", ""),
    }


# ---------- Submission journal (durable record before PMS ack) ----------

JOURNAL_FILE = DATA_DIR / "submissions.jsonl"


def _journal_append(entry: dict) -> None:
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        with JOURNAL_FILE.open("a") as f:
            f.write(json.dumps(entry) + "\n")
    except OSError as e:
        log.warning("Submission journal write failed: %s", e)


# ---------- Health / settings ----------

@app.get("/api/health")
async def health():
    return {"status": "ok", "time": datetime.now(timezone.utc).isoformat()}


@app.get("/api/settings")
async def get_settings():
    """Plaintext settings (PMS URL only). KBS credentials live in session."""
    settings = load_settings()
    sess = load_session()
    return {
        "pms_url": settings.get("pms_url", ""),
        "kbs_configured": bool(sess and _kbs_is_configured(sess)),
    }


@app.post("/api/settings", dependencies=[Depends(require_csrf)])
async def update_settings(payload: SettingsIn):
    """Save the PMS URL (plaintext) and update KBS creds in the active session."""
    save_settings({"pms_url": payload.pms_url})
    sess = load_session()
    if sess is not None:
        sess["kbs_tesis_kodu"] = payload.kbs_tesis_kodu or ""
        sess["kbs_kullanici_adi"] = payload.kbs_kullanici_adi or ""
        # None or empty → preserve existing password (frontend leaves blank)
        if payload.kbs_sifre:
            sess["kbs_sifre"] = payload.kbs_sifre
        sess["kbs_servis_url"] = payload.kbs_servis_url or ""
        sess["pms_url"] = payload.pms_url
        save_session(sess)
    return {"ok": True, "kbs_configured": bool(sess and _kbs_is_configured(sess))}


# ---------- Auth ----------

@app.post("/api/auth/login", dependencies=[Depends(require_csrf)])
async def login(payload: LoginIn):
    pms_resp = await pms_login(payload.pms_url, payload.email, payload.password)
    access_token = pms_resp.get("access_token")
    if not access_token:
        raise HTTPException(status_code=502, detail="PMS access_token donmedi")

    me = await pms_get_me(payload.pms_url, access_token)

    # Preserve existing KBS creds across logins
    prev = load_session() or {}
    save_settings({"pms_url": payload.pms_url})
    save_session({
        "pms_url": payload.pms_url,
        "access_token": access_token,
        "user": me,
        "remember_me": payload.remember_me,
        "kbs_tesis_kodu": prev.get("kbs_tesis_kodu", ""),
        "kbs_kullanici_adi": prev.get("kbs_kullanici_adi", ""),
        "kbs_sifre": prev.get("kbs_sifre", ""),
        "kbs_servis_url": prev.get("kbs_servis_url", ""),
    })
    return {"user": me}


@app.get("/api/auth/me")
async def me(sess: dict = Depends(require_session)):
    return {
        "user": sess["user"],
        "pms_url": sess["pms_url"],
        "kbs_configured": _kbs_is_configured(sess),
    }


@app.post("/api/auth/logout", dependencies=[Depends(require_csrf)])
async def logout():
    clear_session()
    return {"ok": True}


# ---------- KBS data flow ----------

@app.get("/api/guests")
async def list_guests(date: str, sess: dict = Depends(require_session), _csrf: None = Depends(require_csrf)):
    return await pms_get_guests(sess["pms_url"], sess["access_token"], date)


@app.post("/api/kbs/submit", dependencies=[Depends(require_csrf)])
async def submit_to_kbs(payload: ReportIn, sess: dict = Depends(require_session)):
    """1) Pull selected guests from PMS, 2) send to KBS, 3) report back to PMS.

    A durable journal entry is written BEFORE the PMS ack so that if the ack
    fails, the operator can still see the KBS reference and reconcile manually.
    """
    pms_url = sess["pms_url"]
    token = sess["access_token"]

    pms_data = await pms_get_guests(pms_url, token, payload.date)
    selected = [g for g in pms_data.get("guests", []) if g.get("id") in payload.booking_ids]

    if not selected:
        raise HTTPException(status_code=404, detail="Secili misafir bulunamadi")

    not_ready = [g["id"] for g in selected if not g.get("kbs_ready")]
    if not_ready:
        raise HTTPException(
            status_code=400,
            detail=f"Eksik bilgili misafirler gonderilemez: {', '.join(not_ready)}",
        )

    validated_ids = [g["id"] for g in selected]

    try:
        kbs_result = kbs_submit(selected, _kbs_config_from_session(sess), payload.notes)
    except KBSConfigError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except NotImplementedError as e:
        raise HTTPException(status_code=501, detail=str(e))
    except Exception as e:
        log.exception("KBS gonderimi basarisiz")
        raise HTTPException(status_code=502, detail=f"KBS hatasi: {e}")

    # Persist BEFORE attempting PMS ack so we can reconcile on failure
    _journal_append({
        "ts": datetime.now(timezone.utc).isoformat(),
        "user": sess.get("user", {}).get("email"),
        "date": payload.date,
        "booking_ids": validated_ids,
        "submission_reference": kbs_result["submission_reference"],
        "mode": kbs_result["mode"],
        "pms_acked": False,
    })

    # Acknowledge PMS using ONLY validated IDs (not raw client input)
    try:
        pms_ack = await pms_post_report(pms_url, token, {
            "date": payload.date,
            "booking_ids": validated_ids,
            "notes": payload.notes,
            "submission_reference": kbs_result["submission_reference"],
        })
    except Exception as e:
        log.exception("PMS ack basarisiz, KBS gonderimi yapildi")
        _journal_append({
            "ts": datetime.now(timezone.utc).isoformat(),
            "submission_reference": kbs_result["submission_reference"],
            "pms_ack_error": str(e),
        })
        raise HTTPException(
            status_code=502,
            detail=(
                f"KBS gonderimi yapildi (Ref: {kbs_result['submission_reference']}) "
                f"ancak PMS isaretlenemedi: {e}. "
                "Lutfen PMS'te elle isaretleyin veya yeniden deneyin."
            ),
        )

    _journal_append({
        "ts": datetime.now(timezone.utc).isoformat(),
        "submission_reference": kbs_result["submission_reference"],
        "pms_acked": True,
    })

    return {
        "submission_reference": kbs_result["submission_reference"],
        "submitted_at": kbs_result["submitted_at"],
        "guest_count": kbs_result["guest_count"],
        "mode": kbs_result["mode"],
        "booking_ids": validated_ids,
        "pms_ack": pms_ack,
    }


@app.get("/api/reports")
async def list_reports(date_from: str, date_to: str, sess: dict = Depends(require_session), _csrf: None = Depends(require_csrf)):
    return await pms_get_reports(sess["pms_url"], sess["access_token"], date_from, date_to)


@app.get("/api/reports/{report_id}")
async def report_detail(report_id: str, sess: dict = Depends(require_session), _csrf: None = Depends(require_csrf)):
    return await pms_get_report_detail(sess["pms_url"], sess["access_token"], report_id)


# ---------- Error wrapping ----------

@app.exception_handler(PMSError)
async def pms_error_handler(request: Request, exc: PMSError):
    if exc.status_code == 401:
        clear_session()
    from fastapi.responses import JSONResponse
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
