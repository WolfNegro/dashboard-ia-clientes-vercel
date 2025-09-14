# app/routes.py
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from flask import Blueprint, jsonify, redirect, render_template, request, url_for

from .facebook_manager import FacebookAdsManager

routes = Blueprint("routes", __name__)

# ----------------- carga de clientes -----------------
BASE_DIR = Path(__file__).resolve().parent.parent
CLIENTS_PATH = BASE_DIR / "clients.json"

def _load_clients() -> Dict[str, Any]:
    try:
        with open(CLIENTS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

CLIENTS: Dict[str, Any] = _load_clients()
FB = FacebookAdsManager()


def _first_client_id() -> str:
    return next(iter(CLIENTS.keys())) if CLIENTS else ""


def _get_accounts(client_id: str) -> List[str]:
    info = CLIENTS.get(client_id) or {}
    ids = info.get("ad_account_ids") or []
    out: List[str] = []
    for aid in ids:
        s = str(aid).strip()
        out.append(s if s.startswith("act_") else f"act_{s}")
    return out


# ----------------- vistas -----------------
@routes.route("/")
def home():
    cid = _first_client_id()
    if not cid:
        return "Sin clientes cargados en clients.json", 500
    return redirect(url_for("routes.dashboard", client_id=cid))


@routes.route("/dashboard/<client_id>")
def dashboard(client_id: str):
    client = CLIENTS.get(client_id)
    if not client:
        return f"Cliente '{client_id}' no encontrado.", 404
    return render_template(
        "index.html",
        client_id=client_id,
        client_name=client.get("client_name", client_id),
        ad_account_ids=_get_accounts(client_id),
    )


@routes.route("/overview")
def overview():
    return render_template("overview.html")


# ----------------- APIs -----------------
@routes.route("/get_campaigns/<ad_account_id>")
def get_campaigns(ad_account_id: str):
    rows = FB.get_campaigns(ad_account_id)
    active_statuses = {"ACTIVE", "CAMPAIGN_GROUP_ACTIVE", "PAUSED", "IN_PROGRESS"}
    out = []
    for r in rows:
        s = (r.get("status") or "").upper()
        eff = (r.get("effective_status") or "").upper()
        if (s in active_statuses) or (eff in active_statuses):
            out.append(r)
    return jsonify(out)


@routes.route("/get_adsets/<campaign_id>")
def get_adsets(campaign_id: str):
    return jsonify(FB.get_adsets(campaign_id))


@routes.route("/get_ads/<adset_id>")
def get_ads(adset_id: str):
    return jsonify(FB.get_ads(adset_id))


@routes.route("/get_insights/campaign/<campaign_id>")
def get_insights_campaign(campaign_id: str):
    date_preset = request.args.get("date_preset")
    time_increment = request.args.get("time_increment")
    data = FB.get_campaign_insights(campaign_id, date_preset=date_preset, time_increment=time_increment)
    return jsonify(data)


# NUEVO: insights por ANUNCIO
@routes.route("/get_insights/ad/<ad_id>")
def get_insights_ad(ad_id: str):
    date_preset = request.args.get("date_preset")
    since = request.args.get("since")
    until = request.args.get("until")
    if since and until:
        data = FB.insights_for_id(ad_id, since=since, until=until)
    else:
        data = FB.insights_for_id(ad_id, date_preset=date_preset or "today")
    return jsonify(data)


# ---------- Suma segura (usada en /api/overview) ----------
def _summarize(rows: List[dict]) -> Dict[str, float]:
    spend = 0.0
    msgs = 0.0

    for r in rows:
        # gasto
        try:
            spend += float(r.get("spend") or 0)
        except Exception:
            pass

        # preferimos 'results'
        added = False
        val = r.get("results")
        if val is not None:
            try:
                v = float(val)
                msgs += v
                added = v > 0
            except Exception:
                pass

        # fallback 'actions'
        if not added:
            for a in (r.get("actions") or []):
                t = (a.get("action_type") or "").lower()
                if (
                    "onsite_conversion.messaging_conversation_started" in t
                    or "messaging_conversation_started" in t
                    or "messaging_conversations_started" in t
                    or "omni_messaging_conversation_started" in t
                    or "messaging_first_reply" in t
                    or "conversation_started" in t
                ):
                    try:
                        msgs += float(a.get("value") or 0)
                    except Exception:
                        pass

    cpr = (spend / msgs) if msgs else 0.0
    return {"spend": round(spend, 2), "messages": round(msgs, 0), "cpr": round(cpr, 2)}


@routes.route("/api/overview")
def api_overview():
    date_preset = request.args.get("date_preset", "today")
    since = request.args.get("since")
    until = request.args.get("until")

    rows_out: List[Dict[str, Any]] = []

    for cid, meta in CLIENTS.items():
        accounts = _get_accounts(cid)
        agg_spend = 0.0
        agg_msgs = 0.0

        for aid in accounts:
            if since and until:
                data = FB.get_account_insights_range(aid, since, until)
            else:
                data = FB.get_account_insights_preset(aid, date_preset)
            s = _summarize(data)
            agg_spend += s["spend"]
            agg_msgs += s["messages"]

        cpr = (agg_spend / agg_msgs) if agg_msgs else 0.0

        rows_out.append({
            "client_id": cid,
            "client_name": meta.get("client_name", cid),
            "spend": round(agg_spend, 2),
            "messages": round(agg_msgs, 0),
            "cpr": round(cpr, 2),
        })

    return jsonify(rows_out)
