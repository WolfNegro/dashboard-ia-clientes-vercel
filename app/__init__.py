# app/__init__.py
from __future__ import annotations

import os
import json
import hmac
import hashlib
import logging
from typing import Any, Dict, List

from flask import (
    Flask,
    render_template,
    session,
    request,
    redirect,
    url_for,
    abort,
)

# -----------------------------------------------------------------------------
# Carga de clientes (para validar acceso a cuentas en modo clienta)
# -----------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.dirname(__file__))
CLIENTS_PATH = os.path.join(BASE_DIR, "clients.json")

try:
    with open(CLIENTS_PATH, "r", encoding="utf-8") as f:
        CLIENTS: Dict[str, Any] = json.load(f)
except Exception:
    logging.exception("No se pudo leer clients.json en __init__.py")
    CLIENTS = {}

# -----------------------------------------------------------------------------
# Helpers de seguridad (tokens de magic link)
# -----------------------------------------------------------------------------
def _expected_token(slug: str) -> str | None:
    """
    Si existe MAGIC_LINK_SECRET en el entorno, generamos un token HMAC estable:
      token = sha256(secret, slug)[:20]
    Si NO existe, devolvemos None (modo permisivo: acepta cualquier 'k' no vacío).
    """
    secret = os.getenv("MAGIC_LINK_SECRET", "").strip()
    if not secret:
        return None
    h = hmac.new(secret.encode("utf-8"), slug.encode("utf-8"), hashlib.sha256).hexdigest()
    return h[:20]


def _check_magic_token(slug: str, k: str | None) -> bool:
    """
    Valida el token del magic link.
    - Con MAGIC_LINK_SECRET: el token debe coincidir exactamente.
    - Sin MAGIC_LINK_SECRET: acepta cualquier token no vacío (útil para empezar rápido).
    """
    if not k:
        return False
    expected = _expected_token(slug)
    if expected is None:
        # Modo permisivo (sin secret configurado). Seguridad básica.
        logging.warning("MAGIC_LINK_SECRET no configurado: aceptando cualquier token no vacío para '%s'", slug)
        return True
    return hmac.compare_digest(expected, k.strip())


def _norm_act(x: str) -> str:
    return x if x.startswith("act_") else f"act_{x}"


# -----------------------------------------------------------------------------
# Factory
# -----------------------------------------------------------------------------
def create_app() -> Flask:
    app = Flask(__name__)  # usa /app/templates y /app/static

    # Clave de sesión (requerida para cookies seguras)
    app.secret_key = os.getenv("SECRET_KEY", "dev-secret-change-me")
    if app.secret_key == "dev-secret-change-me":
        logging.warning("SECRET_KEY no configurado. Configúralo en el entorno para producción.")

    # Registrar blueprint principal (rutas existentes)
    from .routes import bp as routes_bp
    app.register_blueprint(routes_bp)

    # -------------------- Contexto para templates (por si lo necesitas) --------------------
    @app.context_processor
    def inject_flags():
        return {
            "is_client_mode": session.get("mode") == "client",
            "client_slug": session.get("client_slug"),
        }

    # -------------------- Rutas de sesión: magic link / admin / logout --------------------
    @app.route("/s/<client_slug>")
    def magic_link(client_slug: str):
        """
        Link que se comparte a la clienta: /s/<slug>?k=<token>
        - Valida token
        - Activa 'modo clienta' en esta sesión
        - Redirige a /dashboard/<slug>
        """
        token = request.args.get("k")
        if client_slug not in CLIENTS:
            abort(404)

        if not _check_magic_token(client_slug, token):
            # Token inválido
            return render_template("error.html", code=403, message="Link inválido o expirado"), 403

        # Activar modo clienta en esta sesión
        session["mode"] = "client"
        session["client_slug"] = client_slug

        # Redirigir a su dashboard
        return redirect(url_for("routes.dashboard", client_id=client_slug))

    @app.route("/admin")
    def force_admin():
        """Fuerza modo admin (útil si abriste un magic link por accidente)."""
        session.pop("client_slug", None)
        session["mode"] = "admin"
        return redirect(url_for("routes.overview"))

    @app.route("/logout")
    def logout():
        """Limpia la sesión (sale de modo clienta)."""
        session.clear()
        return redirect(url_for("routes.overview"))

    # -------------------- Guardia de acceso (antes de cada request) --------------------
    @app.before_request
    def guard_client_mode():
        """
        Si la sesión está en 'modo clienta':
          - Bloquea /overview y /api/overview (redirige a su dashboard)
          - Solo permite /dashboard/<su_slug>
          - Bloquea intentos a /dashboard/<otro_slug>
          - En APIs:
              * permite /get_campaigns_active/<ad_account> solo si pertenece a su slug
              * permite /get_ads_by_campaign/<campaign_id>
              * bloquea otras /get_* por seguridad (compat)
        """
        # Permitir assets estáticos y favicon sin restricciones
        p = request.path or ""
        if p.startswith("/static") or p.startswith("/favicon"):
            return None

        # Si no está en modo clienta, no intervenir
        if session.get("mode") != "client":
            return None

        allowed_slug: str | None = session.get("client_slug")
        if not allowed_slug:
            # Sesión inconsistente: salir a admin
            session.clear()
            return redirect(url_for("routes.overview"))

        # 1) Bloquear overview (HTML + API) en modo clienta
        if p == "/" or p.startswith("/overview") or p.startswith("/api/overview"):
            return redirect(url_for("routes.dashboard", client_id=allowed_slug))

        # 2) Bloquear dashboards de otras clientas
        if p.startswith("/dashboard/"):
            parts = p.strip("/").split("/", 1)  # ['dashboard', '<slug>']
            if len(parts) >= 2:
                slug = parts[1]
                if slug != allowed_slug:
                    return redirect(url_for("routes.dashboard", client_id=allowed_slug))

        # 3) Proteger APIs
        if p.startswith("/get_"):
            # Permitimos explícitamente:
            #   - /get_campaigns_active/<ad_account_id>  (solo si pertenece a su slug)
            #   - /get_ads_by_campaign/<campaign_id>     (no validamos campaña -> flujo natural desde su dashboard)
            if p.startswith("/get_campaigns_active/"):
                ad_account = p.rsplit("/", 1)[-1]
                allowed_accounts: List[str] = (CLIENTS.get(allowed_slug, {}) or {}).get("ad_account_ids", []) or []
                allowed_norm = {_norm_act(a) for a in allowed_accounts}
                if _norm_act(ad_account) not in allowed_norm:
                    abort(403)
                return None  # OK
            if p.startswith("/get_ads_by_campaign/"):
                return None  # OK

            # El resto de endpoints /get_* quedan bloqueados en modo clienta
            abort(403)

        # Para cualquier otra ruta, continuar
        return None

    # -------------------- Errores --------------------
    @app.errorhandler(403)
    def _403(_e):
        try:
            return render_template("error.html", code=403, message="Acceso restringido"), 403
        except Exception:
            return ("Acceso restringido", 403)

    @app.errorhandler(500)
    def _500(_e):
        return render_template("error.html", code=500, message="Error interno"), 500

    return app
