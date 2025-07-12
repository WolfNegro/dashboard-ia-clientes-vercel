# app/utils.py

import json
from collections import defaultdict

def procesar_metricas_totales(data):
    """Procesa una lista de insights para obtener un total consolidado y preciso."""
    resultado = defaultdict(float)
    if not data: return dict(resultado)
    for entry in data:
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
    """Procesa una lista de insights diarios para calcular correctamente las métricas de cada día."""
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

# FIX: Un único y poderoso prompt para generar TODO en una sola llamada.
def generar_prompt_completo(metricas_totales, metricas_diarias, top_anuncios, descripcion_negocio, currency_symbol, date_range):
    
    # --- Preparación de datos para el prompt ---
    gasto_total = f"{currency_symbol}{metricas_totales.get('spend', 0):.2f}"
    resultados_totales = int(metricas_totales.get('messages', 0))
    cpr_total = f"{currency_symbol}{metricas_totales.get('cost_per_message', 0):.2f}"
    
    mejor_dia_info = "No hay datos diarios para analizar tendencias."
    if metricas_diarias:
        mejor_dia_data = max(metricas_diarias.values(), key=lambda x: x.get('messages', 0), default=None)
        if mejor_dia_data:
            fecha_mejor_dia = next((k for k, v in metricas_diarias.items() if v == mejor_dia_data), "N/A")
            mejor_dia_info = f"El día de mayor rendimiento fue el {fecha_mejor_dia}, con {int(mejor_dia_data.get('messages', 0))} mensajes."

    # Preparamos los datos de los anuncios para que la IA los analice
    seccion_anuncios_para_analizar = ""
    for i, ad in enumerate(top_anuncios):
        ad_id = ad.get('id', 'N/A')
        ad_texto = ad.get('texto_original', 'Sin texto disponible.')
        ad_cpr = f"{currency_symbol}{ad['metricas'].get('cost_per_message', 0):.2f}"
        seccion_anuncios_para_analizar += f"""
---
**Anuncio {i+1} (ID: {ad_id})**
- **Costo por Resultado (CPR):** {ad_cpr}
- **Texto a Analizar:** "{ad_texto}"
"""

    # --- El Prompt Unificado ---
    prompt = f"""
Actúa como un analista senior de datos y estratega de marketing digital. Tu tarea es generar un informe completo en dos partes, basándote en los datos proporcionados. Tu respuesta debe estar en español.

**PARTE 1: BRIEFING ESTRATÉGICO**

**Datos de la Campaña:**
- **Periodo:** {date_range}
- **Negocio:** {descripcion_negocio}
- **Métricas Generales:** Inversión: {gasto_total}, Mensajes: {resultados_totales}, CPR Promedio: {cpr_total}.
- **Insight Diario:** {mejor_dia_info}

**Instrucciones para el Briefing:**
Crea un briefing ejecutivo usando EXACTAMENTE la siguiente estructura Markdown. Sé directo y accionable.

### 🚀 Resumen Ejecutivo
(1-2 frases resumiendo el rendimiento general).

### 📊 Análisis Rápido
- **Rendimiento General:** (Comenta si el CPR es bueno/malo).
- **Tendencia Clave:** (Explica el insight del 'día de mayor rendimiento').
- **Creatividades que Funcionan:** (Menciona cuál de los anuncios a continuación es más eficiente basándote en su CPR).

### 📌 Plan de Acción Estratégico
- **Optimizar:** (UNA recomendación para mejorar).
- **Escalar:** (UNA recomendación para crecer).
- **Testear:** (UNA recomendación de prueba A/B).

---|||SEPARADOR|||---

**PARTE 2: ANÁLISIS DE COPY DE ANUNCIOS**

**Datos de los Anuncios:**
{seccion_anuncios_para_analizar}

**Instrucciones para el Análisis de Anuncios:**
Para cada anuncio, genera un análisis de su texto usando EXACTAMENTE el siguiente formato. Debes iniciar cada bloque con `|||AD_ANALYSIS_{{ID_DEL_ANUNCIO}}|||`.

|||AD_ANALYSIS_{{ID_DEL_ANUNCIO_1}}|||
✅ **Fuerte:** (1 frase sobre lo mejor del texto del Anuncio 1).
⚠️ **A Mejorar:** (1 frase sobre lo más débil del texto del Anuncio 1).
💡 **Test A/B:** (1 idea de prueba para el texto del Anuncio 1).

|||AD_ANALYSIS_{{ID_DEL_ANUNCIO_2}}|||
✅ **Fuerte:** (Análisis del Anuncio 2).
⚠️ **A Mejorar:** (Análisis del Anuncio 2).
💡 **Test A/B:** (Análisis del Anuncio 2).

(Continúa para todos los anuncios proporcionados)
"""
    return prompt.strip()