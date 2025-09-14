from flask import Flask, render_template, redirect, request, session
import os

# Mapa de slugs válidos (ajusta si cambian)
SLUGS_VALIDOS = {
    "clinic_prime": "Clinic Prime",
    "dra_pia": "Dra Pia",
    "harmony": "Harmony",
    "mc_dent": "Mc Dent",
    "amaru": "Amaru",
    "dra_claudia": "Dra Claudia",
}

def create_app():
    app = Flask(__name__)  # usa /app/templates y /app/static
    app.secret_key = os.environ.get("SECRET_KEY", "dev-secret")

    # Claves simples para activar modo clienta / admin
    app.config["MAGIC_KEY"] = os.environ.get("MAGIC_KEY", "ok")
    app.config["ADMIN_KEY"] = os.environ.get("ADMIN_KEY", "admin")

    # ---- Guardas de navegación (helpers) -----------------
    def set_modo_clienta(slug: str):
        session["client_slug"] = slug

    def clear_modo_clienta():
        session.pop("client_slug", None)

    def slug_valido(slug: str) -> bool:
        return slug in SLUGS_VALIDOS

    # ---- Magic link por clienta ---------------------------
    @app.route("/s/<slug>")
    def magic_link(slug):
        k = request.args.get("k", "")
        if k != app.config["MAGIC_KEY"]:
            # 403 explícito
            return render_template("error.html", code=403, message="Acceso no autorizado"), 403
        if not slug_valido(slug):
            return render_template("error.html", code=404, message="Clienta no encontrada"), 404

        # Activa modo clienta y redirige sin url_for (evita fallo por nombre de endpoint)
        set_modo_clienta(slug)
        return redirect(f"/dashboard/{slug}")

    # ---- Admin link (opcional) ----------------------------
    @app.route("/admin")
    def admin_link():
        k = request.args.get("k", "")
        if k != app.config["ADMIN_KEY"]:
            return render_template("error.html", code=403, message="Acceso no autorizado"), 403
        clear_modo_clienta()
        return redirect("/overview")

    # ---- Logout: limpia modo clienta ----------------------
    @app.route("/logout")
    def logout():
        clear_modo_clienta()
        return redirect("/overview")

    # ---- Blueprints principales ---------------------------
    from .routes import bp as routes_bp
    app.register_blueprint(routes_bp)

    # ---- Errores amigables -------------------------------
    @app.errorhandler(404)
    def _404(e):
        return render_template("error.html", code=404, message="Página no encontrada"), 404

    @app.errorhandler(500)
    def _500(e):
        return render_template("error.html", code=500, message="Error interno"), 500

    return app
