"""Thin HTTP client to the hotel's Syroce PMS.

The PMS exposes a REST API. This module only proxies — no business logic.
"""
import httpx
from fastapi import HTTPException


class PMSError(HTTPException):
    pass


def _translate_error(resp: httpx.Response) -> PMSError:
    try:
        body = resp.json()
        detail = body.get("detail") or body.get("message") or resp.text
    except Exception:
        detail = resp.text or "PMS hatasi"
    return PMSError(status_code=resp.status_code, detail=detail)


async def login(pms_url: str, email: str, password: str) -> dict:
    """POST {PMS_URL}/api/auth/login → {access_token, token_type, user}"""
    url = pms_url.rstrip("/") + "/api/auth/login"
    async with httpx.AsyncClient(timeout=30.0, verify=True) as client:
        try:
            resp = await client.post(url, json={"email": email, "password": password})
        except httpx.RequestError as e:
            raise PMSError(
                status_code=503,
                detail=f"PMS'e ulasilamiyor: {e.__class__.__name__}",
            ) from e
    if resp.status_code >= 400:
        raise _translate_error(resp)
    return resp.json()


async def _authed_get(pms_url: str, token: str, path: str, params: dict | None = None) -> dict:
    url = pms_url.rstrip("/") + path
    async with httpx.AsyncClient(timeout=30.0, verify=True) as client:
        try:
            resp = await client.get(
                url,
                params=params,
                headers={"Authorization": f"Bearer {token}"},
            )
        except httpx.RequestError as e:
            raise PMSError(
                status_code=503,
                detail=f"PMS'e ulasilamiyor: {e.__class__.__name__}",
            ) from e
    if resp.status_code >= 400:
        raise _translate_error(resp)
    return resp.json()


async def _authed_post(pms_url: str, token: str, path: str, body: dict) -> dict:
    url = pms_url.rstrip("/") + path
    async with httpx.AsyncClient(timeout=30.0, verify=True) as client:
        try:
            resp = await client.post(
                url,
                json=body,
                headers={"Authorization": f"Bearer {token}"},
            )
        except httpx.RequestError as e:
            raise PMSError(
                status_code=503,
                detail=f"PMS'e ulasilamiyor: {e.__class__.__name__}",
            ) from e
    if resp.status_code >= 400:
        raise _translate_error(resp)
    return resp.json()


async def get_me(pms_url: str, token: str) -> dict:
    return await _authed_get(pms_url, token, "/api/kbs/me")


async def get_guests(pms_url: str, token: str, date: str) -> dict:
    return await _authed_get(pms_url, token, "/api/kbs/guests", params={"date": date})


async def post_report(pms_url: str, token: str, body: dict) -> dict:
    return await _authed_post(pms_url, token, "/api/kbs/report", body)


async def get_reports(pms_url: str, token: str, date_from: str, date_to: str) -> dict:
    return await _authed_get(
        pms_url, token, "/api/kbs/reports",
        params={"date_from": date_from, "date_to": date_to},
    )


async def get_report_detail(pms_url: str, token: str, report_id: str) -> dict:
    return await _authed_get(pms_url, token, f"/api/kbs/reports/{report_id}")
