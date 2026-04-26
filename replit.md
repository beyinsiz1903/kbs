# KBS Bridge — Otonom KBS Bildirim Ajanı (Syroce KBS Agent v1)

Otelin resepsiyon bilgisayarında (Docker üzerinde) çalışan, **tek operatörlü
otonom ajan**. Operatör bir kez PMS hesabıyla giriş yapar; ajan arkada 7/24
PMS'in KBS kuyruğunu (`/api/kbs/queue`) yoklar, bekleyen işleri claim eder,
KBS web servisine (Phase A: simülasyon, Phase B: gerçek SOAP) gönderir,
sonucu PMS'e geri raporlar. Operatör butonla tetiklemez — yalnızca durumu
izler ve ayarları yönetir.

## Mimari Özet

```
┌─────────────────────────────────────────────────────────────────┐
│  Otelin Bilgisayarı (Docker Compose)                            │
│                                                                  │
│   Tarayıcı (5000) ──▶  React UI (Worker Durumu + Ayarlar)       │
│                          │                                       │
│                          ▼                                       │
│                       FastAPI (8000) ──▶ asyncio Worker         │
│                          │                  (her 15 sn poll)    │
│                ┌─────────┼──────────┐       │                   │
│                ▼         ▼          ▼       ▼                   │
│          PMS Client   KBS Client   Session  worker_id           │
│             │            │           │       │                  │
│             │            │           ▼       ▼                  │
│             │            │   /data/.session.enc   /data/worker_id│
│             ▼            ▼                                       │
└─────────────│────────────│───────────────────────────────────────┘
              ▼            ▼
         Syroce PMS   EGM/Jandarma KBS
         (REST/JSON,  (SOAP/XML,
          v1 KBS       Phase B'de
          Agent        gerçek bağlanır)
          contract)
```

**Veritabanı yok.** PMS tek doğru kaynak; ajan stateless. Yerelde sadece
şifrelenmiş session, PMS URL/hotel_id ayarı ve persistente `worker_id`.

## Operatör Akışı

1. **Login** — PMS URL + `hotel_id` + e-posta + şifre → POST `{PMS_URL}/api/auth/login`.
2. **Settings** — KBS bilgileri (tesis kodu, kullanıcı, şifre, servis URL) — Phase B
   gerçek SOAP'a bağlanırken kullanılacak.
3. **Worker Durumu** — Otomatik tarama her 15 sn. Operatör son turun zamanı,
   son hata, kuyruk istatistikleri (pending/in_progress/done/failed/dead),
   "claim/complete/fail" sayaçları ve son 20 işlem listesini görür.
4. **Şimdi Tara** — Operatör erken tetikleme isteyebilir.

## Worker Davranışı

| Durum | Davranış |
|---|---|
| `next_retry_at` geçmemiş | İş atlanır, sonraki turda denenir |
| Claim 409 | Başka ajan tutmuş, atla |
| KBS başarılı | `complete(kbs_reference)` |
| Timeout/5xx/network | `fail(retry=True)` — PMS exponential backoff verir |
| 4xx (validasyon) | `fail(retry=False)` — PMS dead'e atar |
| 429 | `fail(retry=True)` + uyarı log |
| Beklenmeyen exception | `fail(retry=True)` + tam stack trace |
| 401 | Oturum silinir, frontend login'e düşer |

## Güvenlik

- **PMS URL doğrulaması:** Her dış çağrıda `_validate_pms_url` çalışır;
  loopback/self-host yasak (SSRF koruması).
- **CSRF:** `X-KBS-Client: kbs-bridge` header zorunlu (CORS preflight forced).
- **Session şifrelemesi:** Fernet (AES-128-CBC + HMAC). Anahtar
  `SESSION_ENCRYPTION_KEY` ortam değişkeninden okunur, image'a gömülmez.
- **Konum:** `/data/.session.enc` (mod 600), Docker volume'da kalıcı.
- **Kapsam:** PMS token, hotel_id, kullanıcı bilgisi, **KBS şifresi** hepsi
  tek şifrelenmiş dosyada.
- **30 dk inactivity** → frontend timer + backend `last_active` kontrolü.
- **TC/Pasaport** UI'da maskelenir, log dosyalarına yazılmaz.
- **HTTPS:** PMS ve KBS çağrılarında `verify=True`.

## Backend Dosyaları (`backend/`)

| Dosya | Görev |
|---|---|
| `server.py` | FastAPI; route'lar: `/api/auth/*`, `/api/settings`, `/api/worker/status`, `/api/worker/poll-now` |
| `worker.py` | Otonom polling task (asyncio). FastAPI startup'ta başlar, shutdown'da temiz kapanır. `WORKER_MODE` ile `poll`/`sse`/`auto` arasında geçiş |
| `sse_client.py` | PMS `/api/kbs/queue/stream` SSE istemcisi (`httpx-sse`); `Authorization: Bearer` + `Last-Event-ID` resume desteği |
| `session.py` | Fernet ile `/data/.session.enc` ve `/data/settings.json` yönetimi |
| `pms_client.py` | Syroce PMS v1 KBS Agent contract istemcisi (login, me, queue list/claim/complete/fail) — `idem_key` kwarg destekli |
| `kbs_client.py` | KBS web servisi göndericisi. **Şu an simülasyon** (`KBS_MODE=simulation`); Phase B'de gerçek SOAP |
| `idem.py` | Per-job kalıcı Idempotency-Key (`<DATA_DIR>/idem/{job_id}.json`); claim/complete/fail için stable UUID |
| `journal.py` | `submissions.jsonl`; `find_unacked()` ile pending_complete/fail eşleşmemiş kayıtları tarar (replay için) |

## Frontend Dosyaları (`frontend/src/`)

| Dosya | Görev |
|---|---|
| `App.js` | 3 route: `/login`, `/`, `/ayarlar` |
| `contexts/AuthContext.js` | Oturum durumu + 30 dk inactivity timer + 401 yakalayıcı |
| `lib/api.js` | Axios kümeli, hata mesajı yardımcısı |
| `components/AppShell.jsx` | Sol menü (Worker Durumu + Ayarlar) + üst bar |
| `pages/LoginPage.jsx` | PMS URL + **hotel_id** + e-posta + şifre |
| `pages/WorkerStatusPage.jsx` | Worker canlı durumu, kuyruk istatistikleri, son işlemler, "şimdi tara" |
| `pages/SettingsPage.jsx` | PMS URL + KBS dört alan + "Çıkış" butonu |

## Worker Identity

- `<DATA_DIR>/worker_id` dosyasında kalıcı: `agent-<hostname>-<uuid4>`.
- Restart'lar arası değişmez. Tek dosya, mod 600.
- Aynı PMS'e birden fazla ajan bağlanırsa her biri kendi kimliğiyle claim atar
  (Phase D'de daha sıkı koordinasyon).

## Hata Yönetimi (PMS yanıtı)

| HTTP | Davranış |
|---|---|
| 401 | Session silinir, login ekranına yönlendirilir + worker `session=invalid` |
| 403 | UI'da Türkçe `detail` toast |
| 404/409 | Job artık yok / başka tarafından alınmış — atlanır |
| 429 | retry=True + uyarı log |
| 5xx / timeout / network | retry=True |
| diğer 4xx | retry=False (dead) |

## Ortam Değişkenleri

| Değişken | Zorunlu | Açıklama |
|---|---|---|
| `SESSION_ENCRYPTION_KEY` | ✅ | 32-byte base64 Fernet anahtarı |
| `KBS_MODE` | hayır | `simulation` (varsayılan) veya `real` (Phase B) |
| `DATA_DIR` | hayır | Varsayılan `/data`, dev'de `./.devdata` |
| `POLL_INTERVAL` | hayır | Saniye, varsayılan 15 |
| `WORKER_MODE` | hayır | `poll` (varsayılan) / `sse` / `auto`. `sse` ve `auto` PMS'in `/api/kbs/queue/stream` SSE endpoint'ine bağlanır; her `new_job` event'inde polling tetiklenir. `auto` 3 ardışık SSE başarısızlığında poll'a düşer |
| `CORS_ORIGINS` | hayır | Varsayılan `http://localhost:5000` |
| `PUBLIC_HOSTNAME` | hayır | Self-host engellemek için (opsiyonel) |

## Çalıştırma

### Replit dev ortamı (workflow `Start application`)
`bash start_frontend.sh` — Fernet anahtarını `.devdata/.devkey` içinde otomatik
üretir, backend'i 8000, frontend'i 5000'de başlatır. Worker arkada otomatik döner.

### Üretim (otelin bilgisayarı, Docker)
```bash
export SESSION_ENCRYPTION_KEY=$(python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
docker compose up -d
# → http://localhost:5000
```

### Testler
```bash
uv run pytest tests/ -q
```
116 test (pms_client mock httpx + worker davranış senaryoları + idem + journal replay + real-mode guards + Phase C: secure_storage Fernet fallback + PII maskeleme + eventlog no-op + Phase D: multi-agent atomik claim + SSE client/supervisor).

## Faz Planı

- **Phase A (TAMAMLANDI):** Polling worker iskeleti, queue endpoint'leri,
  hotel_id ile login, Worker Status UI, simülasyon KBS.
- **Phase B (PARÇALI — şemadan bağımsız hazırlık YAPILDI):**
  - ✅ `backend/idem.py` — per-job Idempotency-Key kalıcılığı (claim/complete/fail UUID'leri).
  - ✅ Worker journal refaktörü — `pending_complete` PMS'e çağrı ÖNCE, `complete_ack` SONRA;
    `pending_fail` / `fail_ack` aynı şekilde. `journal.find_unacked()` ile crash-recovery.
  - ✅ Crash-recovery replay — her oturum başlangıcında bir kez çalışır, asılı kalmış
    pending kayıtlarını PMS'e tekrar gönderir (idem key sayesinde PMS de-dup eder).
  - ✅ `KBS_MODE=real` + eksik `KBS_WSDL_URL` → worker **başlamayı reddeder** (`session_status=refused`).
  - ✅ **`kbs_client.REAL_SOAP_IMPLEMENTED=False`** flag'i: SOAP doldurulana kadar real mode iş **işlemeyi reddeder** (`session_status=kbs_not_ready`).
    `_send_real`'in `KBSConfigError`'unun `fail_job(retry=False)` zincirine düşüp PMS'in işi dead-letter'a atmasını engeller (veri kaybı koruması).
  - ✅ Real modda session-tarafı eksik (kbs_kurum vb.) → polling'i atlar (`session_status=kbs_not_configured`).
  - ✅ Settings UI'a Polis/Jandarma radyosu, backend `kbs_kurum` validasyonu.
  - ✅ `zeep` + `requests` bağımlılıkları eklendi.
  - ⏳ **Bekleniyor (Emniyet/Jandarma):** WSDL URL/dosyası, mTLS sertifikası (.pfx veya cert/key),
    test endpoint. Gelince `kbs_client._send_real()` doldurulup canlıya alınır.
- **Phase C (TAMAMLANDI — Linux'ta yazıldı, Windows'ta sınanmalı):**
  - ✅ `backend/secure_storage.py` — Windows DPAPI / Linux Fernet fallback. Session.py Fernet'i kaldırıldı.
  - ✅ `backend/log_setup.py` — RotatingFileHandler (10 MB × 5) + PII maskeleme filter
    (TC, pasaport, doğum tarihi, ad/soyad/şifre alanları → `***`). Job ID maskelenmez.
  - ✅ `backend/eventlog.py` — Windows Event Log writer (Application kanalı).
    Dead-letter olan her iş için Event ID 1001 WARNING. Linux'ta sessiz no-op.
  - ✅ `backend/single_instance.py` — Windows mutex / Linux flock. İkinci instance exit(2).
  - ✅ `backend/tray.py` — `pystray` + `Pillow` ile sistem tepsisi (Durum/Ayarlar/Loglar/Çık).
  - ✅ `backend/service.py` — `pywin32 ServiceFramework` ile NT servisi
    (install/start/stop/remove/debug komutları).
  - ✅ `backend/app_runtime.py` — Loopback bind sertleştirme (`HOST=0.0.0.0` reddedilir).
  - ✅ `backend/__main__.py` — `MODE=server|tray|service` switch.
  - ✅ `installer/SyroceKBSAgent.spec` (PyInstaller) + `installer/installer.iss` (Inno Setup).
  - ✅ `requirements.txt` — Windows-only deps `; sys_platform == 'win32'` marker'ı ile.
  - ✅ Sızdırılmış `.devdata/.devkey` git'ten temizlendi; README'ye rotasyon uyarısı.
  - ⏳ Gerçek `.exe` build + Windows servis testi otelci PC'sinde yapılmalı (Replit'te imkansız).
- **Phase D (PARÇALI):**
  - ✅ Çoklu ajan koordinasyonu (worker_id MAC slug + `other_workers` paneli + atomik claim testleri).
  - ✅ SSE push kanalı (`backend/sse_client.py` + `worker._sse_supervisor`):
    `WORKER_MODE=sse|auto` ile `/api/kbs/queue/stream` dinlenir; her `new_job`
    event'i `poll_now`'u tetikler — claim/idem/journal akışı poll'la birebir aynı
    kalır. Reconnect 1s→2s→4s→8s→16s→30s exp backoff. `auto` 3 ardışık başarısızlıkta
    60s idle'a düşer (poll loop yedek). 401/403 → oturum temizlenir.
  - ⏳ **Bekleniyor (PMS ekibi):** `/api/kbs/queue/stream` endpoint'inin canlı PMS'te yayına alınması.
    Ajan tarafı hazır; sözleşme: `event: new_job\ndata: {"job_id":"...","tenant_id":"..."}`,
    `Authorization: Bearer <token>`, opsiyonel `Last-Event-ID` resume, `event: heartbeat` keep-alive.

## Tasarım Kararları

- **Otonom ajan, manuel tetik yok.** Operatör butonla göndermez; PMS kuyruğu
  doğru kaynak. UI sadece durum gösterir.
- **PMS gerçeğin tek kaynağı.** Ajan stateless. Yerel disk yalnızca session +
  worker_id tutar.
- **Tek kullanıcı modeli.** Resepsiyon makinesi başına bir oturum.
- **MongoDB / JWT / şifre hash silindi.** Auth'u PMS yapar; ajan token taşır.
- **DPAPI yerine Fernet (yalnızca Linux dev).** `backend/secure_storage.py` Windows'ta DPAPI
  kullanır; Linux'ta `SESSION_ENCRYPTION_KEY` ile Fernet'e düşer.
