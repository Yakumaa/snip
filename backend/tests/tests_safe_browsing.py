"""
Unit tests for the Safe Browsing integration (app/services/safe_browsing.py).

Mocks requests.post throughout, so these run offline / in CI with no real
API key and no network access required.

An optional LIVE integration check against the real Google API is included
at the bottom, gated behind a real SAFE_BROWSING_API_KEY being set in the
environment — it's skipped automatically otherwise, so this file is safe to
run in any environment.

Run with:  python tests_safe_browsing.py
"""
import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, ".")

import requests

# Make sure a key is "configured" for the mocked tests below — we're testing
# the request/response handling, not the "no key" fallback (that's tested
# separately in test_no_api_key_fails_open, which manages its own env var).
os.environ.setdefault("SAFE_BROWSING_API_KEY", "test-key-for-mocked-tests")

from app.services import safe_browsing

def _mock_response(json_body, status_ok=True):
    resp = MagicMock()
    resp.json.return_value = json_body
    if status_ok:
        resp.raise_for_status.return_value = None
    return resp

def test_safe_url_returns_true():
    with patch("app.services.safe_browsing.requests.post") as mock_post:
        mock_post.return_value = _mock_response({})  # no "matches" key — real API shape for clean URLs
        is_safe, threat_type = safe_browsing.check_url_safety("https://example.com")
        assert is_safe is True
        assert threat_type is None
    print("PASS  safe_url_returns_true")

def test_flagged_url_returns_false_with_threat_type():
    with patch("app.services.safe_browsing.requests.post") as mock_post:
        mock_post.return_value = _mock_response({
            "matches": [{"threatType": "SOCIAL_ENGINEERING", "platformType": "ANY_PLATFORM"}]
        })
        is_safe, threat_type = safe_browsing.check_url_safety("https://phishing-example.com")
        assert is_safe is False
        assert threat_type == "SOCIAL_ENGINEERING"
    print("PASS  flagged_url_returns_false_with_threat_type")

def test_multiple_matches_returns_first_threat_type():
    with patch("app.services.safe_browsing.requests.post") as mock_post:
        mock_post.return_value = _mock_response({
            "matches": [
                {"threatType": "MALWARE", "platformType": "ANY_PLATFORM"},
                {"threatType": "SOCIAL_ENGINEERING", "platformType": "ANY_PLATFORM"},
            ]
        })
        is_safe, threat_type = safe_browsing.check_url_safety("https://very-bad-example.com")
        assert is_safe is False
        assert threat_type == "MALWARE"
    print("PASS  multiple_matches_returns_first_threat_type")

def test_timeout_fails_open():
    with patch("app.services.safe_browsing.requests.post") as mock_post:
        mock_post.side_effect = requests.exceptions.Timeout("simulated timeout")
        is_safe, threat_type = safe_browsing.check_url_safety("https://example.com")
        assert is_safe is True
        assert threat_type is None
    print("PASS  timeout_fails_open")

def test_connection_error_fails_open():
    with patch("app.services.safe_browsing.requests.post") as mock_post:
        mock_post.side_effect = requests.exceptions.ConnectionError("simulated connection error")
        is_safe, threat_type = safe_browsing.check_url_safety("https://example.com")
        assert is_safe is True
        assert threat_type is None
    print("PASS  connection_error_fails_open")

def test_http_error_fails_open():
    """Covers bad API key, quota exceeded, or Google-side 5xx — all surface as raise_for_status()."""
    with patch("app.services.safe_browsing.requests.post") as mock_post:
        resp = MagicMock()
        resp.raise_for_status.side_effect = requests.exceptions.HTTPError("403 Forbidden")
        mock_post.return_value = resp
        is_safe, threat_type = safe_browsing.check_url_safety("https://example.com")
        assert is_safe is True
        assert threat_type is None
    print("PASS  http_error_fails_open")

def test_malformed_json_response_fails_open():
    with patch("app.services.safe_browsing.requests.post") as mock_post:
        resp = MagicMock()
        resp.raise_for_status.return_value = None
        resp.json.side_effect = ValueError("not JSON")
        mock_post.return_value = resp
        is_safe, threat_type = safe_browsing.check_url_safety("https://example.com")
        assert is_safe is True
        assert threat_type is None
    print("PASS  malformed_json_response_fails_open")

def test_no_api_key_fails_open():
    """
    Isolated from the module-level env var set above — temporarily clears
    SAFE_BROWSING_API_KEY, reloads the module so it re-reads the (now empty)
    environment, and restores everything afterward.
    """
    import importlib

    original_key = os.environ.pop("SAFE_BROWSING_API_KEY", None)
    try:
        importlib.reload(safe_browsing)
        is_safe, threat_type = safe_browsing.check_url_safety("https://example.com")
        assert is_safe is True
        assert threat_type is None
    finally:
        if original_key is not None:
            os.environ["SAFE_BROWSING_API_KEY"] = original_key
        importlib.reload(safe_browsing)  # restore module state for any tests that run after this one
    print("PASS  no_api_key_fails_open")

def test_request_payload_shape():
    """Confirms we send the URL and expected threat categories in the shape Google's API expects."""
    with patch("app.services.safe_browsing.requests.post") as mock_post:
        mock_post.return_value = _mock_response({})
        safe_browsing.check_url_safety("https://example.com/some/path")

        _, kwargs = mock_post.call_args
        assert kwargs["params"] == {"key": os.environ["SAFE_BROWSING_API_KEY"]}
        entries = kwargs["json"]["threatInfo"]["threatEntries"]
        assert entries == [{"url": "https://example.com/some/path"}]
        assert "MALWARE" in kwargs["json"]["threatInfo"]["threatTypes"]
    print("PASS  request_payload_shape")

def test_live_against_real_google_api():
    """
    Optional: only runs if a real SAFE_BROWSING_API_KEY is set (not the
    placeholder one this file sets by default). Uses Google's official,
    permanent test URLs — safe to hit repeatedly, they always match.
    """
    key = os.environ.get("SAFE_BROWSING_API_KEY", "")
    if key in ("", "test-key-for-mocked-tests"):
        print("SKIP  live_against_real_google_api  (no real SAFE_BROWSING_API_KEY set)")
        return

    malware_test_url = "http://testsafebrowsing.appspot.com/apiv4/ANY_PLATFORM/MALWARE/URL/"
    is_safe, threat_type = safe_browsing.check_url_safety(malware_test_url)
    assert is_safe is False, "Google's own permanent test URL should always be flagged"
    assert threat_type == "MALWARE"
    print(f"PASS  live_against_real_google_api  (flagged as {threat_type})")

    is_safe, _ = safe_browsing.check_url_safety("https://www.wikipedia.org")
    assert is_safe is True, "A legitimate, well-known site should not be flagged"
    print("PASS  live_against_real_google_api  (clean site correctly passed)")

if __name__ == "__main__":
    tests = [
        test_safe_url_returns_true,
        test_flagged_url_returns_false_with_threat_type,
        test_multiple_matches_returns_first_threat_type,
        test_timeout_fails_open,
        test_connection_error_fails_open,
        test_http_error_fails_open,
        test_malformed_json_response_fails_open,
        test_no_api_key_fails_open,
        test_request_payload_shape,
        test_live_against_real_google_api,
    ]
    for t in tests:
        t()
    print(f"\n{len(tests)}/{len(tests)} tests completed.")
