"""
IP Geolocation
--------------
Resolves a click's IP address to a coarse location (country, country code, city) so analytics can show a "where are my clicks coming from" breakdown.

Provider: ip-api.com
  Free, keyless, no signup required — 45 requests/minute per source IP on the free tier. Chosen over MaxMind GeoLite2 because MaxMind requires a (free but gated) account signup and a periodically-refreshed local .mmdb database file — real ongoing ops work for a portfolio project. ip-api.com's trade-off: free tier is HTTP only (not HTTPS) and rate limited, which is exactly why we cache aggressively below.

Privacy note — why we don't store the raw IP:
  This app already only stores a one-way hash of the client IP (`ip_hash`), never the IP itself, so it can never be reversed back to a person later. Geolocation needs the *real* IP to look up — so we resolve it here, at click time, using the raw IP just long enough to make the request, and only ever persist the resolved country / country_code / city. The raw IP itself is never written to the database or logs.

Caching:
  Looking up the same visitor's IP on every click would burn through the free-tier rate limit fast and add latency to every redirect. We cache resolved locations in Redis for CACHE_TTL_SECONDS, keyed by the same SHA-256 IP hash the app already computes elsewhere — so even the cache key never holds a raw IP.

Fails open:
  Same philosophy as Safe Browsing and the Redis rate limiter: if the API is unreachable, times out, or the IP can't be geolocated (private ranges, localhost, lookup errors), we return all-None fields rather than blocking or slowing the redirect. A missing "country" in analytics is a cosmetic gap; a slow or broken redirect is a real bug.
"""

import ipaddress
import json
import logging
from typing import Optional

import requests

logger = logging.getLogger(__name__)

GEO_API_URL = "http://ip-api.com/json/{ip}"
GEO_TIMEOUT_SECONDS = 1.5
CACHE_TTL_SECONDS = 24 * 60 * 60  # 24h — plenty stable for IP-to-country data
FAILURE_CACHE_TTL_SECONDS = 5 * 60  # short TTL for failed lookups — see note below
CACHE_KEY_PREFIX = "geo:"

_EMPTY_RESULT = {"country": None, "country_code": None, "city": None}

def _is_public_ip(ip_str: str) -> bool:
    """Only bother calling the API for addresses it could plausibly geolocate."""
    try:
        ip_obj = ipaddress.ip_address(ip_str)
    except ValueError:
        return False
    return not (
        ip_obj.is_private
        or ip_obj.is_loopback
        or ip_obj.is_link_local
        or ip_obj.is_reserved
        or ip_obj.is_multicast
        or ip_obj.is_unspecified
    )

def get_geolocation(ip: str, ip_hash: str, redis_client=None) -> dict:
    """
    Resolve *ip* to {"country", "country_code", "city"}.

    Args:
        ip: the raw client IP (used only for the outbound lookup itself, never persisted).
        ip_hash: the SHA-256 hash of *ip* the caller already computed — reused here as the Redis cache key so the cache never has to hold a raw IP either.
        redis_client: an existing redis.Redis connection. If None (e.g. Redis is unreachable), caching is skipped and every call hits the API directly — geolocation still works, just without the rate-limit protection caching gives it.

    Returns dict with "country", "country_code", "city" — all None if the address is non-public (private/loopback/etc), the API is unreachable, times out, or the response can't be parsed.
    """
    if not ip or not _is_public_ip(ip):
        return dict(_EMPTY_RESULT)

    cache_key = f"{CACHE_KEY_PREFIX}{ip_hash}"

    if redis_client is not None:
        try:
            cached = redis_client.get(cache_key)
            if cached is not None:
                return json.loads(cached)
        except Exception as exc:
            # A broken cache should never block a lookup — just skip caching.
            logger.debug("Geo cache read failed — proceeding without cache: %s", exc)

    try:
        response = requests.get(
            GEO_API_URL.format(ip=ip),
            params={"fields": "status,country,countryCode,city"},
            timeout=GEO_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.RequestException as exc:
        logger.warning("Geolocation lookup failed — failing open: %s", exc)
        # Cache the failure too, but only briefly. Without this, an extended API outage would re-attempt (and time out) the lookup on every single click — adding EO_TIMEOUT_SECONDS of latency to every redirect for as long as the outage lasts. A short TTL here means we retry periodically (in case the outage clears)# without paying that cost on every request in the meantime.
        if redis_client is not None:
            try:
                redis_client.set(cache_key, json.dumps(_EMPTY_RESULT), ex=FAILURE_CACHE_TTL_SECONDS)
            except Exception:
                pass
        return dict(_EMPTY_RESULT)
    except ValueError:
        logger.warning("Geolocation API returned a non-JSON response — failing open")
        return dict(_EMPTY_RESULT)

    if data.get("status") != "success":
        # e.g. private range ip-api itself refuses, or malformed IP
        result = dict(_EMPTY_RESULT)
    else:
        result = {
            "country": data.get("country"),
            "country_code": data.get("countryCode"),
            "city": data.get("city"),
        }

    if redis_client is not None:
        try:
            redis_client.set(cache_key, json.dumps(result), ex=CACHE_TTL_SECONDS)
        except Exception as exc:
            logger.debug("Geo cache write failed — continuing without cache: %s", exc)

    return result
