"""
Sliding Window Log Rate Limiter
--------------------------------
Tracks each request timestamp per IP in an in-memory log.

Algorithm:
  On every request from IP X:
    1. Get the current time (now).
    2. Define the window start as (now - WINDOW_SECONDS).
    3. Evict all timestamps in X's log that are older than the window start
       — they are expired and no longer count.
    4. Count how many timestamps remain (active requests in the window).
    5. If count >= LIMIT → reject with 429.
       - retry_after = ceil(oldest_timestamp + WINDOW_SECONDS - now)
         i.e. "how many seconds until the oldest entry falls out of the window"
    6. Otherwise → append now to the log and allow the request.

Why Sliding Window Log over Fixed Window?
  Fixed Window resets the counter at a hard boundary (e.g. every :00 second).
  A client can fire 5 requests at :59 and 5 more at :01 — 10 in 2 seconds.
  Sliding Window Log measures a true rolling 60-second period, so the burst gap exploit is impossible.

"""

import logging
import math
import threading
from collections import deque
from datetime import datetime, timezone
from functools import wraps
from typing import Deque, Dict

from flask import current_app, jsonify, request

logger = logging.getLogger(__name__)

_store: Dict[str, Deque[float]] = {}
_lock = threading.Lock()

def _check_rate_limit(
    ip: str,
    now: float,
    limit: int,
    window_seconds: int,
) -> tuple[bool, int]:
    """
    Evaluate and update the sliding window log for *ip*.

    Returns:
        (allowed: bool, retry_after: int)
        - allowed=True  → request is within quota; timestamp appended to log.
        - allowed=False → limit exceeded; retry_after is seconds to wait.
    """
    window_start = now - window_seconds

    with _lock:
        if ip not in _store:
            _store[ip] = deque()

        log: Deque[float] = _store[ip]

        # popleft is O(1); the log is always sorted oldest-first.
        while log and log[0] <= window_start:
            log.popleft()

        if len(log) >= limit:
            retry_after = math.ceil(log[0] + window_seconds - now)
            retry_after = max(retry_after, 1)
            return False, retry_after

        log.append(now)
        return True, 0

# Decorator
def rate_limit(f):
    """
    Decorator that applies the sliding window rate limit to a route.

    Reads RATE_LIMIT_MAX_REQUESTS and RATE_LIMIT_WINDOW_SECONDS from the Flask app config so limits can be changed via environment variables without touching code.

    Usage:
        @urls_bp.route("/api/shorten", methods=["POST"])
        @rate_limit
        def shorten_url():
            ...
    """
    @wraps(f)
    def wrapper(*args, **kwargs):
        limit: int = current_app.config["RATE_LIMIT_MAX_REQUESTS"]
        window: int = current_app.config["RATE_LIMIT_WINDOW_SECONDS"]

        # Resolve client IP — respect X-Forwarded-For for Docker / proxies.
        forwarded_for = request.headers.get("X-Forwarded-For", "")
        ip = forwarded_for.split(",")[0].strip() if forwarded_for else (request.remote_addr or "unknown")

        now = datetime.now(timezone.utc).timestamp()
        allowed, retry_after = _check_rate_limit(ip, now, limit, window)

        if not allowed:
            logger.warning(
                "Rate limit exceeded for IP %s — retry in %ds", ip, retry_after
            )
            response = jsonify({
                "error": "Rate limit exceeded.",
                "retry_after_seconds": retry_after,
                "message": (
                    f"You have reached the limit of {limit} URL shortenings "
                    f"per {window} seconds. "
                    f"Please try again in {retry_after} second{'s' if retry_after != 1 else ''}."
                ),
            })
            response.status_code = 429
            # RFC 6585 — tell HTTP clients and intermediaries how long to wait.
            response.headers["Retry-After"] = str(retry_after)
            return response

        return f(*args, **kwargs)

    return wrapper

# Optional: expose current store snapshot (useful for debugging / tests)
def get_store_snapshot() -> dict:
    """Return a copy of the in-memory store for inspection. Not for production use."""
    with _lock:
        return {ip: list(timestamps) for ip, timestamps in _store.items()}
