import os


def _build_database_uri():
    """Return the database URI, preferring DATABASE_URL when present."""
    database_url = os.environ.get("DATABASE_URL")

    if database_url:
        # Railway / production
        return database_url.replace(
            "postgres://",
            "postgresql+psycopg2://",
            1
        ).replace(
            "postgresql://",
            "postgresql+psycopg2://",
            1
        )

    # Local development / Docker
    postgres_user = os.environ.get("POSTGRES_USER", "shortener")
    postgres_password = os.environ.get("POSTGRES_PASSWORD", "shortener")
    postgres_host = os.environ.get("POSTGRES_HOST", "db")
    postgres_port = os.environ.get("POSTGRES_PORT", "5432")
    postgres_db = os.environ.get("POSTGRES_DB", "shortener_db")

    return (
        f"postgresql+psycopg2://{postgres_user}:{postgres_password}"
        f"@{postgres_host}:{postgres_port}/{postgres_db}"
    )


class Config:
    # Core 
    SECRET_KEY = os.environ.get("SECRET_KEY", "change-me-in-production")
    DEBUG = os.environ.get("FLASK_DEBUG", "0") == "1"

    # Database
    DATABASE_URL = os.environ.get("DATABASE_URL")
    SQLALCHEMY_DATABASE_URI = _build_database_uri()
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Rate Limiter
    RATE_LIMIT_MAX_REQUESTS = int(os.environ.get("RATE_LIMIT_MAX_REQUESTS", 5))
    RATE_LIMIT_WINDOW_SECONDS = int(os.environ.get("RATE_LIMIT_WINDOW_SECONDS", 60))

    # CORS 
    FRONTEND_ORIGIN = os.environ.get("FRONTEND_ORIGIN", "http://localhost:5173")

    PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "").rstrip("/")

    # API docs (flask-smorest / OpenAPI)
    API_TITLE = "Snip API"
    API_VERSION = "v1"
    OPENAPI_VERSION = "3.0.3"
    OPENAPI_URL_PREFIX = "/api/docs"
    OPENAPI_JSON_PATH = "/openapi.json"
    OPENAPI_SWAGGER_UI_PATH = "/"
    OPENAPI_SWAGGER_UI_URL = "https://cdn.jsdelivr.net/npm/swagger-ui-dist/"
    OPENAPI_REDOC_PATH = "/redoc"
    OPENAPI_REDOC_URL = "https://cdn.jsdelivr.net/npm/redoc@next/bundles/redoc.standalone.js"