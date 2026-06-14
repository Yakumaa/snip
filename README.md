# Rate-Limited URL Shortener with Analytics

A full-stack web application built as a technical assessment for Grepsr. Users can shorten long URLs, track click activity, and visualise 7-day analytics through a live Chart.js dashboard.

**Stack:** Python 3.12 / Flask · React 18 / Vite · PostgreSQL 16 · Docker

## Project Structure

```
fullstack-assessment/
├── backend/                  # Flask API
│   ├── app/
│   │   ├── middleware/
│   │   │   └── rate_limiter.py   # Custom sliding-window rate limiter
│   │   ├── models/
│   │   │   └── url.py            # ShortenedUrl + Click ORM models
│   │   ├── routes/
│   │   │   └── urls.py           # All API endpoints
│   │   ├── utils/helpers.py
│   │   ├── extensions.py
│   │   └── config.py
│   ├── migrations/               # Alembic migration history
│   ├── tests/                    # Tests for rate limiter
│   ├── Dockerfile
│   ├── entrypoint.sh             # Container startup: migrate → gunicorn
│   ├── requirements.txt
│   └── wsgi.py
├── frontend/                 # React + Vite
│   ├── src/
│   │   ├── components/
│   │   │   ├── UrlShortener.jsx          # URL input + 429 countdown
│   │   │   └── AnalyticsDashboard.jsx    # URL list + Chart.js line chart
│   │   ├── services/api.js               # Centralised fetch client
│   │   └── App.jsx
│   ├── Dockerfile
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
git clone https://github.com/Yakumaa/fullstack-assessment.git
cd fullstack-assessment
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

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/shorten` | Shorten a URL |
| `GET` | `/<alias>` | Redirect + record click |
| `GET` | `/api/urls` | List all shortened URLs |
| `GET` | `/api/urls/<alias>/analytics` | 7-day click time-series |
| `GET` | `/api/health` | Bonus liveness probe that pings the DB |

## API Documentation

All request and response bodies are JSON. Error responses always include an `"error"` key.
 
---
 
### `POST /api/shorten`
 
Shorten a long URL. Subject to rate limiting (5 requests per 60 seconds per IP).
 
**Request**
 
```http
POST /api/shorten
Content-Type: application/json
```
 
```json
{
  "url": "https://www.example.com/some/very/long/path?with=query&params=true"
}
```
 
**Response `201 Created`**
 
```json
{
  "alias": "aB3xYz",
  "short_url": "http://localhost:5000/aB3xYz",
  "original_url": "https://www.example.com/some/very/long/path?with=query&params=true"
}
```
 
**Response `400 Bad Request`** — missing or invalid URL
 
```json
{
  "error": "Invalid URL. Please provide a valid HTTP or HTTPS URL (e.g. https://example.com)."
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
 
### `GET /{alias}`
 
Redirect to the original URL. Records a click event with a UTC timestamp.
 
**Request**
 
```http
GET /aB3xYz
```
 
**Response `302 Found`**
 
```
Location: https://www.example.com/some/very/long/path?with=query&params=true
```
 
**Response `404 Not Found`**
 
```json
{
  "error": "Alias 'aB3xYz' not found."
}
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
      "short_url": "http://localhost:5000/aB3xYz",
      "created_at": "2025-06-14T10:00:00+00:00",
      "total_clicks": 42
    },
    {
      "id": 2,
      "alias": "kP9mNq",
      "original_url": "https://docs.python.org/3/library/collections.html",
      "short_url": "http://localhost:5000/kP9mNq",
      "created_at": "2025-06-13T08:30:00+00:00",
      "total_clicks": 7
    }
  ]
}
```
 
---
 
### `GET /api/analytics/{alias}`
 
Return aggregated daily click counts for one alias over the last 7 days. Always returns exactly 7 data points — days with no clicks are included with `"clicks": 0` so the frontend chart always has a continuous x-axis.
 
**Request**
 
```http
GET /api/analytics/aB3xYz
```
 
**Response `200 OK`**
 
```json
{
  "alias": "aB3xYz",
  "original_url": "https://www.example.com/some/very/long/path",
  "short_url": "http://localhost:5000/aB3xYz",
  "total_clicks": 42,
  "analytics": [
    { "date": "2025-06-08", "clicks": 0 },
    { "date": "2025-06-09", "clicks": 3 },
    { "date": "2025-06-10", "clicks": 8 },
    { "date": "2025-06-11", "clicks": 1 },
    { "date": "2025-06-12", "clicks": 0 },
    { "date": "2025-06-13", "clicks": 12 },
    { "date": "2025-06-14", "clicks": 18 }
  ]
}
```
 
**Response `404 Not Found`**
 
```json
{
  "error": "Alias 'aB3xYz' not found."
}
```
 
---
 
### `GET /api/health`
 
Liveness probe for Docker health checks and uptime monitors.
 
**Response `200 OK`**
 
```json
{ "status": "ok", "db": "ok" }
```
 
**Response `503 Service Unavailable`** — database unreachable
 
```json
{ "status": "degraded", "db": "unreachable" }
```
