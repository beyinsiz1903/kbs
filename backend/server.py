"""KBS Agent backend (Phase A — autonomous polling worker).

This server runs alongside an asyncio polling worker. The worker pulls jobs from
the hotel's Syroce PMS KBS queue and reports results back. The HTTP surface
exists only to:
  - configure the agent (PMS URL + KBS settings)
  - hold the operator's PMS session (encrypted on disk)
  - expose the worker's status to a small UI

There is no "send to KBS" button anymore — submissions are autonomous.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.middleware.cors import CORSMiddleware

import worker
from pms_client import PMSError, get_me as pms_get_me, login as pms_login
from session import (
    clear_session,
    load_session,
    load_settings,
    save_session,
    save_settings,
    touch_session,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s - %(message)s")
log = logging.getLogger("kbs-bridge")

app = FastAPI(title="Syroce KBS Agent", version="3.0.0")

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
    hotel_id: str = Field(min_length=1, max_length=64)
    email: str
    password: str
    pms_url: str
    remember_me: bool = False


# ---------- Helpers ----------

def _kbs_is_configured(sess: dict) -> bool:
    return all(sess.get(k) for k in ("kbs_tesis_kodu", "kbs_kullanici_adi", "kbs_sifre", "kbs_servis_url"))


def require_session() -> dict:
    sess = load_session()
    if sess is None:
        raise HTTPException(status_code=401, detail="Oturum yok veya suresi doldu")
    touch_session()
    return sess


def require_csrf(x_kbs_client: Optional[str] = Header(default=None)) -> None:
    """CSRF protection: requires our custom header which forces CORS preflight.

    Browsers won't send X-KBS-Client cross-origin without a successful preflight,
    and our CORS config only allows the local frontend origin. This protects
    against drive-by sites attacking the loopback API while a session exists.
    """
    if x_kbs_client != "kbs-bridge":
        raise HTTPException(status_code=403, detail="Gecersiz istemci")


# ---------- Lifecycle ----------

@app.on_event("startup")
async def _startup() -> None:
    worker.start()


@app.on_event("shutdown")
async def _shutdown() -> None:
    await worker.stop()


# ---------- Health / settings ----------

@app.get("/api/health")
async def health() -> dict:
    return {"status": "ok", "time": datetime.now(timezone.utc).isoformat()}


@app.get("/api/settings")
async def get_settings() -> dict:
    """Plaintext settings (PMS URL only). KBS credentials live in session."""
    settings = load_settings()
    sess = load_session()
    return {
        "pms_url": settings.get("pms_url", ""),
        "hotel_id": settings.get("hotel_id", ""),
        "kbs_configured": bool(sess and _kbs_is_configured(sess)),
    }


@app.post("/api/settings", dependencies=[Depends(require_csrf)])
async def update_settings(payload: SettingsIn) -> dict:
    """Save the PMS URL (plaintext) and update KBS creds in the active session."""
    save_settings({**load_settings(), "pms_url": payload.pms_url})
    sess = load_session()
    if sess is not None:
        sess["kbs_tesis_kodu"] = payload.kbs_tesis_kodu or ""
        sess["kbs_kullanici_adi"] = payload.kbs_kullanici_adi or ""
        if payload.kbs_sifre:
            sess["kbs_sifre"] = payload.kbs_sifre
        sess["kbs_servis_url"] = payload.kbs_servis_url or ""
        sess["pms_url"] = payload.pms_url
        save_session(sess)
    return {"ok": True, "kbs_configured": bool(sess and _kbs_is_configured(sess))}


# ---------- Auth ----------

@app.post("/api/auth/login", dependencies=[Depends(require_csrf)])
async def login(payload: LoginIn) -> dict:
    """Login through the PMS. Stores the access_token + tenant info in the local session."""
    pms_resp = await pms_login(payload.pms_url, payload.hotel_id, payload.email, payload.password)
    access_token = pms_resp.get("access_token")
    if not access_token:
        raise HTTPException(status_code=502, detail="PMS access_token donmedi")

    me = await pms_get_me(payload.pms_url, access_token)

    # Preserve existing KBS creds across logins
    prev = load_session() or {}
    save_settings({
        **load_settings(),
        "pms_url": payload.pms_url,
        "hotel_id": payload.hotel_id,
    })
    save_session({
        "pms_url": payload.pms_url,
        "hotel_id": payload.hotel_id,
        "access_token": access_token,
        "user": me,
        "remember_me": payload.remember_me,
        "kbs_tesis_kodu": prev.get("kbs_tesis_kodu", ""),
        "kbs_kullanici_adi": prev.get("kbs_kullanici_adi", ""),
        "kbs_sifre": prev.get("kbs_sifre", ""),
        "kbs_servis_url": prev.get("kbs_servis_url", ""),
    })
    # Wake worker so it picks up the new session immediately
    worker.trigger_poll_now()
    return {"user": me}


@app.get("/api/auth/me")
async def me(sess: dict = Depends(require_session)) -> dict:
    return {
        "user": sess["user"],
        "pms_url": sess["pms_url"],
        "hotel_id": sess.get("hotel_id", ""),
        "kbs_configured": _kbs_is_configured(sess),
    }


@app.post("/api/auth/logout", dependencies=[Depends(require_csrf)])
async def logout() -> dict:
    clear_session()
    return {"ok": True}


# ---------- Worker status ----------

@app.get("/api/worker/status")
async def worker_status() -> dict:
    """Snapshot of the polling worker for the UI."""
    return worker.get_state().to_dict()


@app.post("/api/worker/poll-now", dependencies=[Depends(require_csrf)])
async def worker_poll_now() -> dict:
    """Wake the worker now instead of waiting for the next poll tick."""
    triggered = worker.trigger_poll_now()
    return {"triggered": triggered}


# ---------- Error wrapping ----------

@app.exception_handler(PMSError)
async def pms_error_handler(request: Request, exc: PMSError) -> JSONResponse:
    if exc.status_code == 401:
        clear_session()
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
