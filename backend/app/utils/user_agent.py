"""
User-Agent Parsing
-------------------
Turns a raw User-Agent header string into the fields we actually want to aggregate on: browser family, OS family, and a coarse device-type bucket.

We parse and store these at click-time (rather than storing only the raw UA string and re-parsing it on every analytics request) so the "devices" / "browsers" breakdowns in the analytics endpoint can be a plain SQL GROUP BY instead of pulling every row into Python and re-parsing it each time the dashboard is opened.

Uses the `user-agents` package (pure-Python, wraps the same regex database — ua-parser's `uap-core` — that most UA parsers use). No network calls involved; this is a client-provided header, not looked up anywhere.
"""

import logging
from typing import Optional

from user_agents import parse as _parse_ua

logger = logging.getLogger(__name__)

# Device-type buckets we store. Kept small and closed-set on purpose so analytics GROUP BY queries produce a stable, predictable set of rows instead of hundreds of long-tail values.
DEVICE_MOBILE = "mobile"
DEVICE_TABLET = "tablet"
DEVICE_DESKTOP = "desktop"
DEVICE_BOT = "bot"
DEVICE_OTHER = "other"

MAX_FIELD_LENGTH = 50  # matches the DB column size for browser/os


def parse_user_agent(ua_string: Optional[str]) -> dict:
    """
    Parse *ua_string* into browser/os/device_type.

    Returns a dict with keys "browser", "os", "device_type" — all are None if ua_string is empty, or if parsing raises (a UA string is fully client-controlled input; a malformed one should never break the redirect).

    device_type is one of: "mobile", "tablet", "desktop", "bot", "other".
    """
    if not ua_string or not ua_string.strip():
        return {"browser": None, "os": None, "device_type": None}

    try:
        ua = _parse_ua(ua_string)
    except Exception:
        # Defensive: the parser is regex-based and generally very tolerant, but we never want a weird client header to 500 the redirect endpoint.
        logger.debug("Failed to parse User-Agent string — storing as unknown.")
        return {"browser": None, "os": None, "device_type": None}

    if ua.is_bot:
        device_type = DEVICE_BOT
    elif ua.is_mobile:
        device_type = DEVICE_MOBILE
    elif ua.is_tablet:
        device_type = DEVICE_TABLET
    elif ua.is_pc:
        device_type = DEVICE_DESKTOP
    else:
        device_type = DEVICE_OTHER

    browser = ua.browser.family or None
    os_family = ua.os.family or None

    return {
        "browser": browser[:MAX_FIELD_LENGTH] if browser else None,
        "os": os_family[:MAX_FIELD_LENGTH] if os_family else None,
        "device_type": device_type,
    }
