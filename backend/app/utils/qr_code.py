"""
QR Code Generation
-------------------
Turns a short link's target URL into a scannable QR code PNG.

Kept as a small pure function (text in, PNG bytes out) rather than folded into the route — it needs no Flask request context or database access, so it's trivially unit-testable and reusable if another part of the app ever wants a QR code (e.g. a future "download all QR codes" bulk
export).
"""

import io

import qrcode
from qrcode.constants import ERROR_CORRECT_M

MIN_BOX_SIZE = 1
MAX_BOX_SIZE = 40
DEFAULT_BOX_SIZE = 10

# The "quiet zone" — blank margin around the QR modules — is part of the spec, not decoration: scanners use it to find the code's edges, and a too-small border is a common cause of "the QR code doesn't scan" complaints. Fixed rather than exposed as a query parameter so a caller can't accidentally (or deliberately) request an unscannable code.
QUIET_ZONE_BORDER = 4


def generate_qr_png(data: str, box_size: int = DEFAULT_BOX_SIZE) -> bytes:
    """
    Render *data* (typically a short URL) as a PNG QR code.

    box_size is the pixel size of each QR "module" (the small squares the code is made of) — bigger box_size means a larger overall image at the same information density. It's silently clamped to [MIN_BOX_SIZE, MAX_BOX_SIZE] rather than raising on an out-of-range value: this is fed from a caller-supplied query parameter, and the
    worst a bad value should do is produce a small or large-but-bounded image, not a 500 or an unbounded memory allocation.

    Returns raw PNG bytes (not base64-encoded — callers that need a data URI wrap this themselves).
    """
    box_size = max(MIN_BOX_SIZE, min(box_size, MAX_BOX_SIZE))

    qr = qrcode.QRCode(
        error_correction=ERROR_CORRECT_M,
        box_size=box_size,
        border=QUIET_ZONE_BORDER,
    )
    qr.add_data(data)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
