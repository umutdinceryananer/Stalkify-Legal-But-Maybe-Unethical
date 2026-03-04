# Spotify-OSINT

A Python service that watches public Spotify playlists for new track additions and sends you a Telegram notification the moment something gets added. Runs automatically every 30 minutes via GitHub Actions, costs nothing, and lives rent-free in your head — just like the person whose playlists you're watching.

---

## How it works

1. Fetches the playlist's `snapshot_id` from the Spotify API — a unique fingerprint that changes on any modification.
2. If the snapshot hasn't changed since the last run, it does nothing (no browser, no cost, no drama).
3. If it has changed, it launches a headless Chromium browser (Playwright) to scrape the new tracks from the Spotify web player — because Spotify removed public track access from their API in early 2026.
4. Sends a Telegram notification for each new track.
5. Fetches the track's lyrics from [Lrclib](https://lrclib.net) and sends them to Groq (llama-3.3-70b-versatile) for a short emotional analysis, delivered as a second Telegram message.
6. Saves everything to a Supabase (PostgreSQL) database.

---

## Prerequisites

- Python 3.12+
- A [Spotify Developer](https://developer.spotify.com/dashboard) app (free)
- A [Supabase](https://supabase.com) project (free tier is enough)
- A Telegram bot (via [@BotFather](https://t.me/BotFather))
- A [Groq](https://console.groq.com) API key (free)
- A GitHub account (for the automated workflow)

---

## Setup

### 1. Clone the repo

```bash
git clone https://github.com/your-username/spotify-osint.git
cd spotify-osint
```

### 2. Create a virtual environment and install dependencies

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
```

### 3. Create a Spotify app

Go to [developer.spotify.com/dashboard](https://developer.spotify.com/dashboard), create an app, and note your **Client ID** and **Client Secret**.

### 4. Create a Telegram bot

Message [@BotFather](https://t.me/BotFather) on Telegram, create a new bot, and get your **bot token**. Then send any message to your bot and visit:

```
https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates
```

Find your **chat ID** in the response.

### 5. Set up Supabase

Create a project at [supabase.com](https://supabase.com). In the SQL editor, run `schema.sql`:

```sql
CREATE TABLE playlists (
    id          VARCHAR     PRIMARY KEY,
    name        VARCHAR     NOT NULL,
    owner_id    VARCHAR     NOT NULL,
    is_active   BOOLEAN     DEFAULT TRUE,
    added_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE tracked_tracks (
    track_id    VARCHAR     NOT NULL,
    playlist_id VARCHAR     NOT NULL REFERENCES playlists(id),
    track_name  VARCHAR     NOT NULL,
    artist_names TEXT[]     NOT NULL,
    album_name  VARCHAR,
    spotify_url VARCHAR,
    added_at    TIMESTAMPTZ,
    detected_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (track_id, playlist_id)
);
```

Then run this migration to add the snapshot column:

```sql
ALTER TABLE playlists ADD COLUMN snapshot_id TEXT;
```

Go to **Project Settings → Database** and copy the **Session Pooler** connection string (the one that looks like `postgresql://postgres.xxx:password@aws-0-region.pooler.supabase.com:5432/postgres`). Do **not** use the direct connection string — it requires IPv6 and will fail on GitHub Actions.

### 6. Configure environment variables

```bash
cp .env.example .env
```

Fill in `.env`:

```
SPOTIFY_CLIENT_ID=your_client_id
SPOTIFY_CLIENT_SECRET=your_client_secret
DATABASE_URL=your_supabase_session_pooler_url
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
GROQ_API_KEY=your_groq_api_key
```

### 7. Add playlists to monitor

The playlist must be **public**. Grab the playlist ID from its Spotify URL (`open.spotify.com/playlist/<ID>`):

```bash
python -m scripts.manage_playlists add <playlist_id>
```

Other commands:

```bash
python -m scripts.manage_playlists list           # show all monitored playlists
python -m scripts.manage_playlists remove <id>    # stop monitoring a playlist
```

### 8. Run the monitor

```bash
python -m src.monitor
```

The first run scans every playlist in full to build a baseline — no notifications are sent. Subsequent runs only trigger when the snapshot changes.

---

## GitHub Actions (automated)

The workflow in `.github/workflows/monitor.yml` runs every 30 minutes automatically.

Add the following secrets to your GitHub repository under **Settings → Secrets and variables → Actions**:

| Secret | Value |
|---|---|
| `SPOTIFY_CLIENT_ID` | From your Spotify app |
| `SPOTIFY_CLIENT_SECRET` | From your Spotify app |
| `DATABASE_URL` | Supabase session pooler URL |
| `TELEGRAM_BOT_TOKEN` | From BotFather |
| `TELEGRAM_CHAT_ID` | Your Telegram chat ID |
| `GROQ_API_KEY` | From console.groq.com |

You can also trigger the workflow manually from the **Actions** tab.

---

## Ethical disclaimer

This project only monitors **public** playlists. It does not access private playlists, user accounts, or any data that isn't already visible to anyone with a Spotify link. Is it weird to automatically track someone's taste in music? I think it's weird, but I know I'm not alone.

---

---

# Spotify-OSINT

Herkese açık Spotify playlistlerini izleyen ve yeni bir şarkı eklendiği anda sana Telegram bildirimi gönderen bir Python servisi. GitHub Actions üzerinden 30 dakikada bir otomatik çalışır, ücretsizdir ve kimseyi peşime takmadığı sürece çalışacak.

---

## Nasıl çalışır

1. Spotify API'den playlistin `snapshot_id`'sini çeker — herhangi bir değişiklikte değişen benzersiz bir parmak izi.
2. Snapshot son çalıştırmadan beri değişmemişse hiçbir şey yapmaz (tarayıcı açılmaz, işlem olmaz).
3. Değiştiyse headless Chromium tarayıcı (Playwright) açarak Spotify web playerdan yeni şarkıları çeker — Spotify 2026 başında herkese açık playlist erişimini API'den kaldırdığı için.
4. Her yeni şarkı için Telegram bildirimi gönderir.
5. [Lrclib](https://lrclib.net)'den şarkı sözlerini çekip Groq'a (llama-3.3-70b-versatile) göndererek kısa bir duygusal analiz üretir, ikinci bir Telegram mesajı olarak iletir.
6. Her şeyi Supabase (PostgreSQL) veritabanına kaydeder.

---

## Gereksinimler

- Python 3.12+
- [Spotify Developer](https://developer.spotify.com/dashboard) uygulaması (ücretsiz)
- [Supabase](https://supabase.com) projesi (ücretsiz tier yeterli)
- Telegram botu ([@BotFather](https://t.me/BotFather) üzerinden)
- [Groq](https://console.groq.com) API key'i (ücretsiz)
- GitHub hesabı (otomatik çalıştırma için)

---

## Kurulum

### 1. Repoyu klonla

```bash
git clone https://github.com/kullanici-adin/spotify-osint.git
cd spotify-osint
```

### 2. Sanal ortam oluştur ve bağımlılıkları yükle

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
```

### 3. Spotify uygulaması oluştur

[developer.spotify.com/dashboard](https://developer.spotify.com/dashboard) adresine gidip uygulama oluştur. **Client ID** ve **Client Secret**'ı not al.

### 4. Telegram botu oluştur

Telegram'da [@BotFather](https://t.me/BotFather)'a mesaj at, yeni bot oluştur, **bot token**'ını al. Sonra botuna herhangi bir mesaj gönder ve şu adrese git:

```
https://api.telegram.org/bot<TOKEN>/getUpdates
```

Gelen yanıttaki **chat ID**'yi not al.

### 5. Supabase kurulumu

[supabase.com](https://supabase.com)'da proje oluştur. SQL editöründe `schema.sql`'i çalıştır:

```sql
CREATE TABLE playlists (
    id          VARCHAR     PRIMARY KEY,
    name        VARCHAR     NOT NULL,
    owner_id    VARCHAR     NOT NULL,
    is_active   BOOLEAN     DEFAULT TRUE,
    added_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE tracked_tracks (
    track_id    VARCHAR     NOT NULL,
    playlist_id VARCHAR     NOT NULL REFERENCES playlists(id),
    track_name  VARCHAR     NOT NULL,
    artist_names TEXT[]     NOT NULL,
    album_name  VARCHAR,
    spotify_url VARCHAR,
    added_at    TIMESTAMPTZ,
    detected_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (track_id, playlist_id)
);
```

Ardından bu migration'ı çalıştır:

```sql
ALTER TABLE playlists ADD COLUMN snapshot_id TEXT;
```

**Project Settings → Database** kısmından **Session Pooler** bağlantı stringini kopyala (`postgresql://postgres.xxx:password@aws-0-region.pooler.supabase.com:5432/postgres` gibi görünen). Direkt bağlantı stringini kullanma — IPv6 gerektiriyor ve GitHub Actions'ta çalışmıyor.

### 6. Ortam değişkenlerini ayarla

```bash
cp .env.example .env
```

`.env` dosyasını doldur:

```
SPOTIFY_CLIENT_ID=spotify_client_id
SPOTIFY_CLIENT_SECRET=spotify_client_secret
DATABASE_URL=supabase_session_pooler_url
TELEGRAM_BOT_TOKEN=bot_token
TELEGRAM_CHAT_ID=chat_id
GROQ_API_KEY=groq_api_key
```

### 7. Takip edilecek playlistleri ekle

Playlist **herkese açık** olmalı. Playlist ID'sini Spotify URL'inden al (`open.spotify.com/playlist/<ID>`):

```bash
python -m scripts.manage_playlists add <playlist_id>
```

Diğer komutlar:

```bash
python -m scripts.manage_playlists list           # takip edilen playlistleri listele
python -m scripts.manage_playlists remove <id>    # takibi bırak
```

### 8. Monitörü çalıştır

```bash
python -m src.monitor
```

İlk çalıştırmada her playlist baştan taranarak baseline oluşturulur — bildirim gönderilmez. Sonraki çalıştırmalarda yalnızca snapshot değiştiğinde aksiyon alınır.

---

## GitHub Actions (otomatik)

`.github/workflows/monitor.yml` her 30 dakikada bir otomatik çalışır.

GitHub reposunda **Settings → Secrets and variables → Actions** altına şu secretları ekle:

| Secret | Değer |
|---|---|
| `SPOTIFY_CLIENT_ID` | Spotify uygulamasından |
| `SPOTIFY_CLIENT_SECRET` | Spotify uygulamasından |
| `DATABASE_URL` | Supabase session pooler URL |
| `TELEGRAM_BOT_TOKEN` | BotFather'dan |
| `TELEGRAM_CHAT_ID` | Telegram chat ID'n |
| `GROQ_API_KEY` | console.groq.com'dan |

Workflow'u **Actions** sekmesinden manuel olarak da tetikleyebilirsin.

---

## Etik sorumluluk reddi

Bu proje yalnızca **herkese açık** playlistleri izler. Özel playlistlere, kullanıcı hesaplarına ya da Spotify linki olan herkesin zaten göremeyeceği hiçbir veriye erişemez. Birinin müzik zevkini otomatik olarak takip etmek tuhaf mı? Bence tuhaf, ama yalnız olmadığımı biliyorum.
