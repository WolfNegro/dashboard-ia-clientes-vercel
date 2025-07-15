# app/utils.py

import json
from collections import defaultdict
from datetime import datetime, timedelta # CIRUGÍA: Importaciones necesarias para la nueva función

def procesar_metricas_totales(data):
    resultado = defaultdict(float)
    if not data: return dict(resultado)
    entries = data if isinstance(data, list) else [data]
    for entry in entries:
        resultado['spend'] += float(entry.get('spend', 0))
        resultado['clicks'] += int(entry.get('clicks', 0))
        resultado['impressions'] += int(entry.get('impressions', 0))
        if 'actions' in entry:
            for action in entry.get('actions', []):
                if action.get("action_type") == "onsite_conversion.messaging_conversation_started_7d":
                    resultado['messages'] += float(action.get("value", 0))
    if resultado['impressions'] > 0:
        resultado['ctr'] = (resultado['clicks'] / resultado['impressions']) * 100
        resultado['cpm'] = (resultado['spend'] / resultado['impressions']) * 1000
    if resultado['messages'] > 0:
        resultado['cost_per_message'] = resultado['spend'] / resultado['messages']
    return dict(resultado)

def procesar_metricas_diarias(data):
    metricas_por_dia = defaultdict(lambda: defaultdict(float))
    if not data: return {}
    for entry in data:
        fecha = entry.get("date_start")
        if not fecha: continue
        metricas_por_dia[fecha]['spend'] += float(entry.get('spend', 0))
        metricas_por_dia[fecha]['clicks'] += int(entry.get('clicks', 0))
        metricas_por_dia[fecha]['impressions'] += int(entry.get('impressions', 0))
        if 'actions' in entry:
            for action in entry.get('actions', []):
                if action.get("action_type") == "onsite_conversion.messaging_conversation_started_7d":
                    metricas_por_dia[fecha]['messages'] += float(action.get("value", 0))
    resultado_final = {}
    for fecha, metricas in sorted(metricas_por_dia.items()):
        if metricas.get('impressions', 0) > 0:
            metricas['ctr'] = (metricas.get('clicks', 0) / metricas['impressions']) * 100
        if metricas.get('messages', 0) > 0:
            metricas['cost_per_message'] = metricas.get('spend', 0) / metricas['messages']
        resultado_final[fecha] = dict(metricas)
    return resultado_final

def calcular_comparativa(metricas_hoy, metricas_ayer):
    comparativa = {}
    for metrica in ['spend', 'messages', 'cost_per_message']:
        valor_hoy = metricas_hoy.get(metrica, 0)
        valor_ayer = metricas_ayer.get(metrica, 0)
        if valor_ayer > 0:
            diferencia = ((valor_hoy - valor_ayer) / valor_ayer) * 100
            comparativa[metrica] = diferencia
        elif valor_hoy > 0:
            comparativa[metrica] = 100.0
        else:
            comparativa[metrica] = 0.0
    return comparativa

def procesar_datos_ranking(lista_campanas_procesadas, campana_seleccionada_id):
    if not lista_campanas_procesadas: return {}
    metricas_procesadas = lista_campanas_procesadas
    ranking_resultados = sorted(metricas_procesadas, key=lambda x: x['results'], reverse=True)
    ranking_cpr = sorted(metricas_procesadas, key=lambda x: x['cost_per_result'])
    posicion_resultados = next((i + 1 for i, c in enumerate(ranking_resultados) if c['id'] == campana_seleccionada_id), -1)
    posicion_cpr = next((i + 1 for i, c in enumerate(ranking_cpr) if c['id'] == campana_seleccionada_id), -1)
    lista_resultados = [c['results'] for c in metricas_procesadas]
    lista_cpr = [c['cost_per_result'] for c in metricas_procesadas if c['cost_per_result'] != float('inf')]
    return {
        'total_campaigns': len(metricas_procesadas),
        'results': { 'rank': posicion_resultados, 'min': min(lista_resultados) if lista_resultados else 0, 'max': max(lista_resultados) if lista_resultados else 0, 'value': next((c['results'] for c in metricas_procesadas if c['id'] == campana_seleccionada_id), 0) },
        'cost_per_result': { 'rank': posicion_cpr, 'min': min(lista_cpr) if lista_cpr else 0, 'max': max(lista_cpr) if lista_cpr else 0, 'value': next((c['cost_per_result'] for c in metricas_procesadas if c['id'] == campana_seleccionada_id), 0) }
    }

# === FUNCIÓN FINAL PARA EL BRIEFING EXPRESS ===
def generar_prompt_completo(metricas_totales, metricas_diarias, top_anuncios, currency_symbol, date_range):
    """
    Genera un prompt para la IA optimizado para el formato "Briefing Express".
    """
    # --- 1. Preparación de Datos ---
    resultados_totales = int(metricas_totales.get('messages', 0))
    cpr_promedio = metricas_totales.get('cost_per_message', 0)
     
    mejor_anuncio_nombre = "N/A"
    mejor_anuncio_cpr = 0
    porcentaje_mejora_cpr = 0

    if top_anuncios:
        mejor_anuncio = top_anuncios[0]
        mejor_anuncio_nombre = mejor_anuncio.get('nombre_anuncio', 'Anuncio Top')
        mejor_anuncio_cpr = mejor_anuncio['metricas'].get('cost_per_message', 0)
        if cpr_promedio > 0 and mejor_anuncio_cpr > 0:
            porcentaje_mejora_cpr = (1 - (mejor_anuncio_cpr / cpr_promedio)) * 100

    pico_diario_info = "No hubo un pico claro."
    if metricas_diarias:
        mejor_dia_data = max(metricas_diarias.values(), key=lambda x: x.get('messages', 0), default=None)
        if mejor_dia_data and mejor_dia_data.get('messages', 0) > 0:
            fecha_mejor_dia = next((k for k, v in metricas_diarias.items() if v == mejor_dia_data), "N/A")
            pico_diario_info = f"Pico: {int(mejor_dia_data.get('messages', 0))} mensajes el {fecha_mejor_dia}"

    # --- 2. Construcción del Prompt ---
    prompt = f"""
Genera un "Briefing Express" para un dashboard de análisis de campañas.
Debe ser breve, claro y visual, pensado para que un dueño de negocio no técnico lo entienda rápido.
Usa los emojis proporcionados en la estructura.
Mantén un tono profesional, breve y accionable.

**DATOS DE ENTRADA:**
- Resultados totales: {resultados_totales}
- CPR Promedio: {currency_symbol}{cpr_promedio:.2f}
- Mejor anuncio: '{mejor_anuncio_nombre}'
- CPR del mejor anuncio: {currency_symbol}{mejor_anuncio_cpr:.2f}
- Dato del pico diario: {pico_diario_info}
- Porcentaje de mejora del mejor anuncio vs promedio: {porcentaje_mejora_cpr:.0f}%

**INSTRUCCIONES:**
Usa los datos de entrada para rellenar EXACTAMENTE la siguiente plantilla Markdown. No añadas nada más.

### ⚡ Briefing Express
- ✅ {resultados_totales} resultados | CPR {currency_symbol}{cpr_promedio:.2f}
- 🔥 '{mejor_anuncio_nombre}' destaca (CPR {currency_symbol}{mejor_anuncio_cpr:.2f})
- 📈 {pico_diario_info}
- 👉 **Acciones:** duplicar anuncio, escalar en picos y test A/B

### 🧠 Insight Clave:
(Usa el "porcentaje de mejora" para generar una frase. Ejemplo: "Tu mejor anuncio rinde un {porcentaje_mejora_cpr:.0f}% más barato que el promedio, generando mayor volumen a menor costo.")

### ✅ Recomendación Directa:
(Genera UNA frase de acción concreta. Ejemplo: "Invierte más en días pico y prueba 2-3 variantes del anuncio top para mantener el CPR bajo.")
"""
    return prompt.strip()

# ==============================================================================
#           CIRUGÍA: INICIO DE LA NUEVA FUNCIÓN DE PROCESAMIENTO
# ==============================================================================
def procesar_datos_comparativos_historicos(raw_data):
    """
    Procesa la lista de insights diarios de los últimos 60 días y la estructura
    para la vista expandida del frontend.
    """
    if not raw_data:
        return {}

    # Reutilizamos la función existente para tener un diccionario limpio de métricas por día.
    daily_metrics = procesar_metricas_diarias(raw_data)
     
    # Helper interno para calcular totales y series para un conjunto de fechas.
    def _calculate_period_summary(dates_to_process, all_daily_metrics):
        total_spend = 0
        total_leads = 0
        chart_data = {'labels': [], 'leads': [], 'cpr': [], 'spend': []}

        for date_str in sorted(dates_to_process):
            day_data = all_daily_metrics.get(date_str, {})
            day_spend = day_data.get('spend', 0)
            day_leads = day_data.get('messages', 0)
            day_cpr = day_data.get('cost_per_message', 0)

            total_spend += day_spend
            total_leads += day_leads

            chart_data['labels'].append(datetime.strptime(date_str, '%Y-%m-%d').strftime('%d %b'))
            chart_data['leads'].append(int(day_leads))
            chart_data['spend'].append(day_spend)
            chart_data['cpr'].append(day_cpr)

        total_cpr = (total_spend / total_leads) if total_leads > 0 else 0
         
        return {'summary': {'leads': total_leads, 'cpr': total_cpr, 'spend': total_spend}, 'chart_data': chart_data}

    # Helper interno para calcular el porcentaje de tendencia.
    def _calculate_trend(current, previous):
        if previous > 0: return ((current - previous) / previous) * 100
        if current > 0: return 100.0
        return 0.0

    today = datetime.now()
    final_result = {}
     
    for period_days in [3, 7, 30]:
        # Definimos los rangos de fechas para el período actual y el anterior.
        current_period_dates = [(today - timedelta(days=i)).strftime('%Y-%m-%d') for i in range(period_days)]
        previous_period_dates = [(today - timedelta(days=i)).strftime('%Y-%m-%d') for i in range(period_days, period_days * 2)]
         
        # Obtenemos los datos para esos días.
        current_data = _calculate_period_summary(current_period_dates, daily_metrics)
        previous_data = _calculate_period_summary(previous_period_dates, daily_metrics)
         
        current_summary = current_data['summary']
        previous_summary = previous_data['summary']
         
        # Combinamos los valores y las tendencias en la estructura final.
        final_result[f'period_{period_days}'] = {
            'summary': {
                'leads': {'value': int(current_summary['leads']), 'trend': _calculate_trend(current_summary['leads'], previous_summary['leads'])},
                'cpr': {'value': current_summary['cpr'], 'trend': _calculate_trend(current_summary['cpr'], previous_summary['cpr'])},
                'spend': {'value': current_summary['spend'], 'trend': _calculate_trend(current_summary['spend'], previous_summary['spend'])}
            },
            'chart_data': current_data['chart_data']
        }
         
    return final_result
# ==============================================================================
#            CIRUGÍA: FIN DE LA NUEVA FUNCIÓN DE PROCESAMIENTO
# ==============================================================================