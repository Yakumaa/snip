# Snip — Rate-Limited URL Shortener with Analytics

A full-stack URL shortener. Shorten links with random or custom aliases, set an optional expiry, get a QR code for any link, and track clicks with 7-day time-series charts plus device/browser/OS/country/referrer breakdowns. Submitted URLs are checked against SSRF/private-network targets and Google Safe Browsing before being shortened. Interactive API docs are served at `/api/docs` (Swagger UI)..

**Live:** https://snip.shirishmaharjan8.com.np

**Stack:** Python 3.12 / Flask · React 18 / Vite · PostgreSQL 16 · Redis · Docker · Railway · Vercel

## Project Structure

```
snip/
├── backend/                  # Flask API
│   ├── app/
│   │   ├── middleware/
│   │   │   └── rate_limiter.py   # Redis-backed sliding-window rate limiter
│   │   ├── models/
│   │   │   └── url.py            # ShortenedUrl + Click ORM models
│   │   ├── routes/
│   │   │   └── urls.py           # All API endpoints
│   │   ├── services/
│   │   │   ├── safe_browsing.py  # Google Safe Browsing check (fails open)
│   │   │   └── geolocation.py    # ip-api.com lookup, Redis-cached
│   │   ├── utils/
│   │   │   ├── helpers.py        # URL/alias validation, SSRF check, expiry parsing
│   │   │   ├── qr_code.py        # QR PNG generation
│   │   │   └── user_agent.py     # Browser/OS/device parsing
│   │   ├── templates/
│   │   │   └── preview.html      # "You're about to visit X" confirmation page
│   │   ├── schemas.py            # Marshmallow schemas (OpenAPI docs only)
│   │   ├── extensions.py
│   │   └── config.py
│   ├── migrations/               # Alembic migration history
│   ├── tests/                    # Tests for the rate limiter
│   ├── Dockerfile
│   ├── railway.toml
│   ├── requirements.txt
│   └── wsgi.py
├── frontend/                 # React + Vite
│   ├── src/
│   │   ├── components/
│   │   │   ├── UrlShortener.jsx          # URL input + 429 countdown + QR/copy
│   │   │   ├── AnalyticsDashboard.jsx    # URL list + Chart.js line chart + breakdowns
│   │   │   ├── ExpiredLinkPage.jsx       # Shown when a link has expired
│   │   │   └── QrCodeBlock.jsx           # QR display + download
│   │   ├── hooks/useCountdown.js
│   │   ├── services/api.js               # Centralised fetch client
│   │   └── App.jsx
│   ├── Dockerfile
│   ├── vercel.json                       # Prod proxy config — see Deployment
│   └── vite.config.js
├── docker-compose.yml
├── .env.example
└── README.md
```

## Quick Start

### Prerequisites
- [Docker](https://docs.docker.com/get-docker/) and Docker Compose

### 1. Clone & configure

```bash
git clone https://github.com/Yakumaa/snip.git
cd snip
cp .env.example .env
```
Edit `.env` if you want to change any defaults (the defaults work out of the box):

### 2. Start all services

```bash
docker compose up --build
```

| Service  | URL                     |
|----------|-------------------------|
| Frontend | http://localhost:5173   |
| Backend  | http://localhost:5000   |
| Postgres | localhost:5432 (user: shortener, db: shortener_db)  |

<!-- ### 3. Run database migrations

In a separate terminal (after the containers are up):

```bash
docker compose exec backend flask db upgrade
``` -->

### 3. (Optional) Seed / verify DB

```bash
docker compose exec db psql -U shortener -d shortener_db
```

## Running Without Docker (Local Dev)
 
**Backend:**
```bash
cd backend
python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
# Create a local .env or export variables, then:
flask db upgrade
flask run
```
 
**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

## Deployment

Live at **https://snip.shirishmaharjan8.com.np**.

```
Production stack:
├── Postgres (managed)   ← Railway
├── Redis (managed)      ← Railway
├── Backend (Flask)      ← Railway, deployed from GitHub, custom Dockerfile
└── Frontend (static)    ← Vercel, deployed from /frontend
```

### Architecture: one domain, no CORS

The frontend and backend are two separate deployments, but the public app is served from a single origin. `frontend/vercel.json` proxies backend-bound requests through Vercel's edge via `rewrites`, so the browser only ever talks to `snip.shirishmaharjan8.com.np` — Vercel forwards matching requests to Railway server-side and pipes the response back unchanged. This is the same idea as the `/api` proxy in `vite.config.js` for local dev, just applied in production:

| Path pattern | Proxied to |
|---|---|
| `/api/:path*` | Railway backend — all API calls, including `/api/docs` (Swagger) |
| `/go/:alias` | Railway backend — click-tracking redirect |
| `/:alias` (exactly 6 chars, `[a-zA-Z0-9_-]`) | Railway backend — short-link preview page |
| anything else | `index.html` (the React app) |

Because of this, `VITE_API_BASE_URL` is left **empty** in production — `frontend/src/services/api.js` falls back to relative paths (`fetch('/api/urls')`), which is exactly what lets the Vercel rewrite intercept them. It's only set to an absolute URL for local dev against a non-proxied backend.

### Backend (Railway)

1. Push to GitHub, create a Railway project from the repo, and add the **Postgres** and **Redis** plugins — Railway auto-injects `DATABASE_URL` and `REDIS_URL` into the service.
2. Set these additional service variables:

   | Variable | Value |
   |---|---|
   | `SECRET_KEY` | a long random string |
   | `PUBLIC_BASE_URL` | `https://snip.shirishmaharjan8.com.np` — used to build `short_url` / `qr_code_url` in API responses, so links are handed out on the public domain rather than Railway's internal `*.up.railway.app` one |
   | `FRONTEND_ORIGIN` | `https://snip.shirishmaharjan8.com.np` — used for CORS; mostly a defense-in-depth fallback now that the proxy makes requests same-origin |
   | `RATE_LIMIT_MAX_REQUESTS` | `5` |
   | `RATE_LIMIT_WINDOW_SECONDS` | `60` |
   | `SAFE_BROWSING_API_KEY` | optional — Safe Browsing checks fail open (URLs are still shortened) if unset |
   | `PORT` | `5000` — Railway injects its own `PORT` at runtime and expects the app to bind to it; this pins it to a known value so it matches the Networking panel's target port |

3. Custom start command (also baked into `backend/Dockerfile`'s `CMD`):
   ```
   flask db upgrade && gunicorn --bind 0.0.0.0:${PORT:-5000} --workers 4 --worker-class gthread --threads 2 --access-logfile - --error-logfile - wsgi:app
   ```
   Migrations run on every boot (idempotent — Alembic no-ops if already at head). Multiple gunicorn workers are safe because the rate limiter's state lives in Redis, not in-process memory.
4. In Railway's Networking panel, generate a domain and set the target port to match `PORT` (`5000`).
5. Health checks (`backend/railway.toml`) hit `GET /api/health`, which pings the DB and returns `503` if it's unreachable.

### Frontend (Vercel)

1. Import the repo into Vercel, root directory `frontend/`.
2. `vercel.json` already sets `buildCommand` (`npm run build`) and `outputDirectory` (`dist`) — no manual build config needed.
3. Leave `VITE_API_BASE_URL` unset (see architecture note above).
4. Add the custom domain `snip.shirishmaharjan8.com.np` under Project → Domains, and point a CNAME at the value Vercel provides.

### Custom domain

Both platforms auto-issue TLS certs (Let's Encrypt) once DNS resolves — usually within minutes of the CNAME propagating. Only the frontend needs a DNS record; the backend stays on its Railway-generated domain and is reached only via the Vercel proxy, never directly by the browser.

## Rate Limiter — Implementation Explained
 
The rate limiter lives in `backend/app/middleware/rate_limiter.py` and is applied as a Python decorator on `POST /api/shorten`.
 
### Algorithm: Sliding Window Log
 
A **Sliding Window Log** was chosen over the simpler Fixed Window counter because it prevents burst exploitation at window boundaries.
 
**How Fixed Window fails:**
A Fixed Window resets its counter at a hard clock boundary (e.g. every `:00` second). An attacker can send 5 requests at `:59` and 5 more at `:01` — 10 requests in 2 seconds — without ever triggering a rejection.
 
**How Sliding Window Log works:**
 
```
On every incoming request from IP address X:
 
  1. Record current time as `now`.
  2. Define window_start = now − WINDOW_SECONDS (default: 60 s).
  3. Evict all timestamps in X's log that are ≤ window_start
     — they are expired and no longer count toward the limit.
  4. Count remaining timestamps in the log (active requests in window).
  5a. If count ≥ LIMIT (default: 5):
        → Reject with HTTP 429.
        → retry_after = ceil(oldest_timestamp + WINDOW_SECONDS − now)
          i.e. "seconds until the oldest entry falls out of the window"
        → Return header: Retry-After: <retry_after>
  5b. If count < LIMIT:
        → Append `now` to the log.
        → Allow the request.
```
 
<!-- **Data structure:** Each IP maps to a `collections.deque` of UTC timestamps (floats). `deque` gives O(1) `append` and O(1) `popleft` — eviction of expired entries is as cheap as possible.
 
**Thread safety:** A single `threading.Lock` guards the shared in-memory dict, making it safe under gunicorn's threaded workers.
 
**Trade-offs acknowledged:**
- State is in-process memory — a restart clears all counters. Production would use Redis sorted sets for persistence and cross-worker sharing.
- With multiple gunicorn *workers* (processes), each worker maintains its own dict. The compose config uses `--workers 2`; for true multi-worker rate limiting, replace the dict with a Redis backend. -->

## API Endpoints

Interactive, always-current docs: **Swagger UI at `/api/docs`** and raw spec at `/api/docs/openapi.json`. The table below is a quick reference.

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/shorten` | Shorten a URL — random or custom alias, optional expiry. Rate limited. |
| `GET` | `/go/<alias>` | Redirect to the original URL + record a click (referrer, UA, geo) |
| `GET` | `/<alias>` | Render an HTML preview page for the destination — no redirect, no click recorded |
| `GET` | `/api/urls/<alias>/qr` | Get a QR code for a short link — JSON (base64) or raw PNG |
| `GET` | `/api/urls` | List all shortened URLs |
| `GET` | `/api/analytics/<alias>` | 7-day click time-series + device/browser/OS/country/referrer breakdowns |
| `GET` | `/api/health` | Liveness probe that pings the DB |
| `GET` | `/api/docs` | Swagger UI |

## API Documentation

All request and response bodies are JSON except where noted. Error responses always include an `"error"` key.
 
---
 
### `POST /api/shorten`
 
Shorten a long URL. Validates the URL, rejects SSRF-risky targets (localhost, private/link-local ranges, cloud metadata endpoints), checks it against Google Safe Browsing (fails open if `SAFE_BROWSING_API_KEY` isn't set — the URL is still shortened), then stores it under a random or custom alias. Rate limited to 5 requests per 60 seconds per IP.
 
**Request**
 
```http
POST /api/shorten
Content-Type: application/json
```
 
```json
{
  "url": "https://www.example.com/some/very/long/path?with=query&params=true",
  "custom_alias": "123456",
  "expires_at": "2026-12-31T00:00:00Z"
}
```

`custom_alias` and `expires_at` are both optional.
- `custom_alias`: exactly 6 characters, letters/digits/hyphens/underscores only, and can't collide with an existing alias or a reserved word (`api`, `health`, `shorten`, `urls`, `analytics`, `static`, `favicon.ico`, `robots.txt`).
- `expires_at`: ISO-8601 timestamp. After this time, `/go/<alias>` and `/<alias>` redirect to the frontend's expired-link page instead of the destination.
 
**Response `201 Created`**
 
```json
{
  "alias": "aB3xYz",
  "short_url": "https://snip.shirishmaharjan8.com.np/aB3xYz",
  "original_url": "https://www.example.com/some/very/long/path?with=query&params=true",
  "expires_at": null,
  "qr_code_url": "https://snip.shirishmaharjan8.com.np/api/urls/aB3xYz/qr?format=png"
}
```
 
**Response `400 Bad Request`** — missing/invalid URL, SSRF-risky or Safe-Browsing-flagged destination, invalid custom alias, or invalid `expires_at`
 
```json
{
  "error": "Invalid URL. Please provide a valid HTTP or HTTPS URL (e.g. https://example.com)."
}
```

**Response `409 Conflict`** — custom alias already taken, or a random-alias collision (ask the client to retry)

```json
{
  "error": "Alias 'my-link' is already taken. Please choose another."
}
```
 
**Response `429 Too Many Requests`** — rate limit exceeded
 
```json
{
  "error": "Rate limit exceeded.",
  "retry_after_seconds": 47,
  "message": "You have reached the limit of 5 URL shortenings per 60 seconds. Please try again in 47 seconds."
}
```
 
Headers:
```
Retry-After: 47
```
 
---

### `GET /go/{alias}`

Redirect to the original URL and record a click — referrer domain, browser/OS/device (parsed from `User-Agent`), and country/city (resolved via ip-api.com, Redis-cached). The raw client IP is only used transiently for the geo lookup; it's never stored, only a one-way hash plus the resolved country/city persist.

**Request**

```http
GET /go/aB3xYz
```

**Response `302 Found`**

```
Location: https://www.example.com/some/very/long/path?with=query&params=true
```

If the link has expired: `302` to the frontend's expired-link page (`{FRONTEND_ORIGIN}/?expired=1&alias=aB3xYz`) instead.

**Response `404 Not Found`**

```json
{ "error": "Alias 'aB3xYz' not found." }
```

---

### `GET /{alias}`

Renders an HTML preview page ("You're about to visit — continue?") for the destination. Does **not** redirect and does **not** record a click — that only happens on `/go/<alias>`, which the preview page links to.

**Request**

```http
GET /aB3xYz
```

**Response `200 OK`** — `text/html`, renders `preview.html` with the alias, destination, and expiry.

**Response `302 Found`** — if expired, redirects to the frontend's expired-link page (same as `/go/<alias>`).

**Response `404 Not Found`**

```json
{ "error": "Alias 'aB3xYz' not found." }
```

---

### `GET /api/urls/{alias}/qr`

Generate a QR code that encodes the alias's short URL — scanning it goes straight to the same place the short link does.

**Query params**

| Param | Default | Description |
|---|---|---|
| `size` | `10` | Pixels per QR "module" (clamped to a sane range) — controls image resolution, not information density. |
| `format` | `json` | `json` returns `{ "qr_code": "data:image/png;base64,..." }`; `png` streams raw image bytes — this is what `qr_code_url` in other responses points at, so it works directly as `<img src="...">`. |
| `download` | `false` | Only applies to `format=png`. If truthy, sets `Content-Disposition: attachment` so a plain download link forces save-as. |

**Request**

```http
GET /api/urls/aB3xYz/qr?format=json
```

**Response `200 OK`** (`format=json`)

```json
{
  "alias": "aB3xYz",
  "short_url": "https://snip.shirishmaharjan8.com.np/aB3xYz",
  "qr_code": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAA...",
  "is_expired": false
}
```

**Response `200 OK`** (`format=png`) — raw `image/png` bytes, cached aggressively (`Cache-Control: public, max-age=86400, immutable`) since a QR code never changes after the link is created.

**Response `400 Bad Request`** — `size` isn't a valid integer

**Response `404 Not Found`**

```json
{ "error": "Alias 'aB3xYz' not found." }
```
 
---
 
### `GET /api/urls`
 
List all shortened URLs, ordered newest-first.
 
**Request**
 
```http
GET /api/urls
```
 
**Response `200 OK`**
 
```json
{
  "urls": [
    {
      "id": 3,
      "alias": "aB3xYz",
      "original_url": "https://www.example.com/some/very/long/path",
      "short_url": "https://snip.shirishmaharjan8.com.np/aB3xYz",
      "created_at": "2026-06-14T10:00:00+00:00",
      "total_clicks": 42,
      "qr_code_url": "https://snip.shirishmaharjan8.com.np/api/urls/aB3xYz/qr?format=png"
    },
    {
      "id": 2,
      "alias": "kP9mNq",
      "original_url": "https://docs.python.org/3/library/collections.html",
      "short_url": "https://snip.shirishmaharjan8.com.np/kP9mNq",
      "created_at": "2026-06-13T08:30:00+00:00",
      "total_clicks": 7,
      "qr_code_url": "https://snip.shirishmaharjan8.com.np/api/urls/kP9mNq/qr?format=png"
    }
  ]
}
```
 
---
 
### `GET /api/analytics/{alias}`
 
Return aggregated daily click counts for one alias over the last 7 days, plus all-time breakdowns by device, browser, OS, country, and referrer. Always returns exactly 7 data points in `analytics` — days with no clicks are included with `"clicks": 0` so the frontend chart always has a continuous x-axis.
 
**Request**
 
```http
GET /api/analytics/aB3xYz
```
 
**Response `200 OK`**
 
```json
{
  "alias": "aB3xYz",
  "original_url": "https://www.example.com/some/very/long/path",
  "short_url": "https://snip.shirishmaharjan8.com.np/aB3xYz",
  "total_clicks": 42,
  "analytics": [
    { "date": "2026-06-08", "clicks": 0 },
    { "date": "2026-06-09", "clicks": 3 },
    { "date": "2026-06-10", "clicks": 8 },
    { "date": "2026-06-11", "clicks": 1 },
    { "date": "2026-06-12", "clicks": 0 },
    { "date": "2026-06-13", "clicks": 12 },
    { "date": "2026-06-14", "clicks": 18 }
  ],
  "devices": [
    { "device_type": "desktop", "clicks": 25 },
    { "device_type": "mobile", "clicks": 15 },
    { "device_type": "tablet", "clicks": 2 }
  ],
  "browsers": [
    { "browser": "Chrome", "clicks": 20 },
    { "browser": "Safari", "clicks": 12 }
  ],
  "operating_systems": [
    { "os": "Windows", "clicks": 18 },
    { "os": "iOS", "clicks": 10 }
  ],
  "countries": [
    { "country": "United States", "country_code": "US", "clicks": 30 },
    { "country": "United Kingdom", "country_code": "GB", "clicks": 8 }
  ],
  "top_referrers": [
    { "referrer": "twitter.com", "clicks": 14 },
    { "referrer": "Direct / None", "clicks": 10 }
  ]
}
```

`devices` / `browsers` / `operating_systems` are parsed from the `User-Agent` header at click time (see `backend/app/utils/user_agent.py`), using the [`user-agents`](https://pypi.org/project/user-agents/) library. `countries` are resolved via [ip-api.com](https://ip-api.com) (free, keyless, cached in Redis for 24h) — the raw client IP is only used transiently for that lookup and is never stored; only the resolved country/city persist. `top_referrers` groups by domain (e.g. all `twitter.com/...` links count together) rather than the full referrer URL. Device/browser/OS/country breakdowns are all-time totals (not scoped to the 7-day window), since they're about *who* is clicking rather than *when*.
 
**Response `404 Not Found`**
 
```json
{
  "error": "Alias 'aB3xYz' not found."
}
```
 
---
 
### `GET /api/health`
 
Liveness probe for Docker health checks and uptime monitors (also used as Railway's health check — see Deployment).
 
**Response `200 OK`**
 
```json
{ "status": "ok", "db": "ok" }
```
 
**Response `503 Service Unavailable`** — database unreachable
 
```json
{ "status": "degraded", "db": "unreachable" }
```