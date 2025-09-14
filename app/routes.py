# app/routes.py
from __future__ import annotations

import os
import json
import math
import logging
from typing import Dict, Any, List, Optional

import requests
from flask import Flask, jsonify, render_template, request, abort, redirect, url_for

# ---------------------------------------------------------------------
# Config básica y carga de clients.json con RUTA ABSOLUTA (serverless safe)
# ---------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.dirname(__file__))
CLIENTS_PATH = os.path.join(BASE_DIR, "clients.json")

try:
    with open(CLIENTS_PATH, "r", encoding="utf-8") as f:
        CLIENTS: Dict[str, Any] = json.load(f)
except Exception as e:
    # En serverless NO debemos romper la app si falta el archivo
    logging.exception("No se pudo leer clients.json")
    CLIENTS = {}

GRAPH_VERSION = os.getenv("FB_GRAPH_VERSION", "v21.0")
GRAPH_URL = f"https://graph.facebook.com/{GRAPH_VERSION}"

ACCESS_TOKEN = os.getenv("ACCESS_TOKEN", "").strip()
if not ACCESS_TOKEN:
    logging.warning("ENV ACCESS_TOKEN vacío. Configúralo en Vercel > Settings > Environment Variables.")

# ---------------------------------------------------------------------
# Helpers Facebook API
# ---------------------------------------------------------------------
def fb_get(path: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """GET a Graph API con manejo de errores y token inyectado."""
    url = f"{GRAPH_URL}/{path.lstrip('/')}"
    merged = {"access_token": ACCESS_TOKEN}
    merged.update(params or {})
    try:
        r = requests.get(url, params=merged, timeout=35)
        r.raise_for_status()
        return r.json()
    except requests.HTTPError as he:
        try:
            j = r.json()
            err = j.get("error", {})
            logging.error(
                "[Facebook API] %s %s -> type=%s code=%s subcode=%s message=%s",
                r.request.method,
                r.url,
                err.get("type"),
                err.get("code"),
                err.get("error_subcode"),
                err.get("message"),
            )
        except Exception:
            logging.exception("[Facebook API] Error no parseable en %s", url)
        # devolvemos forma homogénea para que el front no se caiga
        return {"data": [], "error": True}
    except Exception:
        logging.exception("[Facebook API] Error de red en %s", url)
        return {"data": [], "error": True}


def fb_paginate_first_level(path: str, params: Dict[str, Any], limit: int = 500) -> List[Dict[str, Any]]:
    """Paginado simple nivel 1 (Graph API) hasta `limit` elementos aprox."""
    out: List[Dict[str, Any]] = []
    page_url = None
    page_params = params.copy()

    while True:
        if page_url:
            resp = requests.get(page_url, timeout=35)
            try:
                resp.raise_for_status()
                j = resp.json()
            except Exception:
                break
        else:
            j = fb_get(path, page_params)

        data = j.get("data", []) or []
        out.extend(data)
        if len(out) >= limit:
            break

        paging = j.get("paging", {}) or {}
        next_url = paging.get("next")
        if not next_url:
            break
        page_url = next_url

    return out


def sum_messages_from_actions(actions: Optional[List[Dict[str, Any]]]) -> float:
    """
    Suma 'mensajes iniciados' desde el arreglo actions.
    Cubrimos variantes que Facebook expone según cuenta/columna:
      - onsite_conversion.messaging_conversation_started_7d
      - onsite_conversion.messaging_conversation_started
    """
    if not actions:
        return 0.0
    wanted = {
        "onsite_conversion.messaging_conversation_started_7d",
        "onsite_conversion.messaging_conversation_started",
    }
    total = 0.0
    for a in actions:
        atype = a.get("action_type")
        if atype in wanted:
            try:
                total += float(a.get("value", 0) or 0)
            except Exception:
                pass
    return total


def fmt_currency(amount: float) -> float:
    try:
        return round(float(amount), 2)
    except Exception:
        return 0.0


# ---------------------------------------------------------------------
# Factory (Vercel requiere create_app)
# ---------------------------------------------------------------------
def create_app() -> Flask:
    app = Flask(__name__, static_folder="static", template_folder="templates")

    # --------------------------------------------------------------
    # Vistas HTML
    # --------------------------------------------------------------
    @app.route("/")
    def root():
        return redirect(url_for("overview"))

    @app.route("/overview")
    def overview():
        # Se inyecta CLIENTS en la plantilla para que el front liste las clientas
        return render_template("overview.html", clients=CLIENTS)

    @app.route("/dashboard/<client_id>")
    def dashboard(client_id: str):
        if client_id not in CLIENTS:
            abort(404)
        client_info = CLIENTS[client_id]
        return render_template("index.html", client_id=client_id, client_name=client_info.get("client_name", client_id))

    # --------------------------------------------------------------
    # API: campañas/adsets/anuncios/insights (lo que consume tu JS)
    # --------------------------------------------------------------
    @app.route("/get_campaigns/<ad_account_id>")
    def get_campaigns(ad_account_id: str):
        """
        Devuelve campañas ACTIVAS del ad account.
        El front espera ['id','name','status','effective_status','objective'].
        """
        account = ad_account_id
        if not account.startswith("act_"):
            account = f"act_{account}"

        fields = "id,name,status,effective_status,objective,updated_time"
        data = fb_paginate_first_level(f"{account}/campaigns", {"fields": fields, "limit": 200})

        # Filtrar a 'activas' (effective_status de familia ACTIVE)
        active_prefix = ("ACTIVE", "PAUSED", "IN_PROCESS", "LIMITED")
        only_active = [c for c in data if str(c.get("effective_status", "")).upper().startswith(active_prefix)]
        # Si quieres SOLO activas (no pausadas), cambia a beginswith "ACTIVE" y listo.
        return jsonify({"data": only_active})

    @app.route("/get_adsets/<campaign_id>")
    def get_adsets(campaign_id: str):
        fields = "id,name,status,effective_status,daily_budget,lifetime_budget"
        data = fb_paginate_first_level(f"{campaign_id}/adsets", {"fields": fields, "limit": 200})
        return jsonify({"data": data})

    @app.route("/get_ads/<adset_id>")
    def get_ads(adset_id: str):
        # Intentamos entregar miniaturas si existen
        fields = "id,name,adset_id,creative{thumbnail_url,asset_feed_spec},status,effective_status"
        data = fb_paginate_first_level(f"{adset_id}/ads", {"fields": fields, "limit": 200})
        # Normaliza miniatura en la raíz para facilidad del front
        out = []
        for ad in data:
            thumb = None
            creative = ad.get("creative") or {}
            if isinstance(creative, dict):
                thumb = creative.get("thumbnail_url")
            ad["thumbnail_url"] = thumb
            out.append(ad)
        return jsonify({"data": out})

    @app.route("/get_insights/campaign/<campaign_id>")
    def get_insights_campaign(campaign_id: str):
        """
        Insights de campaña. El front pasa:
          - date_preset=this_month|today|yesterday|last_7d...
          - time_increment=1 (opcional, para serie diaria)
        Devolvemos spend, results (mensajes) y cpr calculado por día o total.
        """
        date_preset = request.args.get("date_preset", "this_month")
        time_increment = request.args.get("time_increment")

        fields = "date_start,date_stop,spend,actions,objective"
        params = {
            "fields": fields,
            "date_preset": date_preset,
            # Ajustes de atribución típicos de columnas de mensajes
            "action_report_time": "impression",
            "action_attribution_windows": '["7d_click","1d_view"]',
            "limit": 500,
        }
        if time_increment:
            params["time_increment"] = time_increment

        j = fb_get(f"{campaign_id}/insights", params)
        rows = j.get("data", []) or []

        out_rows = []
        total_spend = 0.0
        total_msgs = 0.0

        for r in rows:
            spend = fmt_currency(r.get("spend", 0) or 0)
            msgs = sum_messages_from_actions(r.get("actions"))
            cpr = fmt_currency(spend / msgs) if msgs > 0 else 0.0
            total_spend += spend
            total_msgs += msgs
            out_rows.append(
                {
                    "date_start": r.get("date_start"),
                    "date_stop": r.get("date_stop"),
                    "spend": spend,
                    "results": msgs,
                    "cpr": cpr,
                }
            )

        summary = {
            "spend": fmt_currency(total_spend),
            "results": float(total_msgs),
            "cpr": fmt_currency(total_spend / total_msgs) if total_msgs > 0 else 0.0,
        }
        return jsonify({"data": out_rows, "summary": summary})

    @app.route("/api/overview")
    def api_overview():
        """
        Agregado por CLIENTA para Vista General.
        Query: ?date_preset=today|yesterday|this_month|last_7d...
        Respuesta: [{client_id, client_name, spend, results, cpr}]
        """
        date_preset = request.args.get("date_preset", "today")
        # Campos mínimos para sacar gasto y mensajes a nivel de cuenta
        fields = "date_start,date_stop,spend,actions"

        items = []
        for client_id, info in CLIENTS.items():
            ad_accounts: List[str] = info.get("ad_account_ids", []) or []
            total_spend = 0.0
            total_msgs = 0.0

            for acc in ad_accounts:
                account = acc if acc.startswith("act_") else f"act_{acc}"
                params = {
                    "fields": fields,
                    "date_preset": date_preset,
                    "action_report_time": "impression",
                    "action_attribution_windows": '["7d_click","1d_view"]',
                    "limit": 50,
                }
                j = fb_get(f"{account}/insights", params)
                for r in (j.get("data", []) or []):
                    spend = fmt_currency(r.get("spend", 0) or 0)
                    msgs = sum_messages_from_actions(r.get("actions"))
                    total_spend += spend
                    total_msgs += msgs

            cpr = fmt_currency(total_spend / total_msgs) if total_msgs > 0 else 0.0
            items.append(
                {
                    "client_id": client_id,
                    "client_name": info.get("client_name", client_id),
                    "spend": fmt_currency(total_spend),
                    "results": float(total_msgs),
                    "cpr": cpr,
                }
            )

        return jsonify({"data": items})

    # --------------------------------------------------------------
    # Manejo de errores simple (puedes personalizar tus templates)
    # --------------------------------------------------------------
    @app.errorhandler(404)
    def _404(_e):
        try:
            return render_template("error.html", code=404, message="Recurso no encontrado"), 404
        except Exception:
            return jsonify({"error": "not_found"}), 404

    @app.errorhandler(500)
    def _500(_e):
        logging.exception("Error 500")
        try:
            return render_template("error.html", code=500, message="Error interno"), 500
        except Exception:
            return jsonify({"error": "internal_error"}), 500

    return app


# Soporte para ejecución local: `python run.py` suele crear app en otro archivo,
# pero si quieres poder ejecutar este módulo directamente, descomenta:
# if __name__ == "__main__":
#     app = create_app()
#     app.run(host="0.0.0.0", port=5000, debug=True)
