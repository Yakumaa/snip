"""
Standalone unit tests for User-Agent parsing (app/utils/user_agent.py).
Run with:  python tests/tests_user_agent.py
No Flask, database, or network access required — this is pure string parsing against real-world UA strings.
"""
import sys
sys.path.insert(0, ".")

from app.utils.user_agent import parse_user_agent

IPHONE_SAFARI = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
)
ANDROID_CHROME = (
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
)
WINDOWS_CHROME = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
MAC_SAFARI = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.0 Safari/605.1.15"
)
IPAD_SAFARI = (
    "Mozilla/5.0 (iPad; CPU OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
)
GOOGLEBOT = "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"


def test_empty_or_none_returns_all_none():
    for ua in (None, "", "   "):
        result = parse_user_agent(ua)
        assert result == {"browser": None, "os": None, "device_type": None}, result
    print("PASS  empty_or_none_returns_all_none")


def test_iphone_safari_is_mobile():
    result = parse_user_agent(IPHONE_SAFARI)
    assert result["device_type"] == "mobile", result
    assert result["os"] == "iOS", result
    assert "Safari" in (result["browser"] or ""), result
    print("PASS  iphone_safari_is_mobile")


def test_android_chrome_is_mobile():
    result = parse_user_agent(ANDROID_CHROME)
    assert result["device_type"] == "mobile", result
    assert result["os"] == "Android", result
    assert result["browser"] == "Chrome Mobile", result
    print("PASS  android_chrome_is_mobile")


def test_windows_chrome_is_desktop():
    result = parse_user_agent(WINDOWS_CHROME)
    assert result["device_type"] == "desktop", result
    assert result["os"] == "Windows", result
    assert result["browser"] == "Chrome", result
    print("PASS  windows_chrome_is_desktop")


def test_mac_safari_is_desktop():
    result = parse_user_agent(MAC_SAFARI)
    assert result["device_type"] == "desktop", result
    assert result["os"] == "Mac OS X", result
    assert result["browser"] == "Safari", result
    print("PASS  mac_safari_is_desktop")


def test_ipad_is_tablet():
    result = parse_user_agent(IPAD_SAFARI)
    assert result["device_type"] == "tablet", result
    print("PASS  ipad_is_tablet")


def test_googlebot_is_bot():
    result = parse_user_agent(GOOGLEBOT)
    assert result["device_type"] == "bot", result
    print("PASS  googlebot_is_bot")


def test_garbage_input_never_raises():
    # A UA string is fully client-controlled — parsing garbage should degrade to unknown fields, never raise and break the redirect.
    for garbage in ("asdf;;;<><>", "a" * 5000, "\x00\x01\x02"):
        result = parse_user_agent(garbage)
        assert set(result.keys()) == {"browser", "os", "device_type"}, result
    print("PASS  garbage_input_never_raises")


def test_fields_truncated_to_column_length():
    from app.utils.user_agent import MAX_FIELD_LENGTH
    result = parse_user_agent(WINDOWS_CHROME)
    if result["browser"]:
        assert len(result["browser"]) <= MAX_FIELD_LENGTH
    if result["os"]:
        assert len(result["os"]) <= MAX_FIELD_LENGTH
    print("PASS  fields_truncated_to_column_length")


if __name__ == "__main__":
    tests = [
        test_empty_or_none_returns_all_none,
        test_iphone_safari_is_mobile,
        test_android_chrome_is_mobile,
        test_windows_chrome_is_desktop,
        test_mac_safari_is_desktop,
        test_ipad_is_tablet,
        test_googlebot_is_bot,
        test_garbage_input_never_raises,
        test_fields_truncated_to_column_length,
    ]
    for t in tests:
        t()
    print(f"\n{len(tests)}/{len(tests)} tests passed.")
