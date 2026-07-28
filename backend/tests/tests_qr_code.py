"""
Standalone unit tests for QR code generation (app/utils/qr_code.py).

Run with:  python tests/tests_qr_code.py
No Flask, database, or network access required — this exercises the
pure generate_qr_png() function directly.
"""
import io
import sys

sys.path.insert(0, ".")

from PIL import Image

from app.utils.qr_code import (
    DEFAULT_BOX_SIZE,
    MAX_BOX_SIZE,
    MIN_BOX_SIZE,
    QUIET_ZONE_BORDER,
    generate_qr_png,
)

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def test_output_is_valid_png():
    png_bytes = generate_qr_png("https://example.com/abc123")
    assert png_bytes[:8] == PNG_SIGNATURE, "output does not start with the PNG file signature"
    # Round-trip through Pillow to confirm it's a genuinely valid, openable image.
    img = Image.open(io.BytesIO(png_bytes))
    assert img.format == "PNG"
    print("PASS  output_is_valid_png")


def test_default_box_size_produces_reasonable_dimensions():
    png_bytes = generate_qr_png("https://short.example/a1B2c3")
    img = Image.open(io.BytesIO(png_bytes))
    # A short URL like this fits comfortably in QR version 3-5; at the
    # default box_size the image should be a modest, non-trivial size.
    assert 100 < img.width < 500
    assert img.width == img.height, "QR codes are always square"
    print(f"PASS  default_box_size_produces_reasonable_dimensions  ({img.width}x{img.height})")


def test_larger_box_size_produces_larger_image():
    small = Image.open(io.BytesIO(generate_qr_png("https://example.com/x", box_size=4)))
    large = Image.open(io.BytesIO(generate_qr_png("https://example.com/x", box_size=20)))
    assert large.width > small.width
    print(f"PASS  larger_box_size_produces_larger_image  (small={small.width}, large={large.width})")


def test_box_size_below_minimum_is_clamped_not_rejected():
    # Should not raise — silently clamped to MIN_BOX_SIZE.
    png_bytes = generate_qr_png("https://example.com/x", box_size=0)
    assert png_bytes[:8] == PNG_SIGNATURE
    png_bytes_negative = generate_qr_png("https://example.com/x", box_size=-50)
    assert png_bytes_negative[:8] == PNG_SIGNATURE
    print("PASS  box_size_below_minimum_is_clamped_not_rejected")


def test_box_size_above_maximum_is_clamped_not_rejected():
    unclamped_would_be_huge = MAX_BOX_SIZE + 1000
    png_bytes = generate_qr_png("https://example.com/x", box_size=unclamped_would_be_huge)
    img = Image.open(io.BytesIO(png_bytes))
    at_max = Image.open(io.BytesIO(generate_qr_png("https://example.com/x", box_size=MAX_BOX_SIZE)))
    assert img.width == at_max.width, "a huge requested box_size should clamp to MAX_BOX_SIZE, not balloon the image"
    print(f"PASS  box_size_above_maximum_is_clamped_not_rejected  (clamped width={img.width})")


def test_same_input_produces_identical_output():
    # Deterministic — same URL should always encode to the same QR image,
    # which matters for the route's aggressive Cache-Control headers.
    a = generate_qr_png("https://example.com/stable-alias")
    b = generate_qr_png("https://example.com/stable-alias")
    assert a == b
    print("PASS  same_input_produces_identical_output")


def test_different_input_produces_different_output():
    a = generate_qr_png("https://example.com/alias-one")
    b = generate_qr_png("https://example.com/alias-two")
    assert a != b
    print("PASS  different_input_produces_different_output")


def test_quiet_zone_border_is_present():
    # The outer border should be blank (white) — this is the "quiet zone"
    # scanners rely on to locate the code. A regression here (e.g. border=0)
    # would silently produce codes that don't scan reliably.
    png_bytes = generate_qr_png("https://example.com/x", box_size=10)
    img = Image.open(io.BytesIO(png_bytes)).convert("L")
    border_px = QUIET_ZONE_BORDER * 10  # border modules * box_size
    # Sample a strip just inside the border — should be entirely white (255).
    top_strip = [img.getpixel((x, 2)) for x in range(0, img.width, 5)]
    assert all(p == 255 for p in top_strip), "expected a blank quiet zone at the top edge"
    print("PASS  quiet_zone_border_is_present")


def test_empty_string_does_not_raise():
    # An empty alias/URL shouldn't happen in practice (routes always pass
    # a real short URL), but the function itself shouldn't blow up on it.
    png_bytes = generate_qr_png("")
    assert png_bytes[:8] == PNG_SIGNATURE
    print("PASS  empty_string_does_not_raise")


def test_long_url_does_not_raise():
    long_url = "https://example.com/" + ("a" * 2000)
    png_bytes = generate_qr_png(long_url)
    assert png_bytes[:8] == PNG_SIGNATURE
    print("PASS  long_url_does_not_raise")


if __name__ == "__main__":
    tests = [
        test_output_is_valid_png,
        test_default_box_size_produces_reasonable_dimensions,
        test_larger_box_size_produces_larger_image,
        test_box_size_below_minimum_is_clamped_not_rejected,
        test_box_size_above_maximum_is_clamped_not_rejected,
        test_same_input_produces_identical_output,
        test_different_input_produces_different_output,
        test_quiet_zone_border_is_present,
        test_empty_string_does_not_raise,
        test_long_url_does_not_raise,
    ]
    for t in tests:
        t()
    print(f"\n{len(tests)}/{len(tests)} tests passed.")
