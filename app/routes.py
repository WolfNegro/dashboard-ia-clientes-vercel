# app/routes.py

from flask import Blueprint, render_template, request, jsonify, abort
import os
import json
import logging
from datetime import datetime, timedelta, date

from .facebook_manager import FacebookAdsManager
from .utils import (
    procesar_metricas_diarias, procesar_metricas_totales,
    generar_prompt_completo, calcular_comparativa, procesar_datos_ranking,
    procesar_datos_comparativos_historicos
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
routes = Blueprint('routes', __name__)

RAW_CACHE_DIR = 'cache_raw'
if not os.path.exists(RAW_CACHE_DIR):
    os.makedirs(RAW_CACHE_DIR)

# ARQUITECTURA: Esta función ahora está 'desconectada'. La registraremos en __init__.py
# @routes.before_app_first_request  <-- ESTA LÍNEA CAUSABA EL ERROR Y HA SIDO ELIMINADA
def limpiar_cache_antiguo():
    """Elimina archivos de caché con más de 7 días de antigüedad."""
    logging.info("Ejecutando rutina de limpieza de caché antiguo...")
    try:
        for filename in os.listdir(RAW_CACHE_DIR):
            file_path = os.path.join(RAW_CACHE_DIR, filename)
            try:
                date_str = filename.split('_RAW_')[-1].replace('.json', '')
                file_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                if (date.today() - file_date).days > 7:
                    os.remove(file_path)
                    logging.info(f"Eliminado caché antiguo: {filename}")
            except (ValueError, IndexError) as e:
                logging.warning(f"No se pudo procesar el nombre del archivo de caché: {filename}. Error: {e}")
                continue
    except Exception as e:
        logging.error(f"Error durante la limpieza del caché: {e}", exc_info=True)


def load_clients():
    try:
        with open('clients.json', 'r') as f: return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logging.error(f"CRÍTICO: Error al cargar 'clients.json': {e}"); return {}

# --- [EL RESTO DEL ARCHIVO routes.py SE MANTIENE EXACTAMENTE IGUAL] ---
# ... (todo el código desde @routes.route('/dashboard/<string:client_id>') hasta el final)
# ... es idéntico al que te proporcioné en la respuesta anterior.
# ... No lo incluyo aquí de nuevo para no hacer la respuesta innecesariamente larga.
# ... Solo asegúrate de que el decorador de la función de limpieza ha sido eliminado.

@routes.route('/dashboard/<string:client_id>')
def index(client_id):
    clients_config = load_clients()
    client_data = clients_config.get(client_id)
    if not client_data: abort(404)
    access_token = os.getenv('ACCESS_TOKEN')
    cuentas = []
    error_message = None
    if not access_token:
        error_message = "Error de configuración del servidor."
    else:
        try:
            fb = FacebookAdsManager()
            all_accounts = fb.get_ad_accounts(access_token)
            allowed_ids = client_data.get("ad_account_ids", [])
            cuentas = [acc for acc in all_accounts if acc['id'] in allowed_ids]
            if not cuentas: error_message = f"No se encontraron cuentas publicitarias activas."
        except Exception as e:
            error_message = f"Error al conectar con la API de Facebook: {e}"
    return render_template('index.html', cuentas=cuentas, error_message=error_message)

@routes.route('/get_campaigns/<string:cuenta_id>')
def get_campaigns_route(cuenta_id):
    access_token = os.getenv('ACCESS_TOKEN')
    if not access_token: return jsonify({"error": "Token no configurado"}), 500
    try:
        return jsonify(FacebookAdsManager().get_campaigns(access_token, cuenta_id))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@routes.route('/get_comparative_metrics', methods=['POST'])
def get_comparative_metrics_route():
    access_token = os.getenv('ACCESS_TOKEN')
    if not access_token: return jsonify({"error": "Token de acceso no configurado en el servidor."}), 500

    data = request.json
    campaign_id = data.get('campaign_id')
    cuenta_id = data.get('cuenta_id')
    if not campaign_id or not cuenta_id: return jsonify({"error": "Faltan 'campaign_id' o 'cuenta_id'."}), 400

    try:
        fb = FacebookAdsManager()
        raw_historical_data = get_cached_raw_data(fb, access_token, campaign_id)
        
        processed_data = procesar_datos_comparativos_historicos(raw_historical_data)
        moneda = fb.get_account_currency(access_token, cuenta_id)

        return jsonify({"success": True, "data": processed_data, "moneda": moneda})
    except Exception as e:
        logging.error(f"Error en /get_comparative_metrics: {e}", exc_info=True)
        return jsonify({"error": f"Error del servidor al obtener métricas comparativas: {e}"}), 500

def get_cached_raw_data(fb_manager, access_token, campaign_id, days=90):
    today_str = date.today().strftime('%Y-%m-%d')
    cache_filename = f"{campaign_id}_RAW_{today_str}.json"
    cache_filepath = os.path.join(RAW_CACHE_DIR, cache_filename)

    if os.path.exists(cache_filepath):
        logging.info(f"Caché de datos crudos encontrado para la campaña {campaign_id}. Leyendo desde el archivo.")
        with open(cache_filepath, 'r') as f:
            return json.load(f)
    
    logging.info(f"No se encontró caché para la campaña {campaign_id} hoy. Solicitando nuevos datos a la API.")
    since_date = (date.today() - timedelta(days=days)).strftime('%Y-%m-%d')
    until_date = today_str
    
    raw_data = fb_manager.get_metrics(access_token, campaign_id, since_date, until_date)

    with open(cache_filepath, 'w') as f:
        json.dump(raw_data, f)
    
    return raw_data

@routes.route('/analizar_campana', methods=['POST'])
def analizar_campana_route():
    access_token = os.getenv('ACCESS_TOKEN')
    if not access_token: return jsonify({"error": "Token no configurado"}), 500
    
    data = request.json
    required = ['cuenta_id', 'campaign_id', 'date_range', 'descripcion_negocio', 'pais']
    if not all(key in data for key in required): return jsonify({"error": "Faltan datos"}), 400

    try:
        fb = FacebookAdsManager()
        cuenta_id = data['cuenta_id']
        campaign_id = data['campaign_id']
        since, until = data['date_range'].split(' - ')

        hoy_format = date.today().strftime('%Y-%m-%d')
        metricas_raw_hoy = fb.get_metrics(access_token, campaign_id, hoy_format, hoy_format)
        metricas_hoy = procesar_metricas_totales(metricas_raw_hoy)

        raw_data_90_days = get_cached_raw_data(fb, access_token, campaign_id)

        user_range_insights = [
            insight for insight in raw_data_90_days
            if since <= insight['date_start'] <= until
        ]
        
        ayer_format = (date.today() - timedelta(days=1)).strftime('%Y-%m-%d')
        ayer_insights = [
            insight for insight in raw_data_90_days
            if insight['date_start'] == ayer_format
        ]
        metricas_ayer = procesar_metricas_totales(ayer_insights)

        metricas_totales = procesar_metricas_totales(user_range_insights)
        metricas_diarias = procesar_metricas_diarias(user_range_insights)
        
        todas_las_campanas_activas = fb.get_campaigns(access_token, cuenta_id)
        insights_de_campanas = fb.get_all_campaign_insights_in_account(access_token, cuenta_id, since, until)
        insights_dict = {i['campaign_id']: i for i in insights_de_campanas}
        
        campaign_details_full = []
        for campana in todas_las_campanas_activas:
            insight_data = insights_dict.get(campana['id'])
            metricas_ranking = procesar_metricas_totales(insight_data if insight_data else [])
            campaign_details_full.append({
                "id": campana['id'], "name": campana['name'],
                "results": metricas_ranking.get('messages', 0),
                "cost_per_result": metricas_ranking.get('cost_per_message', float('inf'))
            })
        ranking_data = procesar_datos_ranking(campaign_details_full, campaign_id)
        if 'results' in ranking_data:
            ranking_data['campaign_details'] = campaign_details_full

        top_ads_raw = fb.get_top_performing_ads(access_token, campaign_id, since, until, limit=2)
        top_anuncios = [{"id": ad.get('id'), "imagen": ad.get('imagen'), "metricas": procesar_metricas_totales(ad.get("insights", [])), "nombre_anuncio": ad.get('nombre_anuncio', 'N/A'), "texto_anuncio": ad.get('texto_anuncio', 'N/A')} for ad in top_ads_raw]

        moneda = fb.get_account_currency(access_token, cuenta_id)
        prompt = generar_prompt_completo(metricas_totales, metricas_diarias, top_anuncios, data['descripcion_negocio'], moneda, data['date_range'])
        analisis_ia = fb.llamar_ia(prompt)
        
        resultado_final = {
            "metricas_totales": metricas_totales,
            "metricas_diarias": metricas_diarias,
            "analisis_ia": analisis_ia,
            "top_anuncios": top_anuncios,
            "moneda": moneda,
            "metricas_hoy": metricas_hoy,
            "metricas_ayer": metricas_ayer,
            "comparativa": calcular_comparativa(metricas_hoy, metricas_ayer),
            "ranking_data": ranking_data
        }
        
        return jsonify(resultado_final)
        
    except Exception as e:
        logging.error(f"Error en /analizar_campana: {e}", exc_info=True)
        return jsonify({"error": f"Ocurrió un error en el servidor: {e}"}), 500