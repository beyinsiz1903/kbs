"""Unit tests for pms_client using httpx.MockTransport.

We exercise URL/header/body shape against the v1 KBS Agent contract and the
typed PMSError surface (status code + detail) the worker depends on.
"""
import pytest
import httpx

import pms_client


def _patch_transport(monkeypatch, handler):
    """Make every AsyncClient created inside pms_client use a MockTransport."""
    real_init = httpx.AsyncClient.__init__

    def _init(self, *args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        kwargs.pop("verify", None)
        real_init(self, *args, **kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "__init__", _init)


# ---------- _validate_pms_url ----------

def test_validate_pms_url_rejects_loopback():
    with pytest.raises(pms_client.PMSError) as e:
        pms_client._validate_pms_url("http://localhost:8000")
    assert e.value.status_code == 400


def test_validate_pms_url_rejects_bad_scheme():
    with pytest.raises(pms_client.PMSError):
        pms_client._validate_pms_url("ftp://example.com")


def test_validate_pms_url_accepts_https():
    pms_client._validate_pms_url("https://pms.example.com")  # no raise


# ---------- login ----------

@pytest.mark.asyncio
async def test_login_sends_hotel_id_and_returns_token(monkeypatch):
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["body"] = request.read().decode()
        return httpx.Response(200, json={"access_token": "tok-123", "token_type": "bearer"})

    _patch_transport(monkeypatch, handler)
    res = await pms_client.login("https://pms.x.com", "hotel-A", "u@x.com", "pw")

    assert res["access_token"] == "tok-123"
    assert captured["url"] == "https://pms.x.com/api/auth/login"
    assert '"hotel_id":"hotel-A"' in captured["body"]
    assert '"email":"u@x.com"' in captured["body"]


@pytest.mark.asyncio
async def test_login_requires_hotel_id():
    with pytest.raises(pms_client.PMSError) as e:
        await pms_client.login("https://pms.x.com", "", "u@x.com", "pw")
    assert e.value.status_code == 400


@pytest.mark.asyncio
async def test_login_propagates_4xx_detail(monkeypatch):
    def handler(request):
        return httpx.Response(401, json={"detail": "Hatali sifre"})
    _patch_transport(monkeypatch, handler)
    with pytest.raises(pms_client.PMSError) as e:
        await pms_client.login("https://pms.x.com", "h", "u", "p")
    assert e.value.status_code == 401
    assert e.value.detail == "Hatali sifre"


@pytest.mark.asyncio
async def test_login_translates_timeout(monkeypatch):
    def handler(request):
        raise httpx.TimeoutException("read timed out")
    _patch_transport(monkeypatch, handler)
    with pytest.raises(pms_client.PMSError) as e:
        await pms_client.login("https://pms.x.com", "h", "u", "p")
    assert e.value.status_code == 504


# ---------- queue endpoints ----------

@pytest.mark.asyncio
async def test_list_queue_passes_status_param(monkeypatch):
    captured = {}

    def handler(request):
        captured["url"] = str(request.url)
        captured["auth"] = request.headers.get("authorization")
        return httpx.Response(200, json={"jobs": [], "stats": {"pending": 0}})

    _patch_transport(monkeypatch, handler)
    res = await pms_client.list_queue("https://pms.x.com", "tok", status="pending", limit=5)

    assert "status=pending" in captured["url"]
    assert "limit=5" in captured["url"]
    assert captured["auth"] == "Bearer tok"
    assert res["stats"]["pending"] == 0


@pytest.mark.asyncio
async def test_claim_job_posts_worker_id(monkeypatch):
    captured = {}

    def handler(request):
        captured["url"] = str(request.url)
        captured["body"] = request.read().decode()
        return httpx.Response(200, json={"job": {"id": "j1", "status": "in_progress"}})

    _patch_transport(monkeypatch, handler)
    res = await pms_client.claim_job(
        "https://pms.x.com", "tok", "j1", "agent-host-uuid", lease_seconds=60,
    )

    assert captured["url"].endswith("/api/kbs/queue/j1/claim")
    assert '"worker_id":"agent-host-uuid"' in captured["body"]
    assert '"lease_seconds":60' in captured["body"]
    assert res["job"]["status"] == "in_progress"


@pytest.mark.asyncio
async def test_claim_job_409_when_taken(monkeypatch):
    def handler(request):
        return httpx.Response(409, json={"detail": "Bu job baska bir agent tarafindan tutuluyor"})
    _patch_transport(monkeypatch, handler)
    with pytest.raises(pms_client.PMSError) as e:
        await pms_client.claim_job("https://pms.x.com", "tok", "j1", "agent")
    assert e.value.status_code == 409


@pytest.mark.asyncio
async def test_complete_job_posts_kbs_reference(monkeypatch):
    captured = {}

    def handler(request):
        captured["body"] = request.read().decode()
        return httpx.Response(200, json={"job": {"id": "j1", "status": "done"}})

    _patch_transport(monkeypatch, handler)
    res = await pms_client.complete_job("https://pms.x.com", "tok", "j1", "agent", "REF-1", notes="ok")

    assert '"kbs_reference":"REF-1"' in captured["body"]
    assert '"worker_id":"agent"' in captured["body"]
    assert res["job"]["status"] == "done"


@pytest.mark.asyncio
async def test_fail_job_posts_retry_flag_and_truncates_error(monkeypatch):
    captured = {}

    def handler(request):
        captured["body"] = request.read().decode()
        return httpx.Response(200, json={"will_retry": True, "next_retry_at": "2026-01-01T00:00:00Z"})

    _patch_transport(monkeypatch, handler)
    long_err = "x" * 5000
    res = await pms_client.fail_job("https://pms.x.com", "tok", "j1", "agent", long_err, True)

    # error truncated to 2000 chars per contract
    assert len(captured["body"]) < 2500
    assert '"retry":true' in captured["body"]
    assert res["will_retry"] is True


@pytest.mark.asyncio
async def test_request_rejects_loopback_url_even_with_token(monkeypatch):
    """Defense in depth: even if session is poisoned, _request() refuses loopback."""
    # No transport patch needed — we must fail before any network attempt.
    with pytest.raises(pms_client.PMSError) as e:
        await pms_client.list_queue("http://127.0.0.1:8000", "tok", status="pending")
    assert e.value.status_code == 400


@pytest.mark.asyncio
async def test_idempotency_key_header_passed(monkeypatch):
    captured = {}

    def handler(request):
        captured["idem"] = request.headers.get("idempotency-key")
        return httpx.Response(200, json={})

    _patch_transport(monkeypatch, handler)
    await pms_client.complete_job(
        "https://pms.x.com", "tok", "j1", "agent", "REF", idem_key="my-key",
    )
    assert captured["idem"] == "my-key"
