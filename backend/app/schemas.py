"""
Marshmallow schemas — used ONLY for OpenAPI/Swagger documentation.

Design decision: routes keep returning plain jsonify(...) dicts exactly as before (see app/routes/urls.py). These schemas are attached via @blp.response(...) purely so flask-smorest can generate accurate request/ response docs at /api/docs. They are intentionally *not* used as the serializer (no schema.dump()) and request schemas are *not* enforced via @blp.arguments, so existing validation/error-handling logic and response shapes are completely unchanged — this is a docs-only addition.
"""

from marshmallow import Schema, fields


class ErrorSchema(Schema):
    error = fields.String(required=True, metadata={"description": "Human-readable error message."})


class ShortenRequestSchema(Schema):
    url = fields.String(
        required=True,
        metadata={"description": "The long URL to shorten.", "example": "https://example.com/some/very/long/path"},
    )
    custom_alias = fields.String(
        required=False,
        metadata={"description": "Optional custom alias instead of a random one.", "example": "my-link"},
    )
    expires_at = fields.String(
        required=False,
        metadata={"description": "Optional ISO-8601 expiry timestamp, or a relative shorthand.", "example": "2026-12-31T00:00:00Z"},
    )


class ShortenResponseSchema(Schema):
    alias = fields.String(required=True)
    short_url = fields.String(required=True)
    original_url = fields.String(required=True)
    expires_at = fields.String(required=True, allow_none=True)
    qr_code_url = fields.String(required=True)


class UrlItemSchema(Schema):
    id = fields.Integer(required=True)
    alias = fields.String(required=True)
    original_url = fields.String(required=True)
    short_url = fields.String(required=True)
    created_at = fields.String(required=True)
    total_clicks = fields.Integer(required=True)
    qr_code_url = fields.String(required=True)


class UrlListResponseSchema(Schema):
    urls = fields.List(fields.Nested(UrlItemSchema), required=True)


class DailyClickSchema(Schema):
    date = fields.String(required=True)
    clicks = fields.Integer(required=True)


class DeviceBreakdownSchema(Schema):
    device_type = fields.String(required=True)
    clicks = fields.Integer(required=True)


class BrowserBreakdownSchema(Schema):
    browser = fields.String(required=True)
    clicks = fields.Integer(required=True)


class OSBreakdownSchema(Schema):
    os = fields.String(required=True)
    clicks = fields.Integer(required=True)


class CountryBreakdownSchema(Schema):
    country = fields.String(required=True, allow_none=True)
    country_code = fields.String(required=True, allow_none=True)
    clicks = fields.Integer(required=True)


class ReferrerBreakdownSchema(Schema):
    referrer = fields.String(required=True, allow_none=True)
    clicks = fields.Integer(required=True)


class AnalyticsResponseSchema(Schema):
    alias = fields.String(required=True)
    original_url = fields.String(required=True)
    short_url = fields.String(required=True)
    total_clicks = fields.Integer(required=True)
    analytics = fields.List(fields.Nested(DailyClickSchema), required=True)
    devices = fields.List(fields.Nested(DeviceBreakdownSchema), required=True)
    browsers = fields.List(fields.Nested(BrowserBreakdownSchema), required=True)
    operating_systems = fields.List(fields.Nested(OSBreakdownSchema), required=True)
    countries = fields.List(fields.Nested(CountryBreakdownSchema), required=True)
    top_referrers = fields.List(fields.Nested(ReferrerBreakdownSchema), required=True)


class QRJsonResponseSchema(Schema):
    alias = fields.String(required=True)
    short_url = fields.String(required=True)
    qr_code = fields.String(required=True, metadata={"description": "data:image/png;base64,... URI"})
    is_expired = fields.Boolean(required=True)


class HealthResponseSchema(Schema):
    status = fields.String(required=True)
    db = fields.String(required=True)


class RateLimitedResponseSchema(Schema):
    error = fields.String(required=True)
    retry_after_seconds = fields.Integer(required=True)
    message = fields.String(required=True)