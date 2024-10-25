# app/routes/__init__.py

from .main import main_bp
from .search_routes.PnP.pnp_search import pnp_bp

from ..utils.workflow import undo_bp  # Import undo blueprint

def register_blueprints(app):
    app.register_blueprint(main_bp)
    app.register_blueprint(pnp_bp)
    app.register_blueprint(undo_bp)
    # Register additional search blueprints here
