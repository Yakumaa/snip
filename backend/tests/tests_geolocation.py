"""
Unit tests for IP geolocation (app/services/geolocation.py).

Mocks requests.get throughout, so these run offline / in CI with no network access required — same pattern as tests_safe_browsing.py.

A lightweight fake Redis client (dict-backed) stands in for the real `redis.Redis` so the caching behaviour (hit/miss/negative-cache TTL) is exercised without needing a running Redis server.

Run with:  python tests/tests_geolocation.py
"""
import json
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, ".")

import requests

from app.services import geolocation


class FakeRedis:
    """Minimal in-memory stand-in for redis.Redis — just enough of the surface (get/set with ex=) that geolocation.py actually uses."""

    def __init__(self):
        self.store = {}

    def get(self, key):
        return self.store.get(key)

    def set(self, key, value, ex=None):
        self.store[key] = value
        return True


def _mock_response(json_body, status_ok=True):
    resp = MagicMock()
    resp.json.return_value = json_body
    if status_ok:
        resp.raise_for_status.return_value = None
    return resp


def _hash(ip: str) -> str:
    import hashlib
    return hashlib.sha256(ip.encode()).hexdigest()


# Non-public addresses never even hit the network
def test_private_ip_returns_empty_without_network_call():
    with patch("app.services.geolocation.requests.get") as mock_get:
        result = geolocation.get_geolocation("192.168.1.1", _hash("192.168.1.1"))
        assert result == {"country": None, "country_code": None, "city": None}
        mock_get.assert_not_called()
    print("PASS  private_ip_returns_empty_without_network_call")


def test_loopback_ip_returns_empty_without_network_call():
    with patch("app.services.geolocation.requests.get") as mock_get:
        result = geolocation.get_geolocation("127.0.0.1", _hash("127.0.0.1"))
        assert result == {"country": None, "country_code": None, "city": None}
        mock_get.assert_not_called()
    print("PASS  loopback_ip_returns_empty_without_network_call")


# Successful lookups
def test_successful_lookup_returns_location():
    with patch("app.services.geolocation.requests.get") as mock_get:
        mock_get.return_value = _mock_response({
            "status": "success", "country": "United States",
            "countryCode": "US", "city": "Mountain View",
        })
        result = geolocation.get_geolocation("8.8.8.8", _hash("8.8.8.8"))
        assert result == {
            "country": "United States", "country_code": "US", "city": "Mountain View",
        }
    print("PASS  successful_lookup_returns_location")


def test_api_status_fail_returns_empty():
    """ip-api.com returns status:'fail' for e.g. malformed/reserved IPs it can't place."""
    with patch("app.services.geolocation.requests.get") as mock_get:
        mock_get.return_value = _mock_response({"status": "fail", "message": "reserved range"})
        result = geolocation.get_geolocation("8.8.8.8", _hash("8.8.8.8"))
        assert result == {"country": None, "country_code": None, "city": None}
    print("PASS  api_status_fail_returns_empty")


# Fail-open behaviour
def test_timeout_fails_open():
    with patch("app.services.geolocation.requests.get") as mock_get:
        mock_get.side_effect = requests.exceptions.Timeout("simulated timeout")
        result = geolocation.get_geolocation("8.8.8.8", _hash("8.8.8.8"))
        assert result == {"country": None, "country_code": None, "city": None}
    print("PASS  timeout_fails_open")


def test_connection_error_fails_open():
    with patch("app.services.geolocation.requests.get") as mock_get:
        mock_get.side_effect = requests.exceptions.ConnectionError("simulated connection error")
        result = geolocation.get_geolocation("8.8.8.8", _hash("8.8.8.8"))
        assert result == {"country": None, "country_code": None, "city": None}
    print("PASS  connection_error_fails_open")


def test_malformed_json_fails_open():
    with patch("app.services.geolocation.requests.get") as mock_get:
        resp = MagicMock()
        resp.raise_for_status.return_value = None
        resp.json.side_effect = ValueError("not JSON")
        mock_get.return_value = resp
        result = geolocation.get_geolocation("8.8.8.8", _hash("8.8.8.8"))
        assert result == {"country": None, "country_code": None, "city": None}
    print("PASS  malformed_json_fails_open")


# Caching behaviour
def test_successful_lookup_is_cached():
    fake_redis = FakeRedis()
    ip, ip_hash = "8.8.8.8", _hash("8.8.8.8")
    with patch("app.services.geolocation.requests.get") as mock_get:
        mock_get.return_value = _mock_response({
            "status": "success", "country": "United States",
            "countryCode": "US", "city": "Mountain View",
        })
        geolocation.get_geolocation(ip, ip_hash, redis_client=fake_redis)
        assert mock_get.call_count == 1

        # Second call for the same IP should hit the cache, not the network.
        result2 = geolocation.get_geolocation(ip, ip_hash, redis_client=fake_redis)
        assert mock_get.call_count == 1, "second call should have used the cache"
        assert result2["country"] == "United States"
    print("PASS  successful_lookup_is_cached")


def test_cache_key_never_contains_raw_ip():
    """The cache key must be derived from the IP hash, not the raw IP itself — the whole point of resolving at click-time is to never persist the IP."""
    fake_redis = FakeRedis()
    ip, ip_hash = "8.8.8.8", _hash("8.8.8.8")
    with patch("app.services.geolocation.requests.get") as mock_get:
        mock_get.return_value = _mock_response({
            "status": "success", "country": "United States",
            "countryCode": "US", "city": "Mountain View",
        })
        geolocation.get_geolocation(ip, ip_hash, redis_client=fake_redis)

    for key in fake_redis.store:
        assert ip not in key, f"raw IP leaked into cache key: {key}"
        assert ip_hash in key
    print("PASS  cache_key_never_contains_raw_ip")


def test_failed_lookup_is_negative_cached_briefly():
    """A failed lookup should still be cached (with a short TTL) so an outage doesn't add network latency to every single click."""
    fake_redis = FakeRedis()
    ip, ip_hash = "8.8.8.8", _hash("8.8.8.8")
    with patch("app.services.geolocation.requests.get") as mock_get:
        mock_get.side_effect = requests.exceptions.ConnectionError("simulated outage")
        geolocation.get_geolocation(ip, ip_hash, redis_client=fake_redis)
        assert mock_get.call_count == 1

        # Second call during the "outage window" should be served from the negative cache rather than retrying the network.
        result2 = geolocation.get_geolocation(ip, ip_hash, redis_client=fake_redis)
        assert mock_get.call_count == 1, "second call should have used the negative cache"
        assert result2 == {"country": None, "country_code": None, "city": None}
    print("PASS  failed_lookup_is_negative_cached_briefly")


def test_broken_cache_does_not_break_lookup():
    """If Redis itself errors on get/set, geolocation should still work — just without the caching benefit."""
    class ExplodingRedis:
        def get(self, key):
            raise ConnectionError("redis is down")
        def set(self, key, value, ex=None):
            raise ConnectionError("redis is down")

    with patch("app.services.geolocation.requests.get") as mock_get:
        mock_get.return_value = _mock_response({
            "status": "success", "country": "United States",
            "countryCode": "US", "city": "Mountain View",
        })
        result = geolocation.get_geolocation("8.8.8.8", _hash("8.8.8.8"), redis_client=ExplodingRedis())
        assert result["country"] == "United States"
    print("PASS  broken_cache_does_not_break_lookup")


def test_no_redis_client_skips_caching_but_still_works():
    with patch("app.services.geolocation.requests.get") as mock_get:
        mock_get.return_value = _mock_response({
            "status": "success", "country": "United States",
            "countryCode": "US", "city": "Mountain View",
        })
        result = geolocation.get_geolocation("8.8.8.8", _hash("8.8.8.8"), redis_client=None)
        assert result["country"] == "United States"
    print("PASS  no_redis_client_skips_caching_but_still_works")


if __name__ == "__main__":
    tests = [
        test_private_ip_returns_empty_without_network_call,
        test_loopback_ip_returns_empty_without_network_call,
        test_successful_lookup_returns_location,
        test_api_status_fail_returns_empty,
        test_timeout_fails_open,
        test_connection_error_fails_open,
        test_malformed_json_fails_open,
        test_successful_lookup_is_cached,
        test_cache_key_never_contains_raw_ip,
        test_failed_lookup_is_negative_cached_briefly,
        test_broken_cache_does_not_break_lookup,
        test_no_redis_client_skips_caching_but_still_works,
    ]
    for t in tests:
        t()
    print(f"\n{len(tests)}/{len(tests)} tests passed.")
