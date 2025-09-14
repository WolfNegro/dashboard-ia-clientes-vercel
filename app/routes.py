# app/routes.py
from __future__ import annotations

import os
import json
import logging
from typing import Any, Dict, List, Optional

import requests
from flask import Blueprint, jsonify, render_template, request, abort

# -----------------------------------------------------------------------------
# Config & data
# -----------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.dirname(__file__))
CLIENTS_PATH = os.path.join(BASE_DIR, "clients.json")

try:
    with open(CLIENTS_PATH, "r", encoding="utf-8") as f:
        CLIENTS: Dict[str, Any] = json.load(f)
except Exception:
    logging.exception("No se pudo leer clients.json")
    CLIENTS = {}

GRAPH_VERSION = os.getenv("FB_GRAPH_VERSION", "v21.0").strip()
GRAPH_URL = f"https://graph.facebook.com/{GRAPH_VERSION}"
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN", "").strip()
if not ACCESS_TOKEN:
    logging.warning("ACCESS_TOKEN vacío. Configúralo en tu entorno/Vercel.")

# Blueprint que espera tu app (__init__.py importa 'bp')
bp = Blueprint("routes", __name__)

# Consideramos ACTIVAS solo estas (excluimos PAUSED)
ACTIVE_STATUSES = ("ACTIVE", "IN_PROCESS", "LIMITED")


# -----------------------------------------------------------------------------
# Helpers Facebook API
# -----------------------------------------------------------------------------
def fb_get(path: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """GET Graph API con manejo de errores."""
    url = f"{GRAPH_URL}/{path.lstrip('/')}"
    merged = {"access_token": ACCESS_TOKEN}
    merged.update(params or {})
    try:
        r = requests.get(url, params=merged, timeout=35)
        r.raise_for_status()
        return r.json()
    except requests.HTTPError:
        try:
            j = r.json()
            err = (j or {}).get("error", {})
            logging.error(
                "[FB] %s -> type=%s code=%s sub=%s msg=%s",
                r.url,
                err.get("type"),
                err.get("code"),
                err.get("error_subcode"),
                err.get("message"),
            )
        except Exception:
            logging.exception("[FB] Error no parseable en %s", url)
        return {"data": [], "error": True}
    except Exception:
        logging.exception("[FB] Error de red en %s", url)
        return {"data": [], "error": True}


def fb_paginate_first_level(path: str, params: Dict[str, Any], limit: int = 500) -> List[Dict[str, Any]]:
    """Paginado simple (primer nivel)."""
    out: List[Dict[str, Any]] = []
    next_url: Optional[str] = None
    while True:
        if next_url:
            try:
                r = requests.get(next_url, timeout=35)
                r.raise_for_status()
                j = r.json()
            except Exception:
                break
        else:
            j = fb_get(path, params)

        data = j.get("data", []) or []
        out.extend(data)
        if len(out) >= limit:
            break
        next_url = (j.get("paging") or {}).get("next")
        if not next_url:
            break
    return out


def sum_messages_from_actions(actions: Optional[List[Dict[str, Any]]]) -> float:
    """Suma 'mensajes iniciados' (cubre variantes)."""
    if not actions:
        return 0.0
    keys = {
        "onsite_conversion.messaging_conversation_started_7d",
        "onsite_conversion.messaging_conversation_started",
    }
    total = 0.0
    for a in actions:
        if a.get("action_type") in keys:
            try:
                total += float(a.get("value", 0) or 0)
            except Exception:
                pass
    return total


def f2(v: Any) -> float:
    try:
        return round(float(v or 0), 2)
    except Exception:
        return 0.0


def build_date_params() -> Dict[str, Any]:
    """
    Soporta: ?date_preset=hoy|ayer|7d|mes_actual|mes_pasado|rango
    Si 'rango', usar ?since=YYYY-MM-DD&until=YYYY-MM-DD
    """
    label = (request.args.get("date_preset") or "hoy").lower()
    preset_map = {
        "hoy": "today",
        "ayer": "yesterday",
        "7d": "last_7d",
        "mes_actual": "this_month",
        "mes_pasado": "last_month",
    }
    params: Dict[str, Any] = {
        "action_report_time": "impression",
        "action_attribution_windows": '["7d_click","1d_view"]',
        "limit": 1000,
    }
    if label == "rango":
        since = (request.args.get("since") or "").strip()
        until = (request.args.get("until") or "").strip()
        if since and until:
            params["time_range"] = json.dumps({"since": since, "until": until})
        else:
            params["date_preset"] = "today"  # default
    else:
        params["date_preset"] = preset_map.get(label, "today")
    return params


# -----------------------------------------------------------------------------
# Vistas HTML
# -----------------------------------------------------------------------------
@bp.route("/")
def root():
    return render_template("overview.html", clients=CLIENTS)

@bp.route("/overview")
def overview():
    return render_template("overview.html", clients=CLIENTS)

@bp.route("/dashboard/<client_id>")
def dashboard(client_id: str):
    if client_id not in CLIENTS:
        abort(404)
    info = CLIENTS[client_id]
    return render_template(
        "index.html",
        client_id=client_id,
        client_name=info.get("client_name", client_id),
        ad_account_ids=info.get("ad_account_ids", []) or [],
    )


# -----------------------------------------------------------------------------
# API: Overview (agregado por clienta)
# -----------------------------------------------------------------------------
@bp.route("/api/overview")
def api_overview():
    items: List[Dict[str, Any]] = []
    for cid, info in CLIENTS.items():
        total_spend = 0.0
        total_msgs = 0.0
        for acc in (info.get("ad_account_ids") or []):
            account = acc if str(acc).startswith("act_") else f"act_{acc}"
            j = fb_get(
                f"{account}/insights",
                {"fields": "spend,actions", **build_date_params()},
            )
            for r in (j.get("data") or []):
                total_spend += f2(r.get("spend"))
                total_msgs += sum_messages_from_actions(r.get("actions"))
        cpr = f2(total_spend / total_msgs) if total_msgs > 0 else 0.0
        items.append(
            {
                "client_id": cid,
                "client_name": info.get("client_name", cid),
                "spend": f2(total_spend),
                "results": float(total_msgs),
                "cpr": cpr,
            }
        )
    return jsonify({"data": items})


# -----------------------------------------------------------------------------
# API rápida: campañas ACTIVAS con gasto > 0 (una sola llamada a insights)
# -----------------------------------------------------------------------------
@bp.route("/get_campaigns_active/<ad_account_id>")
def get_campaigns_active(ad_account_id: str):
    """
    Devuelve SOLO campañas ACTIVAS con gasto > 0 en el rango.
    Usa /act_xxx/insights?level=campaign para velocidad.
    """
    account = ad_account_id if ad_account_id.startswith("act_") else f"act_{ad_account_id}"

    # 1) Traer mapa id->status/name (para filtrar activas)
    camps = fb_paginate_first_level(
        f"{account}/campaigns",
        {"fields": "id,name,effective_status", "limit": 500},
    )
    status_map = {c["id"]: str(c.get("effective_status", "")).upper() for c in camps}
    name_map = {c["id"]: c.get("name") for c in camps}

    # 2) Métricas por campaña en UNA llamada
    params = {"level": "campaign", "fields": "campaign_id,campaign_name,spend,actions", **build_date_params()}
    ins = fb_get(f"{account}/insights", params)

    out: List[Dict[str, Any]] = []
    for row in (ins.get("data") or []):
        cid = row.get("campaign_id")
        spend = f2(row.get("spend"))
        msgs = sum_messages_from_actions(row.get("actions"))
        if not cid or spend <= 0:
            continue  # gasto 0 => no mostrar
        if status_map.get(cid, "") and not status_map[cid].startswith(ACTIVE_STATUSES):
            continue  # no activa => no mostrar
        cpr = f2(spend / msgs) if msgs > 0 else 0.0
        out.append(
            {
                "id": cid,
                "name": name_map.get(cid) or row.get("campaign_name") or cid,
                "spend": spend,
                "results": float(msgs),
                "cpr": cpr,
            }
        )

    out.sort(key=lambda x: x.get("spend", 0), reverse=True)
    return jsonify({"data": out})


# -----------------------------------------------------------------------------
# API rápida: miniaturas (ads) con gasto > 0 de una campaña
# -----------------------------------------------------------------------------
@bp.route("/get_ads_by_campaign/<campaign_id>")
def get_ads_by_campaign(campaign_id: str):
    """
    Devuelve SOLO anuncios con gasto > 0 del rango.
    Une:
      - /campaign_id/ads (para nombre + thumbnail)
      - /campaign_id/insights?level=ad (para métricas)  → sin iterar por ad
    """
    # 1) Anuncios (para thumbnail & nombre)
    ads = fb_paginate_first_level(
        f"{campaign_id}/ads",
        {"fields": "id,name,effective_status,creative{thumbnail_url}", "limit": 500},
    )
    meta: Dict[str, Dict[str, Any]] = {}
    for a in ads:
        aid = a.get("id")
        if not aid:
            continue
        meta[aid] = {
            "name": a.get("name"),
            "status": str(a.get("effective_status", "")).upper(),
            "thumb": (a.get("creative") or {}).get("thumbnail_url"),
        }

    # 2) Métricas a nivel ad para TODO en UNA llamada
    ins = fb_get(
        f"{campaign_id}/insights",
        {"level": "ad", "fields": "ad_id,ad_name,spend,actions", **build_date_params()},
    )

    out: List[Dict[str, Any]] = []
    for row in (ins.get("data") or []):
        aid = row.get("ad_id")
        spend = f2(row.get("spend"))
        msgs = sum_messages_from_actions(row.get("actions"))
        if not aid or spend <= 0:
            continue  # mostrar solo con gasto
        info = meta.get(aid, {})
        # (opcional) si quieres filtrar ads inactivos, descomenta:
        # if info.get("status") and not str(info["status"]).startswith(ACTIVE_STATUSES):
        #     continue
        out.append(
            {
                "id": aid,
                "name": info.get("name") or row.get("ad_name") or aid,
                "thumbnail_url": info.get("thumb"),
                "spend": spend,
                "results": float(msgs),
                "cpr": f2(spend / msgs) if msgs > 0 else 0.0,
            }
        )

    out.sort(key=lambda x: x.get("spend", 0), reverse=True)
    return jsonify({"data": out})


# -----------------------------------------------------------------------------
# Compat (rutas antiguas todavía usadas desde el front)
# -----------------------------------------------------------------------------
@bp.route("/get_campaigns/<ad_account_id>")
def get_campaigns(ad_account_id: str):
    account = ad_account_id if ad_account_id.startswith("act_") else f"act_{ad_account_id}"
    data = fb_paginate_first_level(
        f"{account}/campaigns",
        {"fields": "id,name,status,effective_status,objective,updated_time", "limit": 200},
    )
    return jsonify({"data": data})

@bp.route("/get_adsets/<campaign_id>")
def get_adsets(campaign_id: str):
    data = fb_paginate_first_level(
        f"{campaign_id}/adsets",
        {"fields": "id,name,status,effective_status,daily_budget,lifetime_budget", "limit": 200},
    )
    return jsonify({"data": data})

@bp.route("/get_ads/<adset_id>")
def get_ads(adset_id: str):
    data = fb_paginate_first_level(
        f"{adset_id}/ads",
        {"fields": "id,name,adset_id,creative{thumbnail_url,asset_feed_spec},status,effective_status", "limit": 200},
    )
    out = []
    for ad in data:
        creative = ad.get("creative") or {}
        ad["thumbnail_url"] = creative.get("thumbnail_url")
        out.append(ad)
    return jsonify({"data": out})

@bp.route("/get_insights/campaign/<campaign_id>")
def get_insights_campaign(campaign_id: str):
    fields = "date_start,date_stop,spend,actions,objective"
    params = {"fields": fields, **build_date_params()}
    if request.args.get("time_increment"):
        params["time_increment"] = request.args.get("time_increment")

    j = fb_get(f"{campaign_id}/insights", params)
    rows = j.get("data", []) or []

    out_rows = []
    total_spend = 0.0
    total_msgs = 0.0
    for r in rows:
        spend = f2(r.get("spend"))
        msgs = sum_messages_from_actions(r.get("actions"))
        total_spend += spend
        total_msgs += msgs
        out_rows.append(
            {
                "date_start": r.get("date_start"),
                "date_stop": r.get("date_stop"),
                "spend": spend,
                "results": msgs,
                "cpr": f2(spend / msgs) if msgs > 0 else 0.0,
            }
        )

    summary = {
        "spend": f2(total_spend),
        "results": float(total_msgs),
        "cpr": f2(total_spend / total_msgs) if total_msgs > 0 else 0.0,
    }
    return jsonify({"data": out_rows, "summary": summary})


# -----------------------------------------------------------------------------
# Errores
# -----------------------------------------------------------------------------
@bp.app_errorhandler(404)
def _404(_e):
    try:
        return render_template("error.html", code=404, message="Recurso no encontrado"), 404
    except Exception:
        return jsonify({"error": "not_found"}), 404

@bp.app_errorhandler(500)
def _500(_e):
    logging.exception("Error 500")
    try:
        return render_template("error.html", code=500, message="Error interno"), 500
    except Exception:
        return jsonify({"error": "internal_error"}), 500
# --- MAGIC LINK Y GUARDAS (AÑADIR AL FINAL DE app/routes.py) ---
from flask import session, request, redirect, abort

@bp.route("/s/<slug>")
def magic_link(slug):
    """
    Link para clienta. Setea sesión y te lleva a su dashboard.
    No depende de querystrings (?k=ok es ignorado).
    """
    session["client_slug"] = slug
    session["is_client"] = True
    # dura 7 días (cookie firmada por SECRET_KEY)
    session.permanent = True
    return redirect(f"/dashboard/{slug}")

@bp.route("/logout")
def logout():
    """Salir del modo clienta y volver a la Vista General (admin)."""
    session.clear()
    return redirect("/overview")

@bp.before_app_request
def _client_guard():
    """
    Si hay clienta en sesión, sólo puede:
      - ver su dashboard /dashboard/<slug>
      - consumir estáticos y APIs
      - usar /s/<slug> y /logout
      - /overview la redirige a su dashboard
    Impide abrir /dashboard/<otro_slug>.
    """
    slug = session.get("client_slug")
    if not slug:
        return  # no estás en modo clienta: todo normal

    path = request.path.rstrip("/")

    # Rutas siempre permitidas en modo clienta
    if (
        path.startswith("/static")
        or path.startswith("/api/")
        or path.startswith("/get_")
        or path.startswith("/s/")
        or path == "/logout"
    ):
        return

    # Forzar /overview -> su propio dashboard
    if path == "/overview" or path == "":
        return redirect(f"/dashboard/{slug}")

    # Si entra a /dashboard/<otro>, bloquear
    if path.startswith("/dashboard/"):
        try:
            target = path.split("/")[2]
        except IndexError:
            target = ""
        if target and target != slug:
            # 403 con tu plantilla de error
            abort(403)

    # En cualquier otro caso, dejar pasar
    return
# --- FIN BLOQUE ---
