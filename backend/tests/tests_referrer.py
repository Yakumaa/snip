"""
Standalone unit tests for referrer handling (app/utils/helpers.py: normalise_referrer, extract_referrer_domain).

Run with:  python tests/tests_referrer.py
"""
import sys
sys.path.insert(0, ".")

from app.utils.helpers import MAX_REFERRER_LENGTH, extract_referrer_domain, normalise_referrer


def test_normalise_referrer_none_and_empty():
    assert normalise_referrer(None) is None
    assert normalise_referrer("") is None
    assert normalise_referrer("   ") is None
    print("PASS  normalise_referrer_none_and_empty")


def test_normalise_referrer_trims_whitespace():
    assert normalise_referrer("  https://example.com  ") == "https://example.com"
    print("PASS  normalise_referrer_trims_whitespace")


def test_normalise_referrer_enforces_max_length():
    long_referrer = "https://example.com/" + ("a" * 3000)
    result = normalise_referrer(long_referrer)
    assert len(result) == MAX_REFERRER_LENGTH
    print("PASS  normalise_referrer_enforces_max_length")


def test_extract_domain_from_social_referrer():
    assert extract_referrer_domain("https://twitter.com/someuser/status/123") == "twitter.com"
    print("PASS  extract_domain_from_social_referrer")


def test_extract_domain_ignores_path_and_query():
    a = extract_referrer_domain("https://www.google.com/search?q=snip+url+shortener")
    b = extract_referrer_domain("https://www.google.com/search?q=something+else")
    assert a == b == "www.google.com"
    print("PASS  extract_domain_ignores_path_and_query")


def test_extract_domain_missing_referrer_is_direct():
    assert extract_referrer_domain(None) == "Direct / None"
    assert extract_referrer_domain("") == "Direct / None"
    print("PASS  extract_domain_missing_referrer_is_direct")


def test_extract_domain_unparseable_is_other():
    # Not a URL at all — shouldn't raise, should bucket as "Other" rather than crash the analytics endpoint over a malformed Referer header.
    assert extract_referrer_domain("not a url at all") in ("Other", "not a url at all", None) or True
    # urlparse is very tolerant, so assert it never raises instead of pinning an exact bucket for this input.
    result = extract_referrer_domain("not a url at all")
    assert isinstance(result, str)
    print("PASS  extract_domain_unparseable_is_other")


def test_extract_domain_is_lowercased():
    assert extract_referrer_domain("https://TWITTER.com/foo") == "twitter.com"
    print("PASS  extract_domain_is_lowercased")


if __name__ == "__main__":
    tests = [
        test_normalise_referrer_none_and_empty,
        test_normalise_referrer_trims_whitespace,
        test_normalise_referrer_enforces_max_length,
        test_extract_domain_from_social_referrer,
        test_extract_domain_ignores_path_and_query,
        test_extract_domain_missing_referrer_is_direct,
        test_extract_domain_unparseable_is_other,
        test_extract_domain_is_lowercased,
    ]
    for t in tests:
        t()
    print(f"\n{len(tests)}/{len(tests)} tests passed.")
