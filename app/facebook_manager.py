# app/facebook_manager.py

import requests
import os
import logging
import json
from typing import List, Dict, Any

# --- Configuración inicial y constantes ---
try:
    import google.generativeai as genai
except ImportError:
    genai = None
    logging.warning("Librerías de Google AI no instaladas. La funcionalidad de IA no estará disponible.")

GEMINI_API_KEYS_STRING = os.getenv("GEMINI_API_KEYS")
GEMINI_API_KEYS = [key.strip() for key in GEMINI_API_KEYS_STRING.split(',')] if GEMINI_API_KEYS_STRING else []
if not GEMINI_API_KEYS:
    logging.warning("La lista de GEMINI_API_KEYS está vacía en el archivo .env.")

GRAPH_API_VERSION = "v19.0"
GRAPH_URL = f"https://graph.facebook.com/{GRAPH_API_VERSION}"

class FacebookAdsManager:
    """Gestiona las interacciones con la API de Marketing de Facebook y la API de Gemini."""
    
    CURRENCY_MAP = {"PEN": "S/", "USD": "$", "EUR": "€", "COP": "$", "MXN": "$", "ARS": "$", "CLP": "$"}
    REQUEST_TIMEOUT = 45 # Segundos

    def __init__(self):
        self._key_index = 0
        if GEMINI_API_KEYS:
            logging.info(f"FacebookAdsManager inicializado con {len(GEMINI_API_KEYS)} claves de API de Gemini.")

    # --- Métodos Privados de Ayuda ---

    def _make_request(self, url: str, params: dict = None, method: str = 'GET') -> Dict[str, Any]:
        """Realiza una petición HTTP a la API de Facebook y maneja errores comunes."""
        try:
            if method.upper() == 'GET':
                response = requests.get(url, params=params, timeout=self.REQUEST_TIMEOUT)
            elif method.upper() == 'POST':
                response = requests.post(url, data=params, timeout=self.REQUEST_TIMEOUT)
            else:
                raise ValueError(f"Método HTTP no soportado: {method}")
            
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            error_data = e.response.json().get("error", {})
            error_msg = error_data.get("message", "Error desconocido")
            error_code = error_data.get("code", "N/A")
            logging.error(f"Error HTTP {e.response.status_code} en API de Facebook (Código: {error_code}): {error_msg} | URL: {url}")
            raise Exception(f"Error en API de Facebook: {error_msg}")
        except requests.exceptions.RequestException as e:
            logging.error(f"Error de red al contactar API de Facebook: {e}")
            raise Exception(f"Error de red: {e}")

    def _get_next_api_key(self) -> str:
        """Obtiene la siguiente API Key de Gemini de la lista de forma rotativa."""
        if not GEMINI_API_KEYS:
            raise ValueError("No hay claves de API de Gemini disponibles.")
        key = GEMINI_API_KEYS[self._key_index]
        self._key_index = (self._key_index + 1) % len(GEMINI_API_KEYS)
        return key
        
    def _fetch_paginated_data(self, url: str, params: dict) -> List[Dict[str, Any]]:
        """Obtiene datos de un endpoint paginado de la API de Facebook de forma eficiente."""
        all_items = []
        request_url = url
        is_first_request = True
        
        while request_url:
            try:
                # Los parámetros solo se envían en la primera petición. Las siguientes URLs ya los contienen.
                current_params = params if is_first_request else {}
                data = self._make_request(request_url, params=current_params)
                all_items.extend(data.get("data", []))
                request_url = data.get("paging", {}).get("next")
                is_first_request = False
            except Exception as e:
                logging.error(f"Error al obtener un lote de datos paginados desde {url}: {e}")
                break
        return all_items

    # --- Métodos Públicos (API de Facebook) ---

    def get_ad_accounts(self, access_token: str) -> List[Dict[str, str]]:
        """Obtiene todas las cuentas publicitarias activas asociadas a un token."""
        if not access_token: return []
        
        url = f"{GRAPH_URL}/me/adaccounts"
        params = {
            "fields": "id,name,account_status,business_name",
            "access_token": access_token,
            "limit": 100
        }
        all_accounts_raw = self._fetch_paginated_data(url, params)
        
        active_accounts = [
            {
                "id": acc["id"],
                "name": f"{acc.get('business_name')} - {acc['name']}" if acc.get('business_name') else acc['name']
            }
            for acc in all_accounts_raw if acc.get("account_status") == 1
        ]
        return sorted(active_accounts, key=lambda x: x['name'])

    def get_campaigns(self, access_token: str, cuenta_id: str) -> List[Dict[str, str]]:
        """Obtiene todas las campañas activas de una cuenta publicitaria."""
        url = f"{GRAPH_URL}/{cuenta_id}/campaigns"
        params = {"fields": "id,name,status", "access_token": access_token, "limit": 200}
        all_campaigns_raw = self._fetch_paginated_data(url, params)
        
        active_campaigns = [
            {"id": c["id"], "name": c["name"]}
            for c in all_campaigns_raw if c.get("status") == "ACTIVE"
        ]
        return active_campaigns

    def get_account_currency(self, access_token: str, cuenta_id: str) -> str:
        """Obtiene el símbolo de la moneda de la cuenta."""
        url = f"{GRAPH_URL}/{cuenta_id}"
        params = {"fields": "currency", "access_token": access_token}
        data = self._make_request(url, params)
        currency_code = data.get("currency", "USD")
        return self.CURRENCY_MAP.get(currency_code, f"{currency_code} ")

    def get_metrics(self, access_token: str, campaign_id: str, since: str, until: str) -> List[Dict[str, Any]]:
        """Obtiene las métricas diarias de una campaña."""
        url = f"{GRAPH_URL}/{campaign_id}/insights"
        params = {
            "access_token": access_token,
            "time_range": f'{{"since":"{since}","until":"{until}"}}',
            "fields": "spend,clicks,actions,date_start,impressions",
            "time_increment": 1,
            "limit": 365
        }
        return self._make_request(url, params=params).get("data", [])

    def get_top_performing_ads(self, access_token: str, campaign_id: str, since: str, until: str, limit: int = 2) -> List[Dict[str, Any]]:
        """
        Obtiene los anuncios con mayor rendimiento.
        Esta es la versión más robusta, que procesa cada anuncio individualmente para maximizar la fiabilidad.
        """
        
        # 1. Obtener solo los IDs de los anuncios de la campaña.
        ads_url = f"{GRAPH_URL}/{campaign_id}/ads"
        ads_params = {"access_token": access_token, "fields": "id", "limit": 100}
        all_ads_raw = self._fetch_paginated_data(ads_url, ads_params)
        
        if not all_ads_raw:
            logging.info(f"No se encontraron anuncios en la campaña {campaign_id}.")
            return []

        # 2. Iterar sobre cada ID de anuncio para obtener sus datos completos de forma individual.
        processed_ads = []
        for ad_ref in all_ads_raw:
            ad_id = ad_ref.get("id")
            if not ad_id:
                continue

            try:
                # 2.1. Obtener TODO sobre este anuncio en una sola llamada: insights y creativos.
                ad_details_url = f"{GRAPH_URL}/{ad_id}"
                ad_details_params = {
                    "access_token": access_token,
                    "fields": (
                        "name,"
                        "creative{body,title,image_url,thumbnail_url,effective_object_story_id,asset_feed_spec{images}},"
                        f"insights.time_range({{'since':'{since}','until':'{until}'}})"
                        "{spend,clicks,impressions,actions}"
                    )
                }
                ad_details = self._make_request(ad_details_url, params=ad_details_params)

                # 2.2. Validar que tenemos métricas y gasto.
                insights = ad_details.get("insights", {}).get("data")
                if not insights or float(insights[0].get("spend", 0)) == 0:
                    logging.info(f"Anuncio {ad_id} omitido por falta de gasto o métricas.")
                    continue

                # 2.3. Lógica para obtener la mejor imagen posible.
                creative = ad_details.get("creative", {})
                story_id = creative.get("effective_object_story_id")
                imagen = None

                # Prioridad 1: 'full_picture' (la mejor calidad)
                if story_id:
                    try:
                        image_params = {"access_token": access_token, "fields": "full_picture"}
                        image_data = self._make_request(f"{GRAPH_URL}/{story_id}", params=image_params)
                        imagen = image_data.get("full_picture")
                        logging.info(f"Imagen de alta calidad (full_picture) encontrada para ad {ad_id}")
                    except Exception as e:
                        logging.warning(f"No se pudo obtener 'full_picture' para story_id {story_id}: {e}")
                
                # Lógica de fallback si 'full_picture' falla o no existe.
                if not imagen:
                    imagen = creative.get("image_url")
                    if imagen: logging.info(f"Usando 'image_url' para ad {ad_id}")
                
                if not imagen and creative.get("asset_feed_spec", {}).get("images"):
                    imagen_list = creative["asset_feed_spec"]["images"]
                    if imagen_list and imagen_list[0].get("url"):
                        imagen = imagen_list[0].get("url")
                        if imagen: logging.info(f"Usando 'asset_feed_spec' para ad {ad_id}")

                if not imagen:
                    imagen = creative.get("thumbnail_url")
                    if imagen: logging.info(f"Usando 'thumbnail_url' (último recurso) para ad {ad_id}")
                
                # 2.4. Obtener el texto del anuncio.
                texto = creative.get("body") or creative.get("title") or "Texto no disponible"

                # 2.5. Añadir el anuncio procesado a la lista.
                processed_ads.append({
                    "id": ad_id,
                    "name": ad_details.get("name"),
                    "insights": insights,
                    "imagen": imagen or "https://via.placeholder.com/600x600/161b22/c9d1d9?text=Imagen+No+Disponible",
                    "texto": texto
                })
                logging.info(f"Anuncio {ad_id} procesado exitosamente.")

            except Exception as e:
                logging.error(f"Fallo completo al procesar el anuncio {ad_id}: {e}", exc_info=True)
                continue # Continuamos con el siguiente anuncio, pase lo que pase.

        # 3. Ordenar los anuncios procesados por gasto y devolver los 4 mejores.
        if not processed_ads:
            logging.warning("FINAL: Ningún anuncio pudo ser procesado con éxito.")
            return []
            
        logging.info(f"Se procesaron {len(processed_ads)} anuncios. Se devolverán los {limit} mejores.")
        sorted_ads = sorted(processed_ads, key=lambda x: float(x["insights"][0].get("spend", 0)), reverse=True)
        return sorted_ads[:limit]

    # --- Métodos Públicos (API de IA) ---

    def llamar_ia(self, prompt: str) -> str:
        """Llama a la API de Gemini con un prompt y devuelve la respuesta textual."""
        if not genai or not GEMINI_API_KEYS:
            return "Error: La funcionalidad de IA no está configurada en el servidor."
            
        api_key = self._get_next_api_key()
        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel('gemini-1.5-flash-latest')
            response = model.generate_content(
                prompt, 
                generation_config=genai.GenerationConfig(max_output_tokens=2048, temperature=0.7), 
                request_options={"timeout": 120}
            )
            
            if response.parts:
                return response.text.strip()
            
            if response.prompt_feedback and response.prompt_feedback.block_reason:
                block_reason = response.prompt_feedback.block_reason.name
                logging.warning(f"Llamada a la IA bloqueada por: {block_reason}")
                return f"El análisis de la IA fue bloqueado por políticas de seguridad ({block_reason})."
            
            return "La IA no devolvió una respuesta. Inténtalo de nuevo."

        except Exception as e:
            logging.error(f"Error en la llamada a la API de IA: {e}", exc_info=True)
            if "API key not valid" in str(e):
                return "Error: Una de las claves de API de IA no es válida. Por favor, revísala."
            if "429" in str(e): # Rate limit
                 return "Se ha excedido la cuota de solicitudes a la API de IA. Por favor, espera un minuto antes de volver a intentarlo."
            return f"Ocurrió un error inesperado al contactar a la IA. Por favor, intenta de nuevo."