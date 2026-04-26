# Syroce KBS Agent

Tek-çift tıkla kurulum sağlayan, Türk otelleri için **EGM Polis KBS** ve
**Jandarma KBS** sistemine misafir kayıtlarını otomatik gönderen Windows
masaüstü ajanı. Otel resepsiyonu Docker bilmek zorunda değil — ajan tek bir
`SyroceKBSAgent.exe` olarak kurulur ve görünmez bir Windows servisi (veya
sistem tepsisi ikonu) olarak arkada çalışır.

> Phase A (PMS kuyruk worker'ı), Phase B prep (idempotency + crash-replay +
> KBS gerçek-modu güvenlik kapıları), Phase C (Windows paketleme + DPAPI +
> servis modu) ve Phase D kısmı (multi-agent kimlik + sibling görünürlük)
> tamamlandı. SSE push entegrasyonu, PMS'in `/api/kbs/queue/stream` endpoint'i
> yayına girdiğinde aktive edilecek.

---

## Hızlı kurulum (otelci için)

1. `SyroceKBSAgent_Setup.exe` dosyasını indir → çalıştır → "Kur"a bas.
2. Tarayıcı `http://127.0.0.1:8765` adresini aç (otomatik açılır).
3. **Ayarlar** sayfasında:
   - PMS URL'sini gir,
   - Otel kodunu (`hotel_id`), e-posta + şifre ile **Giriş yap**,
   - KBS kurum (Polis / Jandarma), KBS tesis kodu, kullanıcı adı, şifre,
     KBS servis URL'sini gir,
   - **Kaydet**.
4. Bitti — ajan arkada her 15 saniyede bir PMS kuyruğunu okuyup misafirleri
   KBS'e gönderecek.

> Bilgisayar yeniden başladığında ajan otomatik gelir (NT servisi olarak
> kayıtlıdır). Tepsiye sağ tıklayıp **Çık**a basmadığın sürece kapanmaz.

---

## Mimari (kısa özet)

```
PMS (Syroce v1)  ⇄  KBS Bridge (bu uygulama)  ⇄  EGM/Jandarma KBS (SOAP)
                       ↑
                       loopback 127.0.0.1:8765 (yalnızca yerel UI)
```

- **Polling worker**: PMS'in `/api/kbs/queue` endpoint'inden `pending` işleri
  çeker, claim eder, KBS'e gönderir, sonucu rapor eder.
- **Idempotency-Key**: Her iş için (claim/complete/fail) per-job UUID
  diskte (`<DATA_DIR>/idem/`) kalıcı tutulur. PMS bu key ile dedup yapar →
  ağ kesintisinde yeniden deneme güvenli.
- **Crash-recovery journal**: PMS'e çağrı ÖNCE intent (`pending_complete`),
  SONRA ack yazılır. Çakışma sonrası restart'ta unacked intent'ler aynı
  idem-key ile tekrar gönderilir.
- **Windows servisi (Phase C)**: `pywin32` ile NT servisi, DPAPI ile
  credential şifreleme, Event Log ile dead-job uyarıları, RotatingFileHandler
  + PII maskeleme.
- **Multi-agent (Phase D)**: Aynı otelde iki resepsiyon PC'sinde aynı anda
  ajan çalışabilir. PMS'in atomik claim'i çift gönderimi engeller; her
  ajan diğer ajanları `/api/worker/status` üzerindeki `other_workers`
  listesinde görür. `worker_id` formatı: `agent-<host>-<mac4>-<uuid4>` —
  aynı hostname'li iki PC bile MAC kısa eki ile ayrılır.

---

## Mod seçimi (`MODE` env)

Tek `__main__.py` üç farklı mod ile çalışır:

| MODE      | Anlamı                                                                | Hedef                |
|-----------|-----------------------------------------------------------------------|----------------------|
| `server`  | Düz uvicorn — terminal/Docker/CI                                      | Geliştirme, CI       |
| `tray`    | uvicorn + sistem tepsisi ikonu                                        | Otelci masaüstü      |
| `service` | NT Servisi (admin gerektirir) — install/start/stop/remove komutları   | Otel üretim          |

```powershell
# Servis modunu kur (admin PowerShell):
SyroceKBSAgent.exe --installer

# Manuel servis komutları:
sc start  SyroceKBSAgent
sc stop   SyroceKBSAgent
sc query  SyroceKBSAgent
```

---

## Güvenlik

- **Loopback bind zorunlu**: HTTP API yalnızca `127.0.0.1:8765` üzerinde
  dinler. `HOST=0.0.0.0` veya bir LAN IP geçirsen bile **kesin reddedilir**
  (exit kodu 3); escape hatch yoktur. LAN'a açmak isteyen reverse proxy koysun.
- **CORS**: Yalnızca `http://127.0.0.1:8765` ve dev için `:5000`.
- **CSRF**: Tüm yazma endpoint'leri `X-KBS-Client: kbs-bridge` header'ı ister.
- **DPAPI** (Windows): Session ve KBS şifreleri Windows kullanıcısına bağlı
  CryptProtectData ile şifrelenir. Aynı makinedeki başka kullanıcı çözemez.
  Linux dev'de `cryptography.fernet` fallback kullanılır.
- **PII maskeleme**: Tüm log kayıtları TC, pasaport, doğum tarihi, ad/soyad
  alanlarını `***` ile maskeler. Job ID ve booking ID maskelenmez.
- **Single-instance**: Windows mutex ile aynı anda iki ajan çalışamaz.
- **Event Log**: Her dead-letter olan iş Application kanalına WARNING girer
  (Event ID 1001) → otel IT desteği görür.

---

## Log konumu

| Platform | Log yolu |
|----------|----------|
| Windows  | `%LOCALAPPDATA%\SyroceKBSAgent\logs\agent.log` |
| Linux    | `~/.local/share/SyroceKBSAgent/logs/agent.log` |

Rotating: 10 MB × 5 dosya. Dolan dosya `agent.log.1`, `agent.log.2`, ... olur.

---

## Geliştirme

```bash
# Backend (Replit Linux)
bash start_frontend.sh
# → backend :8000, frontend :5000

# Test
uv run pytest tests/ -q
# 116 test
```

### `WORKER_MODE` env (Phase D)

| Değer  | Davranış                                                          |
|--------|-------------------------------------------------------------------|
| `poll` | Default. Her `POLL_INTERVAL` saniyede bir PMS kuyruğunu okur.    |
| `auto` | Şimdilik `poll` ile aynı. PMS SSE endpoint'i hazır olunca SSE'ye geçecek. |
| `sse`  | **Henüz desteklenmiyor.** Açık reddedilir (sahte fallback yok).  |

`KBS_MODE=real` ile çalıştırırsan ve `kbs_client.REAL_SOAP_IMPLEMENTED=False`
ise (default), worker hiçbir iş işlemez (`session_status=kbs_not_ready`).
Bu **veri kaybı koruması**: Emniyet/Jandarma'dan gerçek WSDL+sertifika
gelmeden gerçek KBS gönderimi yapılmaz, ama PMS işleri silinmez —
materyaller geldikten sonra `_send_real()` doldurulup flag açılınca tüm
bekleyen işler işlenir.

---

## ⚠️ Geliştirici Anahtarı Rotasyonu (Tek Sefer)

Önceki commit'lerde `.devdata/.devkey` (geliştirme Fernet anahtarı) yanlışlıkla
git'e eklenmişti. Bu commit ile dosyalar repo'dan silindi ve `.devdata/`
gitignore'a alındı. Eğer bu repo herhangi bir yere push edildiyse:

```bash
# Yeni Fernet anahtarı üret
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# → SESSION_ENCRYPTION_KEY env değişkenine yazıp herkesin yeniden
#   login olmasını söyle (eski şifreli session'lar artık çözülemeyecek).
```

Production Windows'ta DPAPI kullanıldığı için bu anahtar zaten gerekli değil
— rotasyon yalnızca Linux dev ortamı için.

---

## Paketleme (Phase C)

```powershell
# Windows'ta:
pip install -r backend/requirements.txt
pyinstaller installer/SyroceKBSAgent.spec --clean --noconfirm
# → dist/SyroceKBSAgent.exe

# Inno Setup ile installer oluştur:
iscc installer\installer.iss
# → installer\Output\SyroceKBSAgent_Setup.exe
```
