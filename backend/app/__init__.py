import logging

from flask import Flask
from flask_cors import CORS

from app.config import Config
from app.extensions import db, migrate

logger = logging.getLogger(__name__)


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Extensions 
    db.init_app(app)
    migrate.init_app(app, db)

    # CORS 
    CORS(
        app,
        resources={r"/api/*": {"origins": app.config["FRONTEND_ORIGIN"]}},
        supports_credentials=False,
    )

    # Models 
    from app.models import url

    # Blueprints
    from app.routes.urls import urls_bp
    app.register_blueprint(urls_bp)

    logger.info("App created — DB: %s", app.config.get("SQLALCHEMY_DATABASE_URI", "n/a"))
    return app