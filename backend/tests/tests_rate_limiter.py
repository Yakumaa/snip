"""
Standalone unit tests for the sliding window rate limiter core logic.
Run with:  python tests_rate_limiter.py
No Flask or database required.
"""
import sys
sys.path.insert(0, ".")

from app.middleware.rate_limiter import _check_rate_limit, _store

LIMIT = 5
WINDOW = 60  # seconds

def reset():
    _store.clear()

def test_allows_up_to_limit():
    reset()
    for i in range(LIMIT):
        allowed, _ = _check_rate_limit("1.2.3.4", float(i), LIMIT, WINDOW)
        assert allowed, f"Request {i+1} should be allowed"
    print("PASS  allows_up_to_limit")

def test_blocks_on_limit_exceeded():
    reset()
    for i in range(LIMIT):
        _check_rate_limit("1.2.3.4", float(i), LIMIT, WINDOW)
    allowed, retry_after = _check_rate_limit("1.2.3.4", float(LIMIT), LIMIT, WINDOW)
    assert not allowed, "6th request should be blocked"
    assert retry_after > 0, "retry_after must be positive"
    print(f"PASS  blocks_on_limit_exceeded  (retry_after={retry_after}s)")

def test_retry_after_is_accurate():
    reset()
    # Fire 5 requests at t=0
    for _ in range(LIMIT):
        _check_rate_limit("1.2.3.4", 0.0, LIMIT, WINDOW)
    # 6th request at t=10 — oldest entry (t=0) expires at t=60
    allowed, retry_after = _check_rate_limit("1.2.3.4", 10.0, LIMIT, WINDOW)
    assert not allowed
    # retry_after should be ceil(0 + 60 - 10) = 50
    assert retry_after == 50, f"Expected 50, got {retry_after}"
    print(f"PASS  retry_after_is_accurate  (retry_after={retry_after}s)")

def test_window_slides_correctly():
    reset()
    # Fire 5 requests at t=0
    for _ in range(LIMIT):
        _check_rate_limit("1.2.3.4", 0.0, LIMIT, WINDOW)
    # At t=61 the window has slid past all 5 — a new request must be allowed
    allowed, _ = _check_rate_limit("1.2.3.4", 61.0, LIMIT, WINDOW)
    assert allowed, "After window expires, requests should be allowed again"
    print("PASS  window_slides_correctly")


def test_different_ips_are_independent():
    reset()
    for _ in range(LIMIT):
        _check_rate_limit("1.1.1.1", 0.0, LIMIT, WINDOW)
    # IP 1 is at the limit; IP 2 is untouched
    allowed_1, _ = _check_rate_limit("1.1.1.1", 1.0, LIMIT, WINDOW)
    allowed_2, _ = _check_rate_limit("2.2.2.2", 1.0, LIMIT, WINDOW)
    assert not allowed_1, "IP 1 should be blocked"
    assert allowed_2,     "IP 2 should still be allowed"
    print("PASS  different_ips_are_independent")


def test_partial_window_expiry():
    reset()
    # 3 requests at t=0, 2 requests at t=30
    for _ in range(3):
        _check_rate_limit("1.2.3.4", 0.0, LIMIT, WINDOW)
    for _ in range(2):
        _check_rate_limit("1.2.3.4", 30.0, LIMIT, WINDOW)
    # At t=61: the 3 requests from t=0 have expired, only the 2 from t=30 remain
    # → 3 more requests should be allowed
    results = [_check_rate_limit("1.2.3.4", 61.0, LIMIT, WINDOW) for _ in range(3)]
    assert all(r[0] for r in results), "3 requests should be allowed after partial expiry"
    print("PASS  partial_window_expiry")


if __name__ == "__main__":
    tests = [
        test_allows_up_to_limit,
        test_blocks_on_limit_exceeded,
        test_retry_after_is_accurate,
        test_window_slides_correctly,
        test_different_ips_are_independent,
        test_partial_window_expiry,
    ]
    for t in tests:
        t()
    print(f"\n{len(tests)}/{len(tests)} tests passed.")
