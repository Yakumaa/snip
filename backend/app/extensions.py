import os

from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
import redis

db = SQLAlchemy()
migrate = Migrate()

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True)