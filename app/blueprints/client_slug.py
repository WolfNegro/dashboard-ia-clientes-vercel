# app/blueprints/client_slug.py
from flask import Blueprint, render_template
import os, json

client_bp = Blueprint("client_bp", __name__)

def _root(*parts):
    # .../app/blueprints -> repo root
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", *parts))

def _load_clients():
    """
    Lee clients.json (tu formato actual):
    {
      "clinic_prime": { "client_name": "Clinic Prime", "ad_account_ids": ["act_..."] },
      ...
    }
    """
    candidates = [
        _root("clients.json"),          # raíz del repo
        _root("app", "clients.json"),   # fallback por si lo tienes en /app
    ]
    for path in candidates:
        if os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
    return {}

def _pick_entry(data, slug):
    # tolerante con minúsculas y guiones
    if not isinstance(data, dict):
        return {}
    keys = [slug, slug.lower(), slug.replace("-", "_"), slug.replace("-", "_").lower()]
    for k in keys:
        if k in data and isinstance(data[k], dict):
            return data[k]
    return {}

@client_bp.route("/s/<slug>")
def client_slug(slug):
    data = _load_clients()
    entry = _pick_entry(data, slug)
    client_name     = entry.get("client_name") or slug.replace("_", " ").replace("-", " ").title()
    client_id       = entry.get("client_id")  # opcional; si no existe, será None
    ad_account_ids  = entry.get("ad_account_ids") or []

    return render_template(
        "index.html",
        slug=slug,
        client_name=client_name,
        client_id=client_id,
        ad_account_ids=ad_account_ids,
    )
