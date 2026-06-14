from flask import Blueprint

urls_bp = Blueprint("urls", __name__)

# POST /api/shorten
# GET  /<alias>          → redirect + click tracking
# GET  /api/urls         → list all shortened URLs
# GET  /api/urls/<alias>/analytics  → 7-day click time-series
