# app/client_routes.py
# Shim para evitar import circular. NO importa 'app' aquí.
# Solo expone el blueprint y una función opcional de registro.

from app.blueprints.client_slug import client_bp

def init_app(app):
    """Registrar el blueprint si aún no está registrado (opcional)."""
    if "client_bp" not in app.blueprints:
        app.register_blueprint(client_bp)
