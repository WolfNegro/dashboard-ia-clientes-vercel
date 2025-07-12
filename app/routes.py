# app/routes.py

from flask import Blueprint, render_template, request, jsonify, abort
import os
import json
import logging
import re # <-- ¡¡LA ÚNICA LÍNEA QUE NECESITAS AÑADIR!!

from .facebook_manager import FacebookAdsManager
from .utils import (
    procesar_metricas_diarias, procesar_metricas_totales,
    generar_prompt_completo
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
routes = Blueprint('routes', __name__)

def load_clients():
    """Carga la configuración de clientes desde el archivo JSON."""
    try:
        with open('clients.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        logging.error("CRÍTICO: El archivo 'clients.json' no se encontró.")
        return {}
    except json.JSONDecodeError:
        logging.error("CRÍTICO: El archivo 'clients.json' tiene un formato JSON inválido.")
        return {}

# --- RUTA PRINCIPAL MODIFICADA PARA SER MULTI-CLIENTE ---
@routes.route('/dashboard/<string:client_id>')
def index(client_id):
    """
    Ruta principal para un cliente específico.
    Usa un ID de cliente para mostrar solo las cuentas publicitarias permitidas.
    """
    clients_config = load_clients()
    client_data = clients_config.get(client_id)

    # Si el ID del cliente en la URL no está en nuestro archivo, negamos el acceso.
    if not client_data:
        abort(404) # 404 Not Found es más seguro que mostrar un error de "Acceso Prohibido".

    cuentas_permitidas_para_cliente = []
    error_message = None
    access_token = os.getenv('ACCESS_TOKEN')

    if not access_token:
        error_message = "Error de configuración del servidor."
    else:
        try:
            fb = FacebookAdsManager()
            # 1. Obtenemos TODAS las cuentas a las que nuestro token maestro tiene acceso.
            all_accounts_from_token = fb.get_ad_accounts(access_token)
            
            # 2. FILTRAMOS esa lista para quedarnos solo con las que este cliente tiene permitidas.
            allowed_account_ids_for_client = client_data.get("ad_account_ids", [])
            cuentas_permitidas_para_cliente = [
                acc for acc in all_accounts_from_token if acc['id'] in allowed_account_ids_for_client
            ]

            if not cuentas_permitidas_para_cliente:
                error_message = f"Acceso correcto, pero no se encontraron cuentas publicitarias activas para el cliente '{client_data.get('client_name')}'."

        except Exception as e:
            logging.error(f"Error al cargar datos para el cliente {client_id}: {e}", exc_info=True)
            error_message = f"Error al conectar con la API de Facebook: {e}"

    # 3. Pasamos solo la lista filtrada al frontend.
    return render_template('index.html',
                           cuentas=cuentas_permitidas_para_cliente,
                           error_message=error_message)

# --- OTRAS RUTAS (NO NECESITAN CAMBIOS) ---
# Estas funciones ya reciben el ID de la cuenta directamente desde el frontend,
# por lo que no necesitan saber nada sobre el cliente.

@routes.route('/get_campaigns/<string:cuenta_id>')
def get_campaigns_route(cuenta_id):
    access_token = os.getenv('ACCESS_TOKEN')
    if not access_token: return jsonify({"error": "Token de acceso no configurado en el servidor"}), 500
    try:
        manager = FacebookAdsManager()
        campaigns = manager.get_campaigns(access_token, cuenta_id)
        return jsonify(campaigns)
    except Exception as e:
        logging.error(f"Error en get_campaigns_route para cuenta {cuenta_id}: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@routes.route('/analizar_campana', methods=['POST'])
def analizar_campana_route():
    access_token = os.getenv('ACCESS_TOKEN')
    if not access_token: return jsonify({"error": "Token de acceso no configurado en el servidor"}), 500
    try:
        data = request.json
        cuenta_id, campaign_id, date_range, desc, pais = (
            data.get('cuenta_id'), data.get('campaign_id'), data.get('date_range'),
            data.get('descripcion_negocio'), data.get('pais')
        )
        if not all([cuenta_id, campaign_id, date_range, desc, pais]):
            return jsonify({"error": "Faltan datos para el análisis."}), 400
        
        since, until = date_range.split(' - ')
        fb = FacebookAdsManager()
        currency_symbol = fb.get_account_currency(access_token, cuenta_id)
        metricas_raw = fb.get_metrics(access_token, campaign_id, since, until)
        metricas_diarias = procesar_metricas_diarias(metricas_raw)
        metricas_totales = procesar_metricas_totales(metricas_raw)
        top_ads_raw = fb.get_top_performing_ads(access_token, campaign_id, since, until, limit=2)
        top_anuncios_procesados = []
        for ad_data in top_ads_raw:
            insights_anuncio = procesar_metricas_totales(ad_data.get("insights", []))
            top_anuncios_procesados.append({
                "id": ad_data.get('id'), "imagen": ad_data.get('imagen'),
                "metricas": insights_anuncio, "texto_original": ad_data.get('texto', ''),
                "analisis_copy": "Análisis pendiente..."
            })
        
        prompt_completo = generar_prompt_completo(metricas_totales, metricas_diarias, top_anuncios_procesados, desc, currency_symbol, date_range)
        respuesta_completa_ia = fb.llamar_ia(prompt_completo)
        partes = respuesta_completa_ia.split('---|||SEPARADOR|||---')
        analisis_ia_briefing = partes[0].strip()
        analisis_ads_texto = partes[1] if len(partes) > 1 else ""
        matches = re.findall(r'\|\|\|AD_ANALYSIS_([\w\d_]+)\|\|\|([\s\S]*?)(?=\|\|\|AD_ANALYSIS_|$)', analisis_ads_texto)
        analisis_por_ad_id = {ad_id.strip(): analysis.strip() for ad_id, analysis in matches}
        
        for ad in top_anuncios_procesados:
            if ad.get('id') and ad['id'] in analisis_por_ad_id:
                ad['analisis_copy'] = analisis_por_ad_id[ad['id']]
            else:
                ad['analisis_copy'] = "No se pudo generar el análisis para este anuncio."
        
        resultado_final = {
            "metricas_totales": metricas_totales, "metricas_diarias": metricas_diarias,
            "analisis_ia": analisis_ia_briefing, "top_anuncios": top_anuncios_procesados,
            "moneda": currency_symbol
        }
        return jsonify(resultado_final)
    except Exception as e:
        logging.error(f"Error en /analizar_campana: {e}", exc_info=True)
        return jsonify({"error": f"Ocurrió un error en el servidor: {e}"}), 500