import hashlib
import logging
from datetime import datetime, timezone

from flask import Blueprint, jsonify, redirect, request
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.extensions import db
from app.middleware.rate_limiter import rate_limit
from app.models.url import Click, ShortenedUrl
from app.utils.helpers import generate_alias, generate_alias_from_url, is_valid_url, normalise_url

logger = logging.getLogger(__name__)

urls_bp = Blueprint("urls", __name__)

# Helpers
MAX_ALIAS_RETRIES = 5  # how many random attempts before falling back to hash

def _make_unique_alias(original_url: str) -> str:
    """
    Try up to MAX_ALIAS_RETRIES random aliases.
    Fall back to a hash-derived alias if all collide (astronomically unlikely).
    Raises RuntimeError if even the hash alias is taken.
    """
    for _ in range(MAX_ALIAS_RETRIES):
        alias = generate_alias()
        if not ShortenedUrl.query.filter_by(alias=alias).first():
            return alias

    alias = generate_alias_from_url(original_url)
    if ShortenedUrl.query.filter_by(alias=alias).first():
        raise RuntimeError("Could not generate a unique alias — please retry.")
    return alias

def _hash_ip(ip: str) -> str:
    """One-way hash of the client IP for privacy-safe storage."""
    return hashlib.sha256(ip.encode()).hexdigest()

# POST /api/shorten
@urls_bp.route("/api/shorten", methods=["POST"])
@rate_limit  
def shorten_url():
    """
    Accept a long URL and return a shortened alias.

    Request body (JSON):
        { "url": "https://example.com/very/long/path" }

    Responses:
        201  { "alias": "aB3xYz", "short_url": "http://localhost:5000/aB3xYz",
               "original_url": "https://example.com/very/long/path" }
        400  { "error": "..." }          — missing / invalid input
        500  { "error": "..." }          — unexpected server error
    """
    data = request.get_json(silent=True)

    # Input validation 
    if not data:
        return jsonify({"error": "Request body must be JSON."}), 400

    raw_url = data.get("url", "").strip()

    if not raw_url:
        return jsonify({"error": "The 'url' field is required and cannot be empty."}), 400

    print("RAW URL:", raw_url)

    if not is_valid_url(raw_url):
        return jsonify({
            "error": "Invalid URL. Please provide a valid HTTP or HTTPS URL "
                     "(e.g. https://example.com)."
        }), 400

    original_url = normalise_url(raw_url)

    # Alias generation + DB write 
    try:
        alias = _make_unique_alias(original_url)
        entry = ShortenedUrl(original_url=original_url, alias=alias)
        db.session.add(entry)
        db.session.commit()
    except RuntimeError as exc:
        logger.error("Alias generation failed: %s", exc)
        return jsonify({"error": str(exc)}), 500
    except IntegrityError:
        db.session.rollback()
        logger.warning("IntegrityError on alias '%s' — race condition, ask client to retry.", alias)
        return jsonify({"error": "Alias collision — please retry."}), 409
    except SQLAlchemyError as exc:
        db.session.rollback()
        logger.exception("Database error while shortening URL: %s", exc)
        return jsonify({"error": "A database error occurred. Please try again."}), 500

    base_url = request.host_url.rstrip("/")
    return jsonify({
        "alias": alias,
        "short_url": f"{base_url}/{alias}",
        "original_url": original_url,
    }), 201

# GET /<alias>  — redirect + click tracking
@urls_bp.route("/<string:alias>", methods=["GET"])
def redirect_alias(alias: str):
    """
    Look up *alias*, record a click, and redirect to the original URL.

    Responses:
        302  Redirect to original URL.
        404  { "error": "Alias not found." }
        500  { "error": "..." }
    """
    entry = ShortenedUrl.query.filter_by(alias=alias).first()
    if entry is None:
        return jsonify({"error": f"Alias '{alias}' not found."}), 404

    try:
        ip = request.headers.get("X-Forwarded-For", request.remote_addr or "")
        client_ip = ip.split(",")[0].strip()

        click = Click(
            shortened_url_id=entry.id,
            clicked_at=datetime.now(timezone.utc),
            ip_hash=_hash_ip(client_ip) if client_ip else None,
        )
        db.session.add(click)
        db.session.commit()
    except SQLAlchemyError as exc:
        db.session.rollback()
        logger.error("Failed to record click for alias '%s': %s", alias, exc)

    return redirect(entry.original_url, code=302)

# GET /api/health  — lightweight liveness probe
@urls_bp.route("/api/health", methods=["GET"])
def health_check():
    """Simple liveness endpoint for Docker health checks and uptime monitors."""
    try:
        db.session.execute(db.text("SELECT 1"))
        db_status = "ok"
    except SQLAlchemyError:
        db_status = "unreachable"

    status = "ok" if db_status == "ok" else "degraded"
    return jsonify({"status": status, "db": db_status}), 200 if status == "ok" else 503

# GET /api/urls  — list every shortened URL
@urls_bp.route("/api/urls", methods=["GET"])
def list_urls():
    """
    Return all shortened URLs ordered newest-first.
 
    Response 200:
        {
          "urls": [
            {
              "id": 1,
              "alias": "aB3xYz",
              "original_url": "https://example.com/...",
              "short_url": "http://localhost:5000/aB3xYz",
              "created_at": "2025-06-14T10:00:00+00:00",
              "total_clicks": 42
            },
            ...
          ]
        }
    """
    try:
        entries = (
            ShortenedUrl.query
            .order_by(ShortenedUrl.created_at.desc())
            .all()
        )
    except SQLAlchemyError as exc:
        logger.exception("Failed to list URLs: %s", exc)
        return jsonify({"error": "Database error. Please try again."}), 500
 
    base_url = request.host_url.rstrip("/")
 
    return jsonify({
        "urls": [
            {
                **entry.to_dict(),
                "short_url": f"{base_url}/{entry.alias}",
            }
            for entry in entries
        ]
    }), 200
 
 
# GET /api/analytics/<alias>  — 7-day daily click counts for one alias
@urls_bp.route("/api/analytics/<string:alias>", methods=["GET"])
def get_analytics(alias: str):
    """
    Return daily click counts for *alias* over the last 7 days.
 
    Uses the v_clicks_last_7_days VIEW defined in schema.sql so the heavy aggregation stays in Postgres and the Python layer only serialises rows. (Used Raw SQL for now because of migration issues with SQLAlchemy ORM and the view.)
 
    Dates with zero clicks are filled in by Python so Chart.js always receives exactly 7 data points — a continuous x-axis regardless of activity gaps.
 
    Response 200:
        {
          "alias": "aB3xYz",
          "original_url": "https://example.com/...",
          "total_clicks": 42,
          "analytics": [
            { "date": "2025-06-08", "clicks": 0 },
            { "date": "2025-06-09", "clicks": 3 },
            ...
            { "date": "2025-06-14", "clicks": 7 }   ← today
          ]
        }
 
    Response 404:
        { "error": "Alias 'xyz' not found." }
    """
    from datetime import date, timedelta, datetime
 
    entry = ShortenedUrl.query.filter_by(alias=alias).first()
    if entry is None:
        return jsonify({"error": f"Alias '{alias}' not found."}), 404

    try:
        rows = db.session.execute(
            db.text("""
                SELECT
                    DATE(c.clicked_at AT TIME ZONE 'UTC') AS click_date,
                    COUNT(*)                               AS click_count
                FROM clicks c
                JOIN shortened_urls su ON su.id = c.shortened_url_id
                WHERE su.alias = :alias
                  AND c.clicked_at >= NOW() - INTERVAL '7 days'
                GROUP BY click_date
                ORDER BY click_date ASC
            """),
            {"alias": alias},
        ).fetchall()
    except SQLAlchemyError as exc:
        logger.exception("Analytics query failed for alias '%s': %s", alias, exc)
        return jsonify({"error": "Database error. Please try again."}), 500
 
    def to_date(val):
        if isinstance(val, datetime):
            return val.date()
        if isinstance(val, date):
            return val
        # Fallback: string "YYYY-MM-DD"
        return date.fromisoformat(str(val)[:10])
    
    clicks_by_date = {to_date(row.click_date): row.click_count for row in rows}

    today = date.today()
    analytics = []
    for offset in range(6, -1, -1):          
        day = today - timedelta(days=offset)
        analytics.append({
            "date": day.isoformat(),          
            "clicks": clicks_by_date.get(day, 0),
        })
 
    return jsonify({
        "alias": alias,
        "original_url": entry.original_url,
        "short_url": f"{request.host_url.rstrip('/')}/{alias}",
        "total_clicks": entry.to_dict()["total_clicks"],
        "analytics": analytics,
    }), 200
 
@urls_bp.route("/api/debug/rate-limit", methods=["GET"])
def debug_rate_limit():
    """
    DEV ONLY — shows the current in-memory rate-limit store and the IP
    Flask sees for this request.  Remove before deploying to production.
    """
    from app.middleware.rate_limiter import get_store_snapshot
    forwarded_for = request.headers.get("X-Forwarded-For", "").strip()
    resolved_ip = forwarded_for.split(",")[0].strip() if forwarded_for else (request.remote_addr or "unknown")
    snapshot = get_store_snapshot()
    return jsonify({
        "resolved_ip": resolved_ip,
        "remote_addr": request.remote_addr,
        "x_forwarded_for": forwarded_for or None,
        "store": {ip: len(ts) for ip, ts in snapshot.items()},
        "store_detail": snapshot,
    }), 200
