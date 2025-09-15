# api/index.py
# Entry robusto para Vercel: obtiene la Flask app sin ciclos y registra el blueprint /s/<slug>

import importlib

app = None

# 1) Intento estándar: app/__init__.py expone 'app'
try:
    app = importlib.import_module("app").app  # from app import app
except Exception:
    app = None

# 2) Si no existe, intenta run.py con 'app'
if app is None:
    try:
        app = importlib.import_module("run").app  # from run import app
    except Exception:
        app = None

# 3) Si el proyecto usa factory
if app is None:
    try:
        pkg = importlib.import_module("app")
        if hasattr(pkg, "create_app"):
            app = pkg.create_app()
    except Exception:
        app = None

if app is None:
    raise RuntimeError("No se pudo obtener la instancia Flask ('app') ni un 'create_app()' válido.")

# Registrar el blueprint de /s/<slug> (no interfiere con rutas existentes)
from app.blueprints.client_slug import client_bp
if "client_bp" not in app.blueprints:
    app.register_blueprint(client_bp)

# Alias para algunos runtimes
application = app
