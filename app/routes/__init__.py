# app/routes/__init__.py

from .main import main_bp
from .search_routes.PnP.pnp_search import pnp_bp
from .search_routes.Checkers.checkers_search import checkers_bp  # Import Checkers blueprint
from ..utils.workflow import undo_bp  # Import undo blueprint






def register_blueprints(app):
    app.register_blueprint(main_bp)
    app.register_blueprint(pnp_bp)
    app.register_blueprint(checkers_bp)  # Register Checkers blueprint
    app.register_blueprint(undo_bp)
