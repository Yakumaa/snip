"""
Standalone unit tests for the Redis-backed sliding window rate limiter.

Requires a running Redis instance (set REDIS_URL, defaults to redis://localhost:6379/0 — matches what you get from `docker compose up redis` or the exposed port 6379 in docker-compose.yml).

Run with:  python tests_rate_limiter.py
"""
import sys
sys.path.insert(0, ".")

from app.middleware.rate_limiter import _check_rate_limit
from app.extensions import redis_client

LIMIT = 5
WINDOW = 60  # seconds

TEST_IP_PREFIX = "test-suite-ip"  # keeps test keys clearly namespaced

def reset(ip: str):
    """Delete this test's rate-limit key so each test starts clean."""
    redis_client.delete(f"rate_limit:{ip}")

def test_allows_up_to_limit():
    ip = f"{TEST_IP_PREFIX}-1"
    reset(ip)
    for i in range(LIMIT):
        allowed, _ = _check_rate_limit(ip, float(i), LIMIT, WINDOW)
        assert allowed, f"Request {i+1} should be allowed"
    print("PASS  allows_up_to_limit")

def test_blocks_on_limit_exceeded():
    ip = f"{TEST_IP_PREFIX}-2"
    reset(ip)
    for i in range(LIMIT):
        _check_rate_limit(ip, float(i), LIMIT, WINDOW)
    allowed, retry_after = _check_rate_limit(ip, float(LIMIT), LIMIT, WINDOW)
    assert not allowed, "6th request should be blocked"
    assert retry_after > 0, "retry_after must be positive"
    print(f"PASS  blocks_on_limit_exceeded  (retry_after={retry_after}s)")

def test_retry_after_is_accurate():
    ip = f"{TEST_IP_PREFIX}-3"
    reset(ip)
    # Fire 5 requests at t=0
    for _ in range(LIMIT):
        _check_rate_limit(ip, 0.0, LIMIT, WINDOW)
    # 6th request at t=10 — oldest entry (t=0) expires at t=60
    allowed, retry_after = _check_rate_limit(ip, 10.0, LIMIT, WINDOW)
    assert not allowed
    # retry_after should be ceil(0 + 60 - 10) = 50
    assert retry_after == 50, f"Expected 50, got {retry_after}"
    print(f"PASS  retry_after_is_accurate  (retry_after={retry_after}s)")

def test_window_slides_correctly():
    ip = f"{TEST_IP_PREFIX}-4"
    reset(ip)
    # Fire 5 requests at t=0
    for _ in range(LIMIT):
        _check_rate_limit(ip, 0.0, LIMIT, WINDOW)
    # At t=61 the window has slid past all 5 — a new request must be allowed
    allowed, _ = _check_rate_limit(ip, 61.0, LIMIT, WINDOW)
    assert allowed, "After window expires, requests should be allowed again"
    print("PASS  window_slides_correctly")

def test_different_ips_are_independent():
    ip1, ip2 = f"{TEST_IP_PREFIX}-5a", f"{TEST_IP_PREFIX}-5b"
    reset(ip1)
    reset(ip2)
    for _ in range(LIMIT):
        _check_rate_limit(ip1, 0.0, LIMIT, WINDOW)
    # IP 1 is at the limit; IP 2 is untouched
    allowed_1, _ = _check_rate_limit(ip1, 1.0, LIMIT, WINDOW)
    allowed_2, _ = _check_rate_limit(ip2, 1.0, LIMIT, WINDOW)
    assert not allowed_1, "IP 1 should be blocked"
    assert allowed_2,     "IP 2 should still be allowed"
    print("PASS  different_ips_are_independent")

def test_partial_window_expiry():
    ip = f"{TEST_IP_PREFIX}-6"
    reset(ip)
    # 3 requests at t=0, 2 requests at t=30
    for _ in range(3):
        _check_rate_limit(ip, 0.0, LIMIT, WINDOW)
    for _ in range(2):
        _check_rate_limit(ip, 30.0, LIMIT, WINDOW)
    # At t=61: the 3 requests from t=0 have expired, only the 2 from t=30 remain
    # → 3 more requests should be allowed
    results = [_check_rate_limit(ip, 61.0, LIMIT, WINDOW) for _ in range(3)]
    assert all(r[0] for r in results), "3 requests should be allowed after partial expiry"
    print("PASS  partial_window_expiry")

def test_concurrent_requests_cant_exceed_limit():
    """
    Fires LIMIT * 3 requests at the *same* timestamp using a thread pool, to sanity-check that the Lua script's atomicity actually holds under real concurrency (this is the race condition a naive read-then-write implementation would fail).
    """
    import concurrent.futures

    ip = f"{TEST_IP_PREFIX}-7"
    reset(ip)
    now = 1000.0

    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool:
        results = list(pool.map(
            lambda _: _check_rate_limit(ip, now, LIMIT, WINDOW),
            range(LIMIT * 3),
        ))

    allowed_count = sum(1 for allowed, _ in results if allowed)
    assert allowed_count == LIMIT, (
        f"Expected exactly {LIMIT} requests allowed under concurrency, got {allowed_count}"
    )
    print(f"PASS  concurrent_requests_cant_exceed_limit  (allowed={allowed_count}/{LIMIT})")

if __name__ == "__main__":
    try:
        redis_client.ping()
    except Exception as exc:
        print(f"Could not reach Redis at {redis_client.get_connection_kwargs()} — is it running?")
        print(f"({exc})")
        sys.exit(1)

    tests = [
        test_allows_up_to_limit,
        test_blocks_on_limit_exceeded,
        test_retry_after_is_accurate,
        test_window_slides_correctly,
        test_different_ips_are_independent,
        test_partial_window_expiry,
        test_concurrent_requests_cant_exceed_limit,
    ]
    for t in tests:
        t()
    print(f"\n{len(tests)}/{len(tests)} tests passed.")