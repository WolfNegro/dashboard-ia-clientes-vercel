# app/facebook_manager.py

import requests
import os
import logging
import json
from typing import List, Dict, Any
from collections import defaultdict
from datetime import datetime, timedelta # CIRUGÍA: Importación necesaria para el nuevo método

try:
    import google.generativeai as genai
except ImportError:
    genai = None
    logging.warning("Librerías de Google AI no instaladas.")

GEMINI_API_KEYS_STRING = os.getenv("GEMINI_API_KEYS")
GEMINI_API_KEYS = [key.strip() for key in GEMINI_API_KEYS_STRING.split(',')] if GEMINI_API_KEYS_STRING else []
if not GEMINI_API_KEYS: logging.warning("GEMINI_API_KEYS está vacía.")

GRAPH_API_VERSION = "v19.0"
GRAPH_URL = f"https://graph.facebook.com/{GRAPH_API_VERSION}"

class FacebookAdsManager:
    CURRENCY_MAP = {"PEN": "S/", "USD": "$", "EUR": "€", "COP": "$", "MXN": "$", "ARS": "$", "CLP": "$"}
    REQUEST_TIMEOUT = 45

    def __init__(self):
        self._key_index = 0
        if GEMINI_API_KEYS: logging.info(f"FacebookAdsManager inicializado con {len(GEMINI_API_KEYS)} claves.")

    def _make_request(self, url: str, params: dict = None) -> Dict[str, Any]:
        try:
            response = requests.get(url, params=params, timeout=self.REQUEST_TIMEOUT)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            error_data = e.response.json().get("error", {})
            error_msg = error_data.get("message", "Error desconocido")
            logging.error(f"Error HTTP en API de Facebook: {error_msg} | URL: {url}")
            raise Exception(f"Error en API de Facebook: {error_msg}")
        except requests.exceptions.RequestException as e:
            logging.error(f"Error de red al contactar API de Facebook: {e}")
            raise Exception(f"Error de red: {e}")

    def _get_next_api_key(self) -> str:
        if not GEMINI_API_KEYS: raise ValueError("No hay claves de API de Gemini.")
        key = GEMINI_API_KEYS[self._key_index]
        self._key_index = (self._key_index + 1) % len(GEMINI_API_KEYS)
        return key
        
    def _fetch_paginated_data(self, url: str, params: dict) -> List[Dict[str, Any]]:
        all_items, request_url, is_first = [], url, True
        while request_url:
            try:
                data = self._make_request(request_url, params=(params if is_first else None))
                all_items.extend(data.get("data", []))
                request_url = data.get("paging", {}).get("next")
                is_first = False
            except Exception as e:
                logging.error(f"Error al obtener datos paginados desde {url}: {e}"); break
        return all_items

    def get_ad_accounts(self, token: str) -> List[Dict[str, str]]:
        if not token: return []
        url = f"{GRAPH_URL}/me/adaccounts"
        params = {"fields": "id,name,account_status,business_name", "access_token": token, "limit": 100}
        raw = self._fetch_paginated_data(url, params)
        accounts = [{"id": a["id"], "name": f"{a.get('business_name')} - {a['name']}" if a.get('business_name') else a['name']} for a in raw if a.get("account_status") == 1]
        return sorted(accounts, key=lambda x: x['name'])

    def get_campaigns(self, token: str, account_id: str) -> List[Dict[str, str]]:
        url = f"{GRAPH_URL}/{account_id}/campaigns"
        params = {"fields": "id,name", "access_token": token, "limit": 200, "filtering": json.dumps([{'field': 'effective_status', 'operator': 'IN', 'value': ['ACTIVE']}])}
        return self._fetch_paginated_data(url, params)

    def get_account_currency(self, token: str, account_id: str) -> str:
        url = f"{GRAPH_URL}/{account_id}"
        params = {"fields": "currency", "access_token": token}
        data = self._make_request(url, params)
        code = data.get("currency", "USD")
        return self.CURRENCY_MAP.get(code, f"{code} ")

    def get_metrics(self, token: str, object_id: str, since: str, until: str, level: str = 'campaign') -> List[Dict[str, Any]]:
        url = f"{GRAPH_URL}/{object_id}/insights"
        params = {"access_token": token, "time_range": f'{{"since":"{since}","until":"{until}"}}', "fields": "spend,clicks,actions,date_start,impressions", "time_increment": 1, "level": level, "limit": 365}
        return self._make_request(url, params).get("data", [])

    # ==============================================================================
    #             CIRUGÍA: INICIO DEL NUEVO MÉTODO PARA DATOS HISTÓRICOS
    # ==============================================================================
    def get_historical_comparison_data(self, token: str, campaign_id: str) -> List[Dict[str, Any]]:
        """
        Obtiene los datos de insights diarios de una campaña para los últimos 60 días.
        Esto permite calcular las métricas de 3, 7 y 30 días y sus períodos de 
        comparación correspondientes con una sola llamada a la API.
        """
        logging.info(f"Obteniendo datos históricos de 60 días para la campaña {campaign_id}")
        
        today = datetime.now()
        # Pedimos 59 días atrás para tener un total de 60 días de datos (incluyendo hoy).
        # Esto cubre el período más largo (30 días) y su período anterior de comparación (otros 30 días).
        since_date = (today - timedelta(days=59)).strftime('%Y-%m-%d')
        until_date = today.strftime('%Y-%m-%d')
        
        # Reutilizamos el método get_metrics existente, que es robusto y ya maneja la llamada a la API.
        # Esto es más seguro y mantenible que escribir una nueva lógica de request.
        return self.get_metrics(token, campaign_id, since_date, until_date)
    # ==============================================================================
    #             CIRUGÍA: FIN DEL NUEVO MÉTODO
    # ==============================================================================

    def get_top_performing_ads(self, token: str, campaign_id: str, since: str, until: str, limit: int = 2) -> List[Dict[str, Any]]:
        ads_url = f"{GRAPH_URL}/{campaign_id}/ads"
        ads_params = {"access_token": token, "fields": "id", "limit": 100}
        all_ads_raw = self._fetch_paginated_data(ads_url, ads_params)
        if not all_ads_raw: return []
        processed_ads = []
        for ad_ref in all_ads_raw:
            ad_id = ad_ref.get("id")
            if not ad_id: continue
            try:
                details_url = f"{GRAPH_URL}/{ad_id}"
                details_params = {"access_token": token, "fields": f"name,creative{{body,thumbnail_url,title,image_url}},insights.time_range({{'since':'{since}','until':'{until}'}}){{spend,clicks,impressions,actions}}"}
                ad_details = self._make_request(details_url, params=details_params)
                insights = ad_details.get("insights", {}).get("data")
                if not insights or float(insights[0].get("spend", 0)) == 0: continue
                creative = ad_details.get("creative", {})
                imagen = creative.get("image_url") or creative.get("thumbnail_url") or "https://via.placeholder.com/100"
                texto = creative.get("body") or creative.get("title") or "Texto no disponible"
                processed_ads.append({"id": ad_id, "nombre_anuncio": ad_details.get("name"), "insights": insights, "imagen": imagen, "texto_anuncio": texto})
            except Exception as e:
                logging.error(f"Fallo al procesar anuncio {ad_id}: {e}", exc_info=True)
                continue
        return sorted(processed_ads, key=lambda x: float(x["insights"][0].get("spend", 0)), reverse=True)[:limit]

    # --- FUNCIÓN CORREGIDA Y ROBUSTA PARA EL RANKING ---
    def get_all_campaign_insights_in_account(self, token: str, account_id: str, since: str, until: str) -> List[Dict[str, Any]]:
        logging.info(f"Obteniendo insights de ranking para la cuenta {account_id}")
        url = f"{GRAPH_URL}/{account_id}/insights"
        params = {
            "access_token": token, "level": "campaign", "time_range": f'{{"since":"{since}","until":"{until}"}}',
            "fields": "campaign_id,campaign_name,spend,clicks,impressions,actions", "limit": 500
        }
        return self._fetch_paginated_data(url, params)

    def llamar_ia(self, prompt: str) -> str:
        if not genai or not GEMINI_API_KEYS: return "Error: IA no configurada."
        api_key = self._get_next_api_key()
        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel('gemini-1.5-flash-latest')
            response = model.generate_content(prompt, generation_config=genai.GenerationConfig(max_output_tokens=2048, temperature=0.7), request_options={"timeout": 120})
            if response.parts: return response.text.strip()
            if response.prompt_feedback and response.prompt_feedback.block_reason:
                return f"Análisis de IA bloqueado por: {response.prompt_feedback.block_reason.name}."
            return "La IA no devolvió una respuesta."
        except Exception as e:
            logging.error(f"Error en API de IA: {e}", exc_info=True)
            if "API key not valid" in str(e): return "Error: Clave de API de IA no válida."
            if "429" in str(e): return "Cuota de solicitudes a la API de IA excedida."
            return "Error inesperado al contactar a la IA."