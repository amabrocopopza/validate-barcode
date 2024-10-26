# app/routes/__init__.py

from .main import main_bp
from .search_routes.PnP.pnp_search import pnp_bp
from .search_routes.Checkers.checkers_search import checkers_bp
from .search_routes.deeliver_route import deeliver_bp
from ..utils.workflow import undo_bp

def register_blueprints(app):
    app.register_blueprint(main_bp)
    app.register_blueprint(pnp_bp)
    app.register_blueprint(checkers_bp)
    app.register_blueprint(deeliver_bp)
    app.register_blueprint(undo_bp)
