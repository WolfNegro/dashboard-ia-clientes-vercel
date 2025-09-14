from flask import Flask, render_template
from .routes import bp as routes_bp

def create_app():
    app = Flask(__name__)  # usa /app/templates y /app/static

    # rutas de la app
    app.register_blueprint(routes_bp)

    @app.errorhandler(500)
    def _500(e):
        return render_template("error.html", code=500, message="Error interno"), 500

    return app
