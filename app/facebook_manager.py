# app/facebook_manager.py
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

import requests


class FacebookAdsManager:
    """
    Capa delgada para la Graph API.
    - NO pedimos 'messaging_conversations_started' en fields (no es válido).
    - Para contar mensajes usamos:
        a) 'results' (cuando la campaña devuelve 'Mensajes iniciados' como resultado)
        b) fallback a 'actions' con action_type de conversación iniciada (en código de rutas).
    """

    GRAPH_VERSION = "v21.0"
    BASE_URL = f"https://graph.facebook.com/{GRAPH_VERSION}"

    def __init__(self) -> None:
        token = os.getenv("ACCESS_TOKEN", "").strip()
        if not token:
            raise RuntimeError("ACCESS_TOKEN no configurado en el entorno (.env).")
        self.access_token = token

        # Campos válidos y estables para insights
        self.insights_fields = [
            "objective",
            "spend",
            "impressions",
            "clicks",
            "ctr",
            "cpc",
            "results",      # <-- si Meta devuelve 'Mensajes iniciados' como resultado
            "actions",      # <-- aquí vienen los action_type (fallback)
            "date_start",
            "date_stop",
        ]

    # ------------------------ helpers ------------------------

    def _get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if params is None:
            params = {}
        params["access_token"] = self.access_token
        url = f"{self.BASE_URL}/{path.lstrip('/')}"
        try:
            resp = requests.get(url, params=params, timeout=30)
            resp.raise_for_status()
            return resp.json()
        except requests.HTTPError as e:
            try:
                err = resp.json().get("error", {})
            except Exception:
                err = {"message": str(e)}
            print(
                f"[Facebook API] {resp.status_code} {path} -> "
                f"type={err.get('type')} code={err.get('code')} subcode={err.get('error_subcode')} "
                f"message={err.get('message')}"
            )
            return {"data": []}
        except Exception as e:
            print(f"[Facebook API] EXC {path} -> {e}")
            return {"data": []}

    # ------------------------ objetos ------------------------

    def get_campaigns(self, ad_account_id: str) -> List[Dict[str, Any]]:
        """Lista campañas activas/inactivas para un ad account."""
        fields = "id,name,status,effective_status,created_time"
        data = self._get(f"{ad_account_id}/campaigns", {"fields": fields, "limit": 500})
        return data.get("data", [])

    def get_adsets(self, campaign_id: str) -> List[Dict[str, Any]]:
        fields = "id,name,status,effective_status"
        data = self._get(f"{campaign_id}/adsets", {"fields": fields, "limit": 500})
        return data.get("data", [])

    def get_ads(self, adset_id: str) -> List[Dict[str, Any]]:
        fields = "id,name,status,effective_status,creative{thumbnail_url}"
        data = self._get(f"{adset_id}/ads", {"fields": fields, "limit": 500})
        return data.get("data", [])

    # ------------------------ insights ------------------------

    def insights_for_id(
        self,
        object_id: str,
        *,
        date_preset: Optional[str] = None,
        since: Optional[str] = None,
        until: Optional[str] = None,
        time_increment: Optional[str | int] = None,
    ) -> List[Dict[str, Any]]:
        """
        /{object_id}/insights con campos válidos.
        - date_preset OR time_range (since/until)
        - NO incluimos 'messaging_conversations_started' en fields (no es válido).
        """
        params: Dict[str, Any] = {
            "fields": ",".join(self.insights_fields),
            "limit": 500,
            "action_report_time": "impression",
            "action_attribution_windows": '["7d_click","1d_view"]',
        }

        if time_increment:
            params["time_increment"] = str(time_increment)

        if date_preset:
            params["date_preset"] = date_preset
        elif since and until:
            params["time_range"] = {"since": since, "until": until}
        else:
            params["date_preset"] = "this_month"

        data = self._get(f"{object_id}/insights", params)
        return data.get("data", [])

    # ---- helpers de nivel cuenta ----

    def get_account_insights_preset(self, ad_account_id: str, date_preset: str) -> List[Dict[str, Any]]:
        return self.insights_for_id(ad_account_id, date_preset=date_preset)

    def get_account_insights_range(self, ad_account_id: str, since: str, until: str) -> List[Dict[str, Any]]:
        return self.insights_for_id(ad_account_id, since=since, until=until)

    # ---- helpers de campaña (para gráficos diarios del dashboard) ----

    def get_campaign_insights(
        self, campaign_id: str, *, date_preset: Optional[str] = None, time_increment: Optional[int | str] = None
    ) -> List[Dict[str, Any]]:
        return self.insights_for_id(campaign_id, date_preset=date_preset, time_increment=time_increment)
