# app/api/index.py
# Entry para Vercel cuando el Root Directory es "app/"
import importlib

app = None

# A) intentar obtener la app expuesta en app/__init__.py
try:
    pkg = importlib.import_module("app")
    if hasattr(pkg, "app"):
        app = pkg.app
except Exception:
    app = None

# B) intentar run.py
if app is None:
    try:
        app = importlib.import_module("run").app
    except Exception:
        app = None

# C) factory create_app()
if app is None:
    try:
        pkg = importlib.import_module("app")
        if hasattr(pkg, "create_app"):
            app = pkg.create_app()
    except Exception:
        app = None

if app is None:
    raise RuntimeError("No se pudo obtener la instancia Flask ('app') ni un 'create_app()' válido.")

# Registrar el blueprint /s/<slug> (no interfiere con rutas existentes)
from app.blueprints.client_slug import client_bp
if "client_bp" not in app.blueprints:
    app.register_blueprint(client_bp)

# Alias
application = app
