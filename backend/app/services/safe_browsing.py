"""
Google Safe Browsing integration
---------------------------------
Checks submitted URLs against Google's Safe Browsing Lookup API (v4) before we hand out a short link for them, so `snip.io/aB3xYz` can't become an easy way to disguise a phishing or malware link.

How the check works:
  We POST the candidate URL to Safe Browsing's `threatMatches:find` endpoint, listing which threat categories we care about (malware, phishing/"social engineering", unwanted software, etc). Google maintains huge, constantly-updated lists of known-bad URLs; this endpoint just asks "does this URL appear on any of those lists?" and returns any matches.

  This is the "Lookup API" variant (one URL per request, ask Google's servers directly) rather than the "Update API" variant (download the hash lists yourself and check locally). Lookup is far simpler to
  integrate — the trade-off is that Google's servers see every URL you check, and each check is a network round-trip. For a URL shortener's request volume this trade-off is the right one; the Update API only
  really pays off at very high volume where the network round-trips themselves become the bottleneck.

Getting an API key (takes about 2 minutes, no cost):
  1. Go to https://console.cloud.google.com/ and create (or select) a project.
  2. Open "APIs & Services" -> "Library", search for "Safe Browsing API", and click Enable.
  3. Go to "APIs & Services" -> "Credentials" -> "Create Credentials" -> "API key".
  4. (Recommended) Click "Restrict key" and limit it to the Safe Browsing API only, so the key is useless if it ever leaks.
  5. Put the key in your .env as SAFE_BROWSING_API_KEY=...

  The API is free with a default per-project quota (Google's own pricing page: "All use of Safe Browsing APIs is free of charge"). Note Google's terms restrict this specific API to non-commercial use — fine for a portfolio project, but if this ever became a paid product you'd need their commercial equivalent, Web Risk API, instead.

Fails open:
  If SAFE_BROWSING_API_KEY isn't set, or the request to Google times out, errors, or hits a quota limit, we ALLOW the URL through rather than blocking every single shorten request on a third-party service being reachable. The same fail-open philosophy is used in the Redis rate limiter for the same reason: a degraded third-party dependency shouldn't take your whole app down. The trade-off is explicit — worth knowing this means a Safe Browsing outage silently disables the safety check rather than blocking shortenings.
"""

import logging
import os

import requests
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

SAFE_BROWSING_API_URL = "https://safebrowsing.googleapis.com/v4/threatMatches:find"
SAFE_BROWSING_TIMEOUT_SECONDS = 3

# Threat categories we ask Google to check for. See the full list at:
# https://developers.google.com/safe-browsing/v4/reference/rest/v4/ThreatType
_THREAT_TYPES = [
    "MALWARE",
    "SOCIAL_ENGINEERING",       # phishing
    "UNWANTED_SOFTWARE",
    "POTENTIALLY_HARMFUL_APPLICATION",
]

# Only log the "no API key configured" warning once per process, not on
# every single request — otherwise local dev without a key spams the logs.
_missing_key_warned = False

def _get_api_key() -> Optional[str]:
    return os.environ.get("SAFE_BROWSING_API_KEY", "").strip() or None

def check_url_safety(url: str) -> Tuple[bool, Optional[str]]:
    """
    Check *url* against Google Safe Browsing.

    Returns:
        (is_safe, threat_type)
        - (True, None)   -> no known threat found, OR the check was skipped
                             / failed and we're failing open (see module
                             docstring).
        - (False, "...") -> Google reports this URL as a known threat;
                             threat_type is one of the _THREAT_TYPES values
                             above (e.g. "SOCIAL_ENGINEERING").
    """
    global _missing_key_warned

    api_key = _get_api_key()
    if not api_key:
        if not _missing_key_warned:
            logger.warning(
                "SAFE_BROWSING_API_KEY is not set — URL safety checks are "
                "disabled. Every submitted URL will be shortened without a "
                "malware/phishing check until a key is configured."
            )
            _missing_key_warned = True
        return True, None

    payload = {
        "client": {
            "clientId": "snip-url-shortener",
            "clientVersion": "1.0",
        },
        "threatInfo": {
            "threatTypes": _THREAT_TYPES,
            "platformTypes": ["ANY_PLATFORM"],
            "threatEntryTypes": ["URL"],
            "threatEntries": [{"url": url}],
        },
    }

    try:
        response = requests.post(
            SAFE_BROWSING_API_URL,
            params={"key": api_key},
            json=payload,
            timeout=SAFE_BROWSING_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    except requests.exceptions.RequestException as exc:
        # Covers timeouts, connection errors, 4xx/5xx responses (e.g. quota
        # exceeded, bad key, Google having an outage). Fail open — see
        # module docstring for why.
        logger.error("Safe Browsing lookup failed for %s — failing open: %s", url, exc)
        return True, None

    try:
        matches = response.json().get("matches", [])
    except ValueError:
        logger.error("Safe Browsing returned a non-JSON response — failing open")
        return True, None

    if not matches:
        return True, None

    threat_type = matches[0].get("threatType", "UNKNOWN")
    logger.warning("Safe Browsing flagged URL as %s: %s", threat_type, url)
    return False, threat_type