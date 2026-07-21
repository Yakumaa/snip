import hashlib
import ipaddress
import random
import re
import socket
import string
from urllib.parse import urlparse
from typing import Tuple, Optional
from datetime import datetime, timezone

# Alias generation
ALIAS_CHARS = string.ascii_letters + string.digits  # a-z A-Z 0-9
ALIAS_LENGTH = 6

def generate_alias() -> str:
    """Return a random 6-character alphanumeric alias."""
    return "".join(random.choices(ALIAS_CHARS, k=ALIAS_LENGTH))

def generate_alias_from_url(url: str) -> str:
    """
    Deterministic fallback: derive a 6-char alias from the URL's SHA-256 hash.  Used only when random generation keeps colliding (very rare).
    """
    digest = hashlib.sha256(url.encode()).hexdigest()
    return digest[:ALIAS_LENGTH]

# URL validation
# Minimum viable URL regex — requires a scheme and a hostname.
_URL_RE = re.compile(
    r"^(https?://)?"           # optional scheme
    r"([a-zA-Z0-9-]+\.)+"      # subdomain(s) or www
    r"[a-zA-Z]{2,}"            # TLD
    r"(:\d+)?"                 # optional port
    r"(/[^\s]*)?$",            # optional path
    re.IGNORECASE,
)

# Sane upper bound on submitted URL length — also guards against pathological inputs being thrown at the regex engine and stored in the DB unbounded.
MAX_URL_LENGTH = 2048

def is_valid_url(url: str) -> bool:
    """
    Return True if *url* looks like a valid HTTP/HTTPS URL.

    Checks:
      1. Non-empty string, within MAX_URL_LENGTH.
      2. Parseable by urllib with a recognised scheme.
      3. Has a non-empty network location (hostname).
      4. No embedded userinfo (e.g. "http://trusted.com@evil.com/") — a classic phishing trick where the hostname before the '@' is fake and the real destination is whatever follows it. No legitimate use case for a public short link.
      5. Matches the minimal URL regex above.

    Note: this function only checks *shape* — whether the string looks like a well-formed public URL. It does NOT check whether the destination is a private/internal address; that's handled separately by check_ssrf_safety(), because that check requires an actual DNS lookup and doing it here would conflate two different failure reasons the caller wants to report differently.
    """
    if not url or not isinstance(url, str):
        return False

    url = url.strip()

    if len(url) > MAX_URL_LENGTH:
        return False

    # Prepend scheme if missing so urlparse works correctly.
    parse_target = url if url.startswith(("http://", "https://")) else f"https://{url}"

    try:
        parsed = urlparse(parse_target)
    except ValueError:
        return False

    if parsed.scheme not in ("http", "https"):
        return False

    if not parsed.netloc:
        return False

    if parsed.username is not None or "@" in parsed.netloc:
        return False

    return bool(_URL_RE.match(url))

def normalise_url(url: str) -> str:
    """Ensure the URL has an explicit https:// scheme."""
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        return f"https://{url}"
    return url

# SSRF / private-network hardening
#
# Hostnames blocked by name outright, regardless of what they resolve to.
# ".local" is mDNS/Bonjour's reserved TLD for local-network-only names.
_BLOCKED_HOSTNAMES = {
    "localhost",
    "localhost.localdomain",
    "metadata.google.internal",   # GCP instance metadata service's well-known hostname
}

_DNS_TIMEOUT_SECONDS = 2

def _is_blocked_ip(ip: "ipaddress.IPv4Address | ipaddress.IPv6Address") -> bool:
    """
    True if *ip* is any flavor of non-public address: loopback (127.0.0.0/8, ::1), private (RFC 1918 / RFC 4193 ULA), link-local (169.254.0.0/16 — this is where AWS/GCP/Azure serve instance metadata and credentials from 169.254.169.254 — and fe80::/10), unspecified (0.0.0.0 / ::), multicast, or otherwise IANA-reserved.
    """
    return (
        ip.is_loopback
        or ip.is_private
        or ip.is_link_local
        or ip.is_unspecified
        or ip.is_multicast
        or ip.is_reserved
    )

def _resolve_hostname(hostname: str) -> list[str]:
    """
    Resolve *hostname* to every IPv4/IPv6 address it points to.

    Returns an empty list on any resolution failure (NXDOMAIN, timeout, etc.) — callers should treat "couldn't resolve" as "nothing to check," not as a security signal, since a non-resolving hostname isn't a real destination anyone can be routed to.
    """
    try:
        socket.setdefaulttimeout(_DNS_TIMEOUT_SECONDS)
        infos = socket.getaddrinfo(hostname, None)
    except (socket.gaierror, socket.timeout, UnicodeError, OSError):
        return []
    finally:
        socket.setdefaulttimeout(None)

    return list({info[4][0] for info in infos})  # dedupe

def check_ssrf_safety(url: str) -> Tuple[bool, Optional[str]]:
    """
    Check whether *url*'s destination is a private/internal network address that should never be handed out as a public short link.

    Returns:
        (is_safe, reason)
        - (True, None)   -> looks like a normal public address, or the
                             hostname didn't resolve at all (see note below).
        - (False, "...") -> resolves to a private, loopback, link-local, or
                             otherwise internal-only address.

    Why we resolve DNS instead of pattern-matching the hostname string:
      Wildcard-DNS services like nip.io / sslip.io / xip.io resolve an arbitrary-looking hostname straight to an IP of the caller's choosing — e.g. "127.0.0.1.nip.io" resolves to 127.0.0.1. A hostname-string check (even one that blocklists "localhost" and "127.0.0.1") sails right past that, because the *string* never contains anything suspicious — only the IP it resolves to does. So this function always resolves the hostname and inspects the real address(es), rather than trusting the hostname text.

    On DNS resolution failure:
      We fail OPEN (allow it through). A hostname that doesn't resolve at all isn't a security risk in itself — there's no real destination to reach, just a broken or not-yet-propagated link. This is different from *successfully* resolving to a private IP, which we always reject regardless of anything else.
    """
    try:
        hostname = urlparse(url).hostname
    except ValueError:
        return False, "URL could not be parsed."

    if not hostname:
        return False, "URL has no hostname."

    hostname_lower = hostname.lower()
    if hostname_lower in _BLOCKED_HOSTNAMES or hostname_lower.endswith(".local"):
        return False, "URL points to a reserved local/internal hostname."

    # Literal IP in the URL (e.g. http://169.254.169.254/) — no DNS needed.
    try:
        ip_obj = ipaddress.ip_address(hostname)
    except ValueError:
        ip_obj = None

    if ip_obj is not None:
        if _is_blocked_ip(ip_obj):
            return False, "URL points directly to a private or internal IP address."
        return True, None

    # Ordinary hostname — resolve it and check every address it points to.
    resolved_ips = _resolve_hostname(hostname)
    if not resolved_ips:
        return True, None  # couldn't resolve — see docstring

    for ip_str in resolved_ips:
        try:
            candidate = ipaddress.ip_address(ip_str)
        except ValueError:
            continue
        if _is_blocked_ip(candidate):
            return False, f"URL's hostname resolves to a private or internal address ({ip_str})."

    return True, None

ALIAS_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{6}$")

# Reserved so custom aliases can't collide with real routes
RESERVED_ALIASES = {
    "api", "health", "shorten", "urls", "analytics",
    "static", "favicon.ico", "robots.txt",
}

# TODO: alias works even when it is not 6 characters
def is_valid_custom_alias(alias: str) -> tuple[bool, str]:
    """
    Validate a user-supplied custom alias.
    Returns (is_valid, reason_if_invalid).
    """
    if not alias:
        return False, "Custom alias cannot be empty."
    if not ALIAS_PATTERN.match(alias):
        return False, (
            "Custom alias must be 6 characters and contain only "
            "letters, numbers, hyphens, and underscores."
        )
    if alias.lower() in RESERVED_ALIASES:
        return False, f"'{alias}' is a reserved word and cannot be used as an alias."
    return True, ""

def parse_expiry(raw_expiry: str) -> tuple[datetime | None, str]:
    """
    Parse an ISO 8601 expiry timestamp from the client.
    Returns (parsed_datetime_or_None, error_message).
    """
    if not raw_expiry:
        return None, ""

    try:
        # Accept "Z" suffix as well as explicit offsets
        dt = datetime.fromisoformat(raw_expiry.replace("Z", "+00:00"))
    except ValueError:
        return None, "Invalid expiry date format. Use ISO 8601 (e.g. 2026-08-01T00:00:00Z)."

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    if dt <= datetime.now(timezone.utc):
        return None, "Expiry date must be in the future."

    return dt, ""