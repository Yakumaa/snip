"""
Unit tests for URL validation and SSRF/private-network hardening (app/utils/helpers.py: is_valid_url, check_ssrf_safety).

check_ssrf_safety's DNS-based tests require real internet/DNS access (to resolve public hostnames and the real nip.io wildcard-DNS bypass) — this is DNS resolution only, not HTTP, so it works even in network-restricted CI environments that block arbitrary outbound HTTP but allow DNS.

Run with:  python tests_url_validation.py
"""
import sys

sys.path.insert(0, ".")

from app.utils.helpers import MAX_URL_LENGTH, check_ssrf_safety, is_valid_url

# is_valid_url — syntactic checks
def test_valid_public_urls_pass():
    for url in [
        "https://example.com",
        "http://www.example.com/some/path?query=1",
        "example.com",  # scheme gets added by normalise_url elsewhere; is_valid_url alone still accepts it
    ]:
        assert is_valid_url(url), f"Expected valid: {url}"
    print("PASS  valid_public_urls_pass")

def test_empty_and_non_string_rejected():
    assert not is_valid_url("")
    assert not is_valid_url(None)
    assert not is_valid_url("   ")
    print("PASS  empty_and_non_string_rejected")

def test_non_http_schemes_rejected():
    for url in ["javascript:alert(1)", "ftp://example.com/file", "file:///etc/passwd", "data:text/html,hi"]:
        assert not is_valid_url(url), f"Expected rejected: {url}"
    print("PASS  non_http_schemes_rejected")

def test_embedded_credentials_rejected():
    """Phishing trick: http://trusted.com@evil.com/ looks like trusted.com but isn't."""
    for url in ["http://trusted.com@evil.com/", "http://user:pass@example.com/"]:
        assert not is_valid_url(url), f"Expected rejected (embedded credentials): {url}"
    assert is_valid_url("https://example.com/path"), "Normal URL without '@' should still pass"
    print("PASS  embedded_credentials_rejected")

def test_max_length_enforced():
    too_long = "https://example.com/" + "a" * MAX_URL_LENGTH
    assert not is_valid_url(too_long)
    normal = "https://example.com/" + "a" * 100
    assert is_valid_url(normal)
    print("PASS  max_length_enforced")

# check_ssrf_safety — private/internal network checks
def test_literal_private_ips_blocked():
    for url in [
        "http://127.0.0.1/",
        "http://169.254.169.254/",   # AWS/GCP/Azure cloud metadata endpoint
        "http://10.0.0.5/",
        "http://172.16.0.1/",
        "http://192.168.1.1/",
        "http://[::1]/",             # IPv6 loopback
        "http://[fe80::1]/",         # IPv6 link-local
        "http://0.0.0.0/",
    ]:
        is_safe, reason = check_ssrf_safety(url)
        assert not is_safe, f"Expected blocked: {url}"
        assert reason
    print("PASS  literal_private_ips_blocked")

def test_literal_public_ips_allowed():
    for url in ["http://93.184.216.34/", "https://1.1.1.1/"]:
        is_safe, reason = check_ssrf_safety(url)
        assert is_safe, f"Expected allowed: {url} (reason: {reason})"
    print("PASS  literal_public_ips_allowed")

def test_blocked_hostnames():
    for url in [
        "http://localhost/",
        "http://localhost.localdomain/",
        "http://metadata.google.internal/",
        "http://printer.local/",
    ]:
        is_safe, reason = check_ssrf_safety(url)
        assert not is_safe, f"Expected blocked: {url}"
    print("PASS  blocked_hostnames")

def test_public_hostname_allowed():
    is_safe, reason = check_ssrf_safety("https://www.wikipedia.org")
    assert is_safe, f"Expected allowed: (reason: {reason})"
    print("PASS  public_hostname_allowed")

def test_nonresolving_hostname_fails_open():
    is_safe, reason = check_ssrf_safety("https://this-domain-should-never-exist-abc123xyz.com")
    assert is_safe, "A hostname that doesn't resolve should fail open (nothing to check)"
    print("PASS  nonresolving_hostname_fails_open")

def test_wildcard_dns_bypass_is_caught():
    """
    THE key regression test: nip.io is a real, live wildcard-DNS service that resolves "127.0.0.1.nip.io" to 127.0.0.1. A hostname-string check would never catch this (the string mentions no blocked term) — only resolving DNS and inspecting the real IP catches it.
    """
    is_safe, reason = check_ssrf_safety("http://127.0.0.1.nip.io/")
    assert not is_safe, "nip.io bypass should be caught by DNS resolution"
    assert "127.0.0.1" in reason
    print(f"PASS  wildcard_dns_bypass_is_caught  ({reason})")

if __name__ == "__main__":
    tests = [
        test_valid_public_urls_pass,
        test_empty_and_non_string_rejected,
        test_non_http_schemes_rejected,
        test_embedded_credentials_rejected,
        test_max_length_enforced,
        test_literal_private_ips_blocked,
        test_literal_public_ips_allowed,
        test_blocked_hostnames,
        test_public_hostname_allowed,
        test_nonresolving_hostname_fails_open,
        test_wildcard_dns_bypass_is_caught,
    ]
    for t in tests:
        t()
    print(f"\n{len(tests)}/{len(tests)} tests passed.")
