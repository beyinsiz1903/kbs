"""Thin async HTTP client to the hotel's Syroce PMS (KBS Agent contract v1).

This module ONLY proxies. No business logic, no retries (worker decides retries
based on the typed exceptions / PMSError status codes raised here).

Endpoints used:
    POST /api/auth/login        — login with hotel_id + email + password
    GET  /api/auth/me           — current user / tenant info
    GET  /api/kbs/queue         — list queue jobs
    POST /api/kbs/queue/{id}/claim    — atomic claim (409 if taken)
    POST /api/kbs/queue/{id}/complete — mark done with kbs_reference
    POST /api/kbs/queue/{id}/fail     — mark fail (PMS decides retry vs dead)
"""
from __future__ import annotations

import os
from typing import Optional
from urllib.parse import urlparse

import httpx
from fastapi import HTTPException


class PMSError(HTTPException):
    """HTTP error from the PMS surface, with the same shape as FastAPI's HTTPException."""


# Hosts the user must NEVER set as their PMS URL — would cause request loops
_FORBIDDEN_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "::1"}

DEFAULT_TIMEOUT = httpx.Timeout(connect=8.0, read=15.0, write=10.0, pool=5.0)


def _validate_pms_url(pms_url: str) -> None:
    try:
        u = urlparse(pms_url)
    except Exception:
        raise PMSError(status_code=400, detail="PMS URL gecersiz")
    if u.scheme not in ("http", "https") or not u.netloc:
        raise PMSError(status_code=400, detail="PMS URL 'https://...' formatinda olmali")
    host = (u.hostname or "").lower()
    if host in _FORBIDDEN_HOSTS:
        raise PMSError(
            status_code=400,
            detail="PMS URL bu bilgisayara isaret ediyor. Otelinizin gercek Syroce PMS adresini girin.",
        )
    own_host = os.environ.get("PUBLIC_HOSTNAME", "").lower()
    if own_host and host == own_host:
        raise PMSError(
            status_code=400,
            detail="PMS URL bu uygulamanin kendi adresi. Otelinizin gercek PMS adresini girin.",
        )


def _translate_error(resp: httpx.Response) -> PMSError:
    try:
        body = resp.json()
        detail = body.get("detail") or body.get("message") or resp.text
    except Exception:
        detail = resp.text or "PMS hatasi"
    return PMSError(status_code=resp.status_code, detail=detail)


def _wrap_request_error(e: httpx.RequestError) -> PMSError:
    if isinstance(e, httpx.TimeoutException):
        return PMSError(
            status_code=504,
            detail="PMS yanit vermedi (zaman asimi). PMS adresini kontrol edin.",
        )
    return PMSError(
        status_code=503,
        detail=f"PMS'e ulasilamiyor: {e.__class__.__name__}",
    )


# ---------- Internal helpers ----------

def _auth_headers(token: str, idem_key: Optional[str] = None) -> dict:
    h = {"Authorization": f"Bearer {token}"}
    if idem_key:
        h["Idempotency-Key"] = idem_key
    return h


async def _request(method: str, url: str, *, headers: dict, json_body: Optional[dict] = None,
                   params: Optional[dict] = None, timeout: httpx.Timeout = DEFAULT_TIMEOUT) -> dict:
    # Defense in depth: every outbound call re-validates the host so a poisoned
    # session/settings store cannot redirect the worker to loopback or self.
    _validate_pms_url(url)
    async with httpx.AsyncClient(timeout=timeout, verify=True, follow_redirects=False) as client:
        try:
            resp = await client.request(method, url, headers=headers, json=json_body, params=params)
        except httpx.RequestError as e:
            raise _wrap_request_error(e) from e
    if resp.status_code >= 400:
        raise _translate_error(resp)
    if resp.status_code == 204 or not resp.content:
        return {}
    try:
        return resp.json()
    except ValueError:
        raise PMSError(
            status_code=502,
            detail="PMS adresi bir Syroce PMS gibi yanit vermedi (JSON donmedi).",
        )


# ---------- Auth ----------

async def login(pms_url: str, hotel_id: str, email: str, password: str) -> dict:
    """POST {PMS_URL}/api/auth/login → {access_token, token_type, user}.

    `hotel_id` is REQUIRED by the v1 KBS Agent contract.
    """
    _validate_pms_url(pms_url)
    if not hotel_id:
        raise PMSError(status_code=400, detail="hotel_id zorunludur")
    url = pms_url.rstrip("/") + "/api/auth/login"
    body = {"hotel_id": hotel_id, "email": email, "password": password}
    return await _request("POST", url, headers={}, json_body=body)


async def get_me(pms_url: str, token: str) -> dict:
    """GET {PMS_URL}/api/auth/me → {id, email, tenant_id, role, ...}."""
    url = pms_url.rstrip("/") + "/api/auth/me"
    return await _request("GET", url, headers=_auth_headers(token))


# ---------- KBS Queue (v1) ----------

async def list_queue(
    pms_url: str,
    token: str,
    status: Optional[str] = None,
    limit: int = 20,
    date_from: Optional[str] = None,
) -> dict:
    """GET {PMS_URL}/api/kbs/queue?status=&limit=&date_from=

    Returns: {jobs: [...], total: N, stats: {pending, in_progress, done, failed, dead}}
    `status` may be a single value or comma-separated.
    """
    url = pms_url.rstrip("/") + "/api/kbs/queue"
    params: dict = {"limit": limit}
    if status:
        params["status"] = status
    if date_from:
        params["date_from"] = date_from
    return await _request("GET", url, headers=_auth_headers(token), params=params)


async def claim_job(
    pms_url: str,
    token: str,
    job_id: str,
    worker_id: str,
    lease_seconds: int = 300,
    idem_key: Optional[str] = None,
) -> dict:
    """POST {PMS_URL}/api/kbs/queue/{id}/claim → {job: {...}}.

    Raises PMSError(409) if another worker holds the lease, PMSError(404) if missing.
    """
    url = pms_url.rstrip("/") + f"/api/kbs/queue/{job_id}/claim"
    body = {"worker_id": worker_id, "lease_seconds": lease_seconds}
    return await _request("POST", url, headers=_auth_headers(token, idem_key), json_body=body)


async def complete_job(
    pms_url: str,
    token: str,
    job_id: str,
    worker_id: str,
    kbs_reference: str,
    notes: str = "",
    idem_key: Optional[str] = None,
) -> dict:
    """POST {PMS_URL}/api/kbs/queue/{id}/complete → {job, report_id}.

    Raises PMSError(403) if worker_id mismatch, PMSError(409) if already closed.
    """
    url = pms_url.rstrip("/") + f"/api/kbs/queue/{job_id}/complete"
    body = {"worker_id": worker_id, "kbs_reference": kbs_reference, "notes": notes}
    return await _request("POST", url, headers=_auth_headers(token, idem_key), json_body=body)


async def fail_job(
    pms_url: str,
    token: str,
    job_id: str,
    worker_id: str,
    error: str,
    retry: bool,
    idem_key: Optional[str] = None,
) -> dict:
    """POST {PMS_URL}/api/kbs/queue/{id}/fail → {job, will_retry, next_retry_at}.

    PMS decides whether the job is retried (with backoff) or marked dead.
    `error` is truncated to 2000 chars to match the contract.
    """
    url = pms_url.rstrip("/") + f"/api/kbs/queue/{job_id}/fail"
    body = {"worker_id": worker_id, "error": (error or "")[:2000], "retry": bool(retry)}
    return await _request("POST", url, headers=_auth_headers(token, idem_key), json_body=body)
