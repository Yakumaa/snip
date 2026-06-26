import hashlib
import random
import re
import string
from urllib.parse import urlparse

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

def is_valid_url(url: str) -> bool:
    """
    Return True if *url* looks like a valid HTTP/HTTPS URL.

    Checks:
      1. Non-empty string.
      2. Parseable by urllib with a recognised scheme.
      3. Has a non-empty network location (hostname).
      4. Matches the minimal URL regex above.
    """
    if not url or not isinstance(url, str):
        return False

    url = url.strip()

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

    return bool(_URL_RE.match(url))

def normalise_url(url: str) -> str:
    """Ensure the URL has an explicit https:// scheme."""
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        return f"https://{url}"
    return url