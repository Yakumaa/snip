"""
Sliding Window Log Rate Limiter — Redis-backed
------------------------------------------------
Tracks each request timestamp per IP in a Redis Sorted Set (ZSET), so the limit is enforced correctly across process restarts and across multiple gunicorn workers/machines — unlike a plain in-memory dict, which is private
to a single process and vanishes on restart.

Data structure:
  Key:    "rate_limit:<ip>"
  Member: a unique string per request (e.g. "1728999999.123:ab12cd34")
  Score:  the request's UTC unix timestamp (float)

  Using the timestamp as the score lets Redis do the heavy lifting natively:
    ZADD              -> record a new request
    ZREMRANGEBYSCORE  -> evict everything older than (now - window) in O(log N + M)
    ZCARD             -> count requests currently in the window
    ZRANGE ... WITHSCORES -> peek at the oldest entry, to compute retry_after

  The member must be unique even when two requests land in the same millisecond (Redis ZSET members are deduplicated by member value, not by score) — so we append a short random suffix rather than using the raw
  timestamp alone.

Algorithm (identical logic to the original in-memory version):
  On every request from IP X:
    1. Get the current time (now).
    2. Define the window start as (now - WINDOW_SECONDS).
    3. Evict all timestamps in X's ZSET older than the window start.
    4. Count how many timestamps remain (active requests in the window).
    5. If count >= LIMIT -> reject with 429.
       - retry_after = ceil(oldest_timestamp + WINDOW_SECONDS - now)
    6. Otherwise -> add `now` to the ZSET and allow the request.

Why a Lua script instead of separate Python calls?
  Steps 3-6 must happen as one atomic unit. If we issued ZREMRANGEBYSCORE,ZCARD, and ZADD as three separate round-trips, two concurrent requests from the same IP could both read "count = 4" before either writes, and both get allowed — letting 6 requests through a limit of 5 (a classic check-then-act race condition).

  Redis guarantees that an entire Lua script runs as a single, uninterrupted operation — no other client's command can be interleaved partway through. So we push the whole "evict, count, decide, maybe-add" sequence into one script and send it in a single round-trip. This is the standard pattern for building correct rate limiters on Redis.

Failure mode:
  If Redis itself is unreachable, we log the error and FAIL OPEN (allow the request) rather than taking the whole app down. For a URL shortener, a temporarily-disabled rate limit is a much better outcome than a 500 on every request. Fail-closed (reject everything) is the right call for something like a payments API — worth knowing this is a deliberate trade-off, not an oversight.
"""

import logging
import math
from datetime import datetime, timezone
from functools import wraps
from uuid import uuid4

import redis
from flask import current_app, jsonify, request

from app.extensions import redis_client

logger = logging.getLogger(__name__)

# Lua script, executed atomically inside Redis on every request.
#
# KEYS[1] = the ZSET key for this IP, e.g. "rate_limit:203.0.113.7"
# ARGV[1] = now (float, unix timestamp)
# ARGV[2] = window_seconds (int)
# ARGV[3] = limit (int)
# ARGV[4] = member (unique string identifying this request)
#
# Returns a 2-element array: {allowed (0/1), retry_after (int seconds)}
_SLIDING_WINDOW_LUA = """
local key          = KEYS[1]
local now           = tonumber(ARGV[1])
local window        = tonumber(ARGV[2])
local limit         = tonumber(ARGV[3])
local member         = ARGV[4]

-- Evict every entry that fell out of the window.
redis.call('ZREMRANGEBYSCORE', key, '-inf', now - window)

local count = redis.call('ZCARD', key)

if count >= limit then
    -- Look at the single oldest surviving entry to compute retry_after:
    -- "how many seconds until that entry falls out of the window".
    local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
    local oldest_score = tonumber(oldest[2])
    local retry_after = math.ceil(oldest_score + window - now)
    if retry_after < 1 then
        retry_after = 1
    end
    return {0, retry_after}
end

-- Under the limit: record this request and allow it.
redis.call('ZADD', key, now, member)
-- Let Redis auto-expire the whole key once the window has fully elapsed,
-- so IPs that stop making requests don't leave garbage behind forever.
redis.call('EXPIRE', key, window)

return {1, 0}
"""

# register_script() does NOT execute anything yet — it just wraps the Lua
# source in a callable Script object. The first time it's actually called,
# redis-py sends it to Redis (EVALSHA/EVAL) and caches the script's SHA for
# fast reuse on every call after that. Safe to create at import time.
_script = redis_client.register_script(_SLIDING_WINDOW_LUA)

def _check_rate_limit(
    ip: str,
    now: float,
    limit: int,
    window_seconds: int,
) -> tuple[bool, int]:
    """
    Evaluate and update the sliding window log for *ip* via the Lua script.

    Returns:
        (allowed: bool, retry_after: int)
        - allowed=True  -> request is within quota; timestamp recorded.
        - allowed=False -> limit exceeded; retry_after is seconds to wait.
    """
    key = f"rate_limit:{ip}"
    # Unique per-request member so simultaneous requests in the same
    # millisecond don't collide/overwrite each other in the ZSET.
    member = f"{now}:{uuid4().hex[:8]}"

    try:
        allowed, retry_after = _script(
            keys=[key],
            args=[now, window_seconds, limit, member],
        )
    except redis.exceptions.RedisError:
        logger.error("Redis unavailable — failing open (allowing request) for IP %s", ip)
        return True, 0

    return bool(allowed), int(retry_after)

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
    """
    Return a snapshot of current rate-limit ZSETs for inspection. Not for production use — SCAN + per-key ZRANGE is fine for a debug endpoint but shouldn't be called on a hot path.
    """
    snapshot = {}
    try:
        for key in redis_client.scan_iter(match="rate_limit:*"):
            ip = key.split(":", 1)[1]
            members_with_scores = redis_client.zrange(key, 0, -1, withscores=True)
            snapshot[ip] = [score for _member, score in members_with_scores]
    except redis.exceptions.RedisError:
        logger.error("Could not fetch rate limit snapshot — Redis unavailable")
    return snapshot