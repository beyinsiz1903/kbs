# KBS Bridge — PMS Bağlantılı KBS İnce İstemcisi

Otelin resepsiyon bilgisayarında (Docker üzerinde) çalışan, **tek kullanıcılı** bir
thin client. Otelci kendi PMS hesabıyla giriş yapar; uygulama PMS'ten misafirleri
çeker, seçilenleri Emniyet/Jandarma KBS web servisine bildirir, sonra PMS'e geri
"bildirildi" işareti basar.

## Mimari Özet

```
┌─────────────────────────────────────────────────────────────────┐
│  Otelin Bilgisayarı (Docker Compose)                            │
│                                                                  │
│   Tarayıcı (5000) ──▶  React UI                                 │
│                          │                                       │
│                          ▼                                       │
│                       FastAPI (8000)                             │
│                          │                                       │
│                ┌─────────┼──────────┐                            │
│                ▼         ▼          ▼                            │
│          PMS Client   KBS Client   Session Store                 │
│             │            │           │                           │
│             │            │           ▼                           │
│             │            │      /data/.session.enc (Fernet)      │
│             │            │      /data/settings.json              │
│             ▼            ▼                                       │
└─────────────│────────────│───────────────────────────────────────┘
              ▼            ▼
         Syroce PMS   EGM/Jandarma KBS
         (REST/JSON)  (SOAP/XML)
```

**Veritabanı yok.** PMS tek doğru kaynak. Yerelde sadece şifrelenmiş session
ve PMS URL ayarı tutulur.

## Kullanıcı Akışı

1. **Settings** — PMS URL + KBS bilgileri (tesis kodu, kullanıcı, şifre, servis URL)
2. **Login** — PMS e-posta + şifre + "Beni hatırla" → POST `{PMS_URL}/api/auth/login`
3. **Bugünün Misafirleri** — GET `{PMS_URL}/api/kbs/guests?date=...`, seçim, KBS'ye gönder
4. **KBS gönderim** — KBS'ye SOAP, sonra POST `{PMS_URL}/api/kbs/report` ile PMS'e işaret
5. **Rapor Geçmişi** — GET `{PMS_URL}/api/kbs/reports?date_from&date_to`

## Güvenlik

- **Session şifrelemesi:** Fernet (AES-128-CBC + HMAC). Anahtar `SESSION_ENCRYPTION_KEY`
  ortam değişkeninden okunur, image'a gömülmez. Anahtar üretmek için:
  ```bash
  python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
  ```
- **Konum:** `/data/.session.enc` (mod 600), Docker volume'da kalıcı.
- **Kapsam:** Token, PMS URL, kullanıcı bilgisi, **KBS şifresi** hepsi tek bir
  şifrelenmiş dosyada.
- **30 dk inactivity** → frontend timer + backend `last_active` kontrolü session'ı siler.
- **Manuel çıkış:** Settings ve sidebar'da "Çıkış" butonları (`/data/.session.enc` silinir).
- **TC/Pasaport** UI'da maskelenir, log dosyalarına yazılmaz.
- **HTTPS:** PMS ve KBS çağrılarında `verify=True`.

## Backend Dosyaları (`backend/`)

| Dosya | Görev |
|---|---|
| `server.py` | FastAPI; route'lar: `/api/auth/*`, `/api/settings`, `/api/guests`, `/api/kbs/submit`, `/api/reports*` |
| `session.py` | Fernet ile `/data/.session.enc` ve `/data/settings.json` yönetimi |
| `pms_client.py` | Syroce PMS'e ince HTTP proxy (`httpx`, 30s timeout, retry yok) |
| `kbs_client.py` | KBS web servisi göndericisi. **Şu an simülasyon** (`KBS_MODE=simulation`). Gerçek için `_send_real()` SOAP'ı doldurulacak |

## Frontend Dosyaları (`frontend/src/`)

| Dosya | Görev |
|---|---|
| `App.js` | 4 route: `/login`, `/`, `/raporlar`, `/ayarlar` |
| `contexts/AuthContext.js` | Oturum durumu + 30 dk inactivity timer + 401 yakalayıcı |
| `lib/api.js` | Axios kümeli, hata mesajı yardımcısı |
| `components/AppShell.jsx` | Sol menü + üst bar, "Çıkış" butonu |
| `pages/LoginPage.jsx` | PMS URL + e-posta + şifre + "Beni hatırla" |
| `pages/SettingsPage.jsx` | PMS URL + KBS dört alan + "Çıkış" butonu |
| `pages/GuestsPage.jsx` | Tarih seç, tablo, çoklu seçim, "KBS'ye Gönder" |
| `pages/ReportsPage.jsx` | Tarih aralığı, geçmiş raporlar tablosu |

## Hata Yönetimi (Spec'teki kurallar)

| HTTP | Davranış |
|---|---|
| 401 | Session silinir, login ekranına yönlendirilir |
| 403 | "Yetkiniz yok" toast (PMS'in döndüğü `detail`) |
| 404 | "Kayıt bulunamadı" |
| 503 | "PMS'e ulaşılamıyor" |
| diğer | PMS'in döndüğü Türkçe `detail` toast olarak gösterilir |

## Ortam Değişkenleri

| Değişken | Zorunlu | Açıklama |
|---|---|---|
| `SESSION_ENCRYPTION_KEY` | ✅ | 32-byte base64 Fernet anahtarı |
| `KBS_MODE` | hayır | `simulation` (varsayılan) veya `real` |
| `DATA_DIR` | hayır | Varsayılan `/data`, dev'de `./.devdata` |
| `CORS_ORIGINS` | hayır | Varsayılan `*` |

## Çalıştırma

### Replit dev ortamı (mevcut workflow)
`bash start_frontend.sh` — Fernet anahtarını `.devdata/.devkey` içinde otomatik
üretir, backend'i 8000, frontend'i 5000'de başlatır.

### Üretim (otelin bilgisayarı, Docker)
```bash
export SESSION_ENCRYPTION_KEY=$(python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
docker compose up -d
# → http://localhost:5000
```

## Yapılacaklar

- [ ] **`kbs_client._send_real()` doldurulacak.** Emniyet/Jandarma KBS WSDL'i ve
  XML şablonu kullanıcı tarafından sağlanınca. Şimdi `NotImplementedError` döner.
- [ ] Üretimde `SESSION_ENCRYPTION_KEY`'i `.env` dosyasına alıp `docker-compose --env-file` ile vermek.
- [ ] (İsteğe bağlı) Sertifikalı KBS endpoint'i için mTLS sertifikası volume mount.

## Tasarım Kararları

- **Çok kiracılı yapı silindi.** Her otel kendi PMS'i ile konuşur, kendi KBS
  hesabıyla bildirim gönderir; merkezi bir admin paneline gerek yok.
- **MongoDB silindi.** Hiçbir veri yerel olarak tutulmaz; PMS otoriter.
- **JWT/şifre hash silindi.** Auth'u PMS yapıyor.
- **DPAPI yerine Fernet.** Docker (Linux container) seçildiği için Windows
  DPAPI kullanılamadı; pratikte eşdeğer (anahtar env'de, dosya mod 600, volume).
