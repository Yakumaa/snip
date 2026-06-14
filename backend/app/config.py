import os

class Config:
    # Core 
    SECRET_KEY = os.environ.get("SECRET_KEY", "change-me-in-production")
    DEBUG = os.environ.get("FLASK_DEBUG", "0") == "1"

    # Database 
    POSTGRES_USER = os.environ.get("POSTGRES_USER", "shortener")
    POSTGRES_PASSWORD = os.environ.get("POSTGRES_PASSWORD", "shortener")
    POSTGRES_HOST = os.environ.get("POSTGRES_HOST", "db")
    POSTGRES_PORT = os.environ.get("POSTGRES_PORT", "5432")
    POSTGRES_DB = os.environ.get("POSTGRES_DB", "shortener_db")

    SQLALCHEMY_DATABASE_URI = (
        f"postgresql+psycopg2://{POSTGRES_USER}:{POSTGRES_PASSWORD}"
        f"@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Rate Limiter
    RATE_LIMIT_MAX_REQUESTS = int(os.environ.get("RATE_LIMIT_MAX_REQUESTS", 5))
    RATE_LIMIT_WINDOW_SECONDS = int(os.environ.get("RATE_LIMIT_WINDOW_SECONDS", 60))

    # CORS 
    FRONTEND_ORIGIN = os.environ.get("FRONTEND_ORIGIN", "http://localhost:5173")
