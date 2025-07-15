/**
 * =================================================================================
 *    DASHBOARD.JS - VERSIÓN FINAL (33.0 - ELIMINACIÓN DE ERROR DE ALTURA)
 * =================================================================================
 * La solución final se aplica en CSS dando una altura explícita al contenedor
 * del modal (#modal-chart-container). Este JS es la versión más limpia y robusta,
 * asegurando que la escala del eje Y es automática y los datos se pasan
 * correctamente.
 * =================================================================================
 */

// --- ESTADO GLOBAL ---
let chartInstances = {};
let modalChartInstance = null;
let selectedDateRangeLabel = "Personalizado";
let historicalDataStore = null;
let historicalChartInstance = null;
let chartDataStore = {};

// --- INICIALIZACIÓN PRINCIPAL ---
document.addEventListener('DOMContentLoaded', function() {
    try {
        const loader = document.getElementById('loader');
        const appContent = document.getElementById('app-content');
        if (loader) loader.style.display = 'none';
        if (appContent) appContent.style.display = 'block';
        if (typeof ERROR_MESSAGE !== 'undefined' && ERROR_MESSAGE) {
            showNotification(ERROR_MESSAGE, 'error');
        }
        setupControlPanel();
        setupDatePicker();
        addEventListeners();
    } catch (error) {
        console.error("Error crítico durante la inicialización:", error);
        const appContent = document.getElementById('app-content');
        if (appContent) {
            appContent.innerHTML = `\<div class='card'\>\<h2\>Error Crítico\</h2\>\<p\>No se pudo iniciar el dashboard. Revise la consola (F12).\</p\>\</div\>`;
            appContent.style.display = 'block';
        }
    }
});

// ==============================================================================
//           FUNCIONES DE CONFIGURACIÓN INICIAL (SETUP)
// ==============================================================================
function setupControlPanel() {
    const cuentaSelect = document.getElementById('cuenta-select');
    if (!cuentaSelect) return;

    if (typeof CUENTAS !== 'undefined' && CUENTAS && CUENTAS.length > 0) {
        cuentaSelect.innerHTML = '\<option value=""\>Seleccione una cuenta...\</option\>';
        CUENTAS.forEach(a => { cuentaSelect.appendChild(new Option(a.name, a.id)); });
        cuentaSelect.disabled = false;
    } else {
        const errorMsg = (typeof ERROR_MESSAGE !== 'undefined' && ERROR_MESSAGE) ? 'Error al cargar' : 'No hay cuentas';
        cuentaSelect.innerHTML = `\<option\>${errorMsg}\</option\>`;
        cuentaSelect.disabled = true;
    }
}

function setupDatePicker() {
    if (typeof $ === 'undefined' || typeof moment === 'undefined') {
        console.error("jQuery o Moment.js no están cargados. El selector de fechas no funcionará.");
        return;
    }
    const datePickerElement = $('#fecha');
    if (!datePickerElement.length) return;

    datePickerElement.daterangepicker({
        ranges: { 'Hoy': [moment(), moment()], 'Ayer': [moment().subtract(1, 'days'), moment().subtract(1, 'days')], 'Últimos 7 Días': [moment().subtract(6, 'days'), moment()], 'Últimos 30 Días': [moment().subtract(29, 'days'), moment()], 'Este Mes': [moment().startOf('month'), moment().endOf('month')], 'Mes Pasado': [moment().subtract(1, 'month').startOf('month'), moment().subtract(1, 'month').endOf('month')] },
        locale: { "format": "YYYY-MM-DD", "separator": " - ", "applyLabel": "Aplicar", "cancelLabel": "Cancelar", "fromLabel": "Desde", "toLabel": "Hasta", "customRangeLabel": "Personalizado", "daysOfWeek": ["Do", "Lu", "Ma", "Mi", "Ju", "Vi", "Sa"], "monthNames": ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"], },
        alwaysShowCalendars: true,
        startDate: moment().subtract(29, 'days'),
        endDate: moment()
    }, (start, end, label) => {
        selectedDateRangeLabel = label;
        validateForm();
    });
     
    selectedDateRangeLabel = "Últimos 30 Días";
    validateForm();
}

function addEventListeners() {
    document.getElementById('cuenta-select')?.addEventListener('change', e => {
        const campanaSelect = document.getElementById('campana-select');
        if (campanaSelect) {
            campanaSelect.innerHTML = '\<option value=""\>Seleccione cuenta\</option\>';
            campanaSelect.disabled = true;
        }
        if (e.target.value) cargarCampanas(e.target.value);
        validateForm();
    });

    ['campana-select', 'descripcion-negocio', 'ubicacion-pais', 'fecha'].forEach(id => {
        const element = document.getElementById(id);
        if (element) {
            const eventType = (id === 'descripcion-negocio' || id === 'ubicacion-pais') ? 'keyup' : 'change';
            element.addEventListener(eventType, validateForm);
            if (eventType === 'change') element.addEventListener('change', validateForm);
        }
    });

    document.getElementById('analizar-btn')?.addEventListener('click', analizarCampana);
    document.getElementById('metricas-hoy-ayer-card')?.addEventListener('click', openHistoricalModal);
    document.querySelector('#chart-modal .close-button')?.addEventListener('click', closeChartModal);
    document.querySelector('#historical-analysis-modal .close-button')?.addEventListener('click', closeHistoricalModal);
     
    document.querySelectorAll('#historical-analysis-modal .period-btn').forEach(btn => {
        btn.addEventListener('click', e => {
            e.stopPropagation();
            document.querySelectorAll('#historical-analysis-modal .period-btn').forEach(b => b.classList.remove('active'));
            e.currentTarget.classList.add('active');
            renderHistoricalData(parseInt(e.currentTarget.dataset.period, 10));
        });
    });

    window.addEventListener('click', e => {
        if (e.target.id === 'chart-modal') closeChartModal();
        if (e.target.id === 'historical-analysis-modal') closeHistoricalModal();
    });
}

// ==============================================================================
//                             LÓGICA PRINCIPAL
// ==============================================================================

function validateForm() {
    const btn = document.getElementById('analizar-btn');
    if(!btn) return;
    btn.disabled = !(document.getElementById('cuenta-select').value && document.getElementById('campana-select').value && document.getElementById('fecha').value && document.getElementById('descripcion-negocio').value && document.getElementById('ubicacion-pais').value);
}

function cargarCampanas(accountId) {
    const c = document.getElementById('campana-select');
    c.disabled = true;
    c.innerHTML = '\<option\>Cargando campañas...\</option\>';
     
    fetch(`/get_campaigns/${accountId}`)
    .then(response => {
        if (!response.ok) throw new Error('Error del servidor.');
        return response.json();
    })
    .then(data => {
        if (data && data.length > 0) {
            c.innerHTML = '\<option value=""\>Seleccione una campaña...\</option\>';
            data.forEach(v => { c.appendChild(new Option(v.name, v.id)); });
            c.disabled = false;
        } else {
            c.innerHTML = '\<option\>No hay campañas activas\</option\>';
        }
    })
    .catch(error => {
        c.innerHTML = '\<option\>Error al cargar\</option\>';
        showNotification('No se pudieron cargar las campañas.', 'error');
        console.error(error);
    })
    .finally(validateForm);
}

async function analizarCampana() {
    resetHistoricalView();
    const btn = document.getElementById('analizar-btn');
    const loader = document.getElementById('loader');
    const dashboard = document.getElementById('dashboard-container');
     
    btn.disabled = true;
    btn.innerHTML = '\<i class="fa-solid fa-spinner fa-spin"\>\</i\> Analizando...';
    loader.style.display = 'flex';
    dashboard.style.display = 'none';
     
    const payload = {
        cuenta_id: document.getElementById('cuenta-select').value,
        campaign_id: document.getElementById('campana-select').value,
        date_range: document.getElementById('fecha').value,
        descripcion_negocio: document.getElementById('descripcion-negocio').value,
        pais: document.getElementById('ubicacion-pais').value
    };

    try {
        const response = await fetch('/analizar_campana', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const result = await response.json();
        if (!response.ok) throw new Error(result.error || 'Error desconocido del servidor.');
         
        result.date_range_label = selectedDateRangeLabel;
        result.date_range_value = payload.date_range;
         
        renderDashboard(result);
        dashboard.style.display = 'block';
        showNotification('Análisis completado con éxito.', 'success');
    } catch (e) {
        showNotification(`Error: ${e.message}`, 'error');
        console.error(e);
    } finally {
        btn.disabled = false;
        btn.innerHTML = 'Analizar Campaña';
        loader.style.display = 'none';
    }
}

// ==============================================================================
//                         FUNCIONES DE RENDERIZADO
// ==============================================================================

function renderDashboard(data) {
    Object.values(chartInstances).forEach(c => { try { c.destroy(); } catch(e){} });
    chartInstances = {};
    chartDataStore = {};
    const dateLabel = getFormattedDateLabel(data.date_range_label, data.date_range_value);

    addDateTagToCard('metricas-card', dateLabel);
    renderMetricasPrincipales(data.metricas_totales, data.moneda);
    renderizarMetricasHoyAyer(data.metricas_hoy, data.metricas_ayer, data.comparativa, data.moneda);
    addDateTagToCard('ranking-card', dateLabel);
    renderizarRanking(data.ranking_data, data.moneda, document.getElementById('campana-select').value);
    addDateTagToCard('briefing-card', dateLabel);
    renderBriefing(data.analisis_ia);
    addDateTagToCard('graficos-evolucion-card', dateLabel);
    renderGraficos(data.metricas_diarias, data.moneda);
    addDateTagToCard('top-anuncios-card', dateLabel);
    renderTopAnuncios(data.top_anuncios, data.moneda);
}

function renderMetricasPrincipales(m, c) {
    const container = document.getElementById('metricas-grid-container');
    if (!container) return;
    container.innerHTML = `
        \<div class="metrica-card"\>\<h3\>Gasto Total\</h3\>\<div class="valor"\>${formatCurrency(m.spend,c)}\</div\>\</div\>
        \<div class="metrica-card"\>\<h3\>Resultados (Msg)\</h3\>\<div class="valor"\>${(m.messages||0).toLocaleString()}\</div\>\</div\>
        \<div class="metrica-card"\>\<h3\>Costo por Resultado\</h3\>\<div class="valor"\>${formatCurrency(m.cost_per_message,c)}\</div\>\</div\>
        \<div class="metrica-card"\>\<h3\>Impresiones\</h3\>\<div class="valor"\>${(m.impressions||0).toLocaleString()}\</div\>\</div\>
        \<div class="metrica-card"\>\<h3\>CTR\</h3\>\<div class="valor"\>${(m.ctr||0).toFixed(2)}%\</div\>\</div\>
        \<div class="metrica-card"\>\<h3\>CPM\</h3\>\<div class="valor"\>${formatCurrency(m.cpm,c)}\</div\>\</div\>
    `;
}

function renderizarMetricasHoyAyer(h, a, c, m) {
    const hoyContainer = document.getElementById('metricas-hoy-grid-container');
    const ayerContainer = document.getElementById('metricas-ayer-grid-container');
    if (!hoyContainer || !ayerContainer) return;

    const t = (T, v, p) => {
        let trendClass = '', trendSymbol = p >= 0 ? '▲' : '▼';
        if (p !== 0 && typeof p !== 'undefined') {
            trendClass = p > 0 ? 'positive' : 'negative';
            if (T.toLowerCase().includes('costo')) trendClass = p > 0 ? 'negative' : 'positive';
        }
        const comparativaHTML = (typeof p !== 'undefined' && p !== null) ? `\<div class="comparativa ${trendClass}"\>${trendSymbol} ${Math.abs(p).toFixed(1)}%\</div\>` : '';
        return `\<div class="metrica-card"\>\<h3\>${T}\</h3\>\<div class="valor"\>${v}\</div\>${comparativaHTML}\</div\>`;
    };

    hoyContainer.innerHTML = t('Resultados',(h.messages||0).toLocaleString(), c.messages) + t('Costo/Resultado',formatCurrency(h.cost_per_message,m), c.cost_per_message) + t('Gasto',formatCurrency(h.spend,m), c.spend);
    ayerContainer.innerHTML = `\<div class="metrica-card"\>\<h3\>Resultados\</h3\>\<div class="valor"\>${(a.messages||0).toLocaleString()}\</div\>\</div\>` + `\<div class="metrica-card"\>\<h3\>Costo/Resultado\</h3\>\<div class="valor"\>${formatCurrency(a.cost_per_message,m)}\</div\>\</div\>` + `\<div class="metrica-card"\>\<h3\>Gasto\</h3\>\<div class="valor"\>${formatCurrency(a.spend,m)}\</div\>\</div\>`;
}

function renderizarRanking(data, moneda, currentCampaignId) {
    const card = document.getElementById('ranking-card');
    if (!data || !data.campaign_details) {
        if(card) card.style.display = 'none';
        return;
    }
    if(card) card.style.display = 'block';

    const crearPodiumHTML = (campaigns, metric, formatter, isDesc) => {
        const sorted = [...campaigns].sort((a, b) => isDesc ? b[metric] - a[metric] : a[metric] - b[metric]);
        const medals = ['🥇', '🥈', '🥉'];
        return sorted.slice(0, 3).map((camp, index) => `\<li class="podium-item ${camp.id === currentCampaignId ? 'current-campaign' : ''}"\>\<span class="name"\>\<span class="medal"\>${medals[index] || '•'}\</span\> ${camp.name}\</span\>\<span class="value"\>${formatter(camp[metric])}\</span\>\</li\>`).join('');
    };

    const res = data.results;
    if (res) {
        document.getElementById('ranking-results-pos').textContent = `${res.rank || '--'} de ${data.total_campaigns}`;
        document.getElementById('ranking-results-min').textContent = (res.min || 0).toLocaleString();
        document.getElementById('ranking-results-max').textContent = (res.max || 0).toLocaleString();
        let resMarkerPos = res.max > res.min ? ((res.value - res.min) / (res.max - res.min)) * 100 : (res.max > 0 ? 100 : 0);
        document.getElementById('ranking-results-marker').style.left = `calc(${Math.max(0, Math.min(100, resMarkerPos))}% - 2px)`;
        document.getElementById('ranking-results-context').innerHTML = data.total_campaigns > 1 ? (res.rank === 1 ? `🏆 \<strong\>¡Felicidades!\</strong\> Eres el #1 en resultados.` : `Tu valor: \<strong\>${res.value.toLocaleString()}\</strong\>.`) : `📈 Con una sola campaña, tu valor es \<strong\>${res.value.toLocaleString()}\</strong\>.`;
        document.getElementById('ranking-results-podium').innerHTML = crearPodiumHTML(data.campaign_details, 'results', val => val.toLocaleString(), true);
    }
     
    const cpr = data.cost_per_result;
    if (cpr) {
        document.getElementById('ranking-cpr-pos').textContent = `${cpr.rank || '--'} de ${data.total_campaigns}`;
        document.getElementById('ranking-cpr-min').textContent = formatCurrency(cpr.min, moneda);
        document.getElementById('ranking-cpr-max').textContent = formatCurrency(cpr.max, moneda);
        let cprMarkerPos = cpr.max > cpr.min ? ((cpr.value - cpr.min) / (cpr.max - cpr.min)) * 100 : 0;
        document.getElementById('ranking-cpr-marker').style.left = `calc(${Math.max(0, Math.min(100, cprMarkerPos))}% - 2px)`;
        document.getElementById('ranking-cpr-context').innerHTML = data.total_campaigns > 1 ? (cpr.rank === 1 ? `🏆 \<strong\>¡Imbatible!\</strong\> Tienes el costo más bajo.` : `Tu CPR: \<strong\>${formatCurrency(cpr.value, moneda)}\</strong\>.`) : `📈 Con una sola campaña, tu CPR es \<strong\>${formatCurrency(cpr.value, moneda)}\</strong\>.`;
        document.getElementById('ranking-cpr-podium').innerHTML = crearPodiumHTML(data.campaign_details, 'cost_per_result', val => formatCurrency(val, moneda), false);
    }
}

function renderBriefing(analisis) {
    const container = document.getElementById('briefing-content');
    if (container && typeof marked !== 'undefined') container.innerHTML = marked.parse(analisis || "No se pudo generar el análisis.");
}

function renderTopAnuncios(anuncios, moneda) {
    const container = document.getElementById('top-ads-container');
    if (!container) return;
    container.innerHTML = '';
    if (!anuncios || anuncios.length === 0) {
        container.innerHTML = '\<p\>No hay datos de anuncios para mostrar.\</p\>';
        return;
    }
    anuncios.forEach(ad => {
        const textoPreview = (ad.texto_anuncio || 'Texto no disponible.').substring(0, 120) + '...';
        container.innerHTML += `\<div class="ad-card"\>\<div class="ad-image-container"\>\<img src="${ad.imagen || 'https://via.placeholder.com/100'}" alt="Creatividad" class="ad-image"\>\</div\>\<div class="ad-details"\>\<div class="ad-name" title="${ad.nombre_anuncio}"\>${ad.nombre_anuncio}\<span class="ad-id"\>(ID: ${ad.id || 'N/A'})\</span\>\</div\>\<p class="ad-text-preview"\>${textoPreview}\</p\>\<div class="ad-metrics"\>\<div class="ad-metric-item"\>\<span\>Resultados\</span\>\<br\>\<strong\>${(ad.metricas.messages || 0)}\</strong\>\</div\>\<div class="ad-metric-item"\>\<span\>CPR\</span\>\<br\>\<strong\>${formatCurrency(ad.metricas.cost_per_message, moneda)}\</strong\>\</div\>\<div class="ad-metric-item"\>\<span\>Gasto\</span\>\<br\>\<strong\>${formatCurrency(ad.metricas.spend, moneda)}\</strong\>\</div\>\</div\>\</div\>\</div\>`;
    });
}

// ==============================================================================
//             LÓGICA DE GRÁFICOS Y MODAL (UNIFICADA Y CORREGIDA)
// ==============================================================================

function chartOptions(title, isModal, currency) {
    return {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        plugins: {
            legend: { display: isModal, position: 'top', labels: { color: '#f0f6fc' } },
            title: { display: true, text: title, color: '#f0f6fc', font: { size: 16, weight: '500' }, padding: { top: 5, bottom: isModal ? 25 : 10 } },
            subtitle: { display: !isModal, text: 'Haz clic en el gráfico para ampliar', color: '#8b949e', font: { size: 12, style: 'italic' }, padding: { bottom: 15 } },
            tooltip: {
                callbacks: {
                    label: context => {
                        let label = context.dataset.label || '';
                        if (label) label += ': ';
                        if (context.parsed.y !== null) {
                            const isCurrency = label.toLowerCase().includes('costo') || label.toLowerCase().includes('gasto');
                            label += isCurrency ? formatCurrency(context.parsed.y, currency) : context.parsed.y.toLocaleString('es-ES');
                        }
                        return label;
                    }
                }
            }
        },
        scales: {
            x: { ticks: { color: '#8b949e', font: { size: isModal ? 12 : 10 } }, grid: { color: 'rgba(139, 148, 158, 0.2)' } },
            y: {
                beginAtZero: true,
                ticks: { color: '#8b949e', font: { size: isModal ? 12 : 10 } },
                grid: { color: 'rgba(139, 148, 158, 0.2)' },
            }
        }
    };
}

function renderGraficos(dailyData, currency) {
    const labels = Object.keys(dailyData).sort();

    const createChart = (canvasId, type, title, data, color, fill, datasetLabel) => {
        const canvas = document.getElementById(canvasId);
        if (!canvas) return;
        const ctx = canvas.getContext('2d');

        const dataset = {
            label: datasetLabel, data: data, borderColor: color, tension: 0.4, fill: fill,
            backgroundColor: fill ? (color + '80') : color,
            borderWidth: 2, pointRadius: 2, pointBackgroundColor: color
        };

        chartDataStore[canvasId] = { type, title, currency, labels, dataset };

        if (chartInstances[canvasId]) chartInstances[canvasId].destroy();
        
        chartInstances[canvasId] = new Chart(ctx, {
            type: type,
            data: { labels: labels, datasets: [dataset] },
            options: chartOptions(title, false, currency)
        });

        canvas.parentElement.onclick = () => openModalWithChart(canvasId);
    };

    createChart('grafico-resultados', 'line', 'Resultados por Día', labels.map(date => Number(dailyData[date]?.messages) || 0), '#36A2EB', true, 'Resultados');
    createChart('grafico-cpr', 'line', `Costo por Resultado (${currency})`, labels.map(date => Number(dailyData[date]?.cost_per_message) || 0), '#E0E0E0', false, 'Costo por Resultado');
    createChart('grafico-gasto', 'bar', `Gasto Diario (${currency})`, labels.map(date => Number(dailyData[date]?.spend) || 0), 'rgba(54, 162, 235, 0.7)', false, 'Gasto Diario');
}

function openModalWithChart(canvasId) {
    const modal = document.getElementById('chart-modal');
    if (!modal) return;
    
    const storedData = chartDataStore[canvasId];
    if (!storedData) return;

    modal.classList.add('is-visible');
    
    setTimeout(() => {
        if (modalChartInstance) modalChartInstance.destroy();
        
        const canvas = document.getElementById('modal-chart-canvas');
        if (!canvas) return;
        const ctx = canvas.getContext('2d');
        
        const dataForModal = JSON.parse(JSON.stringify(storedData));
        
        // CORRECCIÓN ESENCIAL: Si es un gráfico de área, el degradado debe
        // ser recreado para el NUEVO canvas del modal. No se puede copiar.
        if (dataForModal.type === 'line' && dataForModal.dataset.fill === true) {
            const gradient = ctx.createLinearGradient(0, 0, 0, canvas.getBoundingClientRect().height);
            gradient.addColorStop(0, 'rgba(46, 167, 249, 0.5)'); // Usamos los colores de la paleta
            gradient.addColorStop(1, 'rgba(46, 167, 249, 0.05)');
            dataForModal.dataset.backgroundColor = gradient;
        }

        modalChartInstance = new Chart(ctx, {
            type: dataForModal.type,
            data: {
                labels: dataForModal.labels,
                datasets: [dataForModal.dataset]
            },
            options: chartOptions(dataForModal.title, true, dataForModal.currency)
        });
    }, 100); // Delay para asegurar que el modal es visible y tiene dimensiones
}

function closeChartModal() {
    const modal = document.getElementById('chart-modal');
    if(modal) modal.classList.remove('is-visible');
    
    if (modalChartInstance) {
        modalChartInstance.destroy();
        modalChartInstance = null;
    }
}

// ==============================================================================
//                         LÓGICA MODAL HISTÓRICO
// ==============================================================================

async function openHistoricalModal() {
    const modal = document.getElementById('historical-analysis-modal');
    if(!modal) return;
    modal.classList.add('is-visible');
    if (historicalDataStore) return;

    const content = document.getElementById('historical-view-content');
    const loader = document.getElementById('historical-view-loader');
    content.style.display = 'none';
    loader.style.display = 'flex';

    try {
        const campaign_id = document.getElementById('campana-select').value;
        if (!campaign_id) throw new Error("Seleccione una campaña primero para ver su historial.");

        const response = await fetch('/get_comparative_metrics', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ campaign_id: campaign_id, cuenta_id: document.getElementById('cuenta-select').value })
        });
        if (!response.ok) {
            const errData = await response.json();
            throw new Error(errData.error || 'Error al cargar datos comparativos.');
        }
         
        historicalDataStore = await response.json();
        loader.style.display = 'none';
        content.style.display = 'block';
         
        document.querySelector('#historical-analysis-modal .period-btn.active')?.classList.remove('active');
        document.querySelector(`#historical-analysis-modal .period-btn[data-period='30']`)?.classList.add('active');
        renderHistoricalData(30);

    } catch (error) {
        showNotification(error.message, 'error');
        console.error(error);
        closeHistoricalModal();
    }
}

function closeHistoricalModal() {
    document.getElementById('historical-analysis-modal')?.classList.remove('is-visible');
}

function resetHistoricalView() {
    historicalDataStore = null;
    if (historicalChartInstance) {
        historicalChartInstance.destroy();
        historicalChartInstance = null;
    }
}

function renderHistoricalData(period) {
    if (!historicalDataStore?.data) return;
    const periodData = historicalDataStore.data[`period_${period}`];
    if (!periodData) {
        showNotification('No hay datos disponibles para este período.', 'warning');
        return;
    };
     
    const header = document.getElementById('historical-trend-header');
    if(header) header.textContent = `Tendencia (vs. los ${period} días anteriores)`;
     
    renderHistoricalSummaryTable(periodData.summary, historicalDataStore.moneda);
    renderHistoricalChart(periodData.chart_data, historicalDataStore.moneda);
}

function renderHistoricalSummaryTable(summaryData, moneda) {
    const tbody = document.getElementById('comparison-summary-tbody');
    if(!tbody) return;
    tbody.innerHTML = '';

    const formatTrend = (trendValue, isCost) => {
        if (Math.abs(trendValue) < 0.1) return `\<span class="trend-indicator neutral"\>(Sin cambios)\</span\>`;
        const trendClass = trendValue > 0 ? (isCost ? 'negative' : 'positive') : (isCost ? 'positive' : 'negative');
        const trendSymbol = trendValue > 0 ? '▲' : '▼';
        return `\<span class="trend-indicator ${trendClass}"\>${trendSymbol} ${Math.abs(trendValue).toFixed(1)}%\</span\>`;
    };
    const rows = [
        { label: 'Mensajes Obtenidos', value: summaryData.leads.value.toLocaleString(), trend: formatTrend(summaryData.leads.trend, false) },
        { label: 'Costo Promedio / Mensaje', value: formatCurrency(summaryData.cpr.value, moneda), trend: formatTrend(summaryData.cpr.trend, true) },
        { label: 'Gasto Total', value: formatCurrency(summaryData.spend.value, moneda), trend: formatTrend(summaryData.spend.trend, true) }
    ];
    rows.forEach(row => {
        tbody.innerHTML += `\<tr\>\<td\>${row.label}\</td\>\<td\>${row.value}\</td\>\<td\>${row.trend}\</td\>\</tr\>`;
    });
}

function renderHistoricalChart(chartData, moneda) {
    const ctx = document.getElementById('historical-chart-canvas')?.getContext('2d');
    if(!ctx) return;

    if (historicalChartInstance) historicalChartInstance.destroy();
     
    historicalChartInstance = new Chart(ctx, {
        type: 'line',
        data: {
            labels: chartData.labels,
            datasets: [
                { label: `Mensajes`, data: chartData.leads, borderColor: '#2ea7f9', backgroundColor: '#2ea7f933', fill: true, yAxisID: 'y', tension: 0.3 },
                { label: `Gasto (${moneda})`, data: chartData.spend, borderColor: '#28a745', yAxisID: 'y1', tension: 0.3 },
                { label: `Costo/Mensaje (${moneda})`, data: chartData.cpr, borderColor: '#E0E0E0', yAxisID: 'y1', tension: 0.3 }
            ]
        },
        options: {
            responsive: true, maintainAspectRatio: false, interaction: { mode: 'index', intersect: false },
            plugins: { legend: { position: 'top', labels: { color: '#f0f6fc' } } },
            scales: {
                x: { ticks: { color: '#8b949e' }, grid: { color: '#30363d' } },
                y: { type: 'linear', display: true, position: 'left', title: { display: true, text: 'Mensajes', color: '#f0f6fc' }, ticks: { color: '#f0f6fc' }, grid: { color: '#3036d' } },
                y1: { type: 'linear', display: true, position: 'right', title: { display: true, text: `Costo (${moneda})`, color: '#f0f6fc' }, ticks: { color: '#f0f6fc' }, grid: { drawOnChartArea: false } }
            }
        }
    });
}

// ==============================================================================
//                         FUNCIONES UTILITARIAS
// ==============================================================================

function getFormattedDateLabel(label, value) {
    if (label && label !== "Personalizado") return label;
    if (!value) return "Rango personalizado";
    const [start, end] = value.split(' - ');
    return `${moment(start).format('D MMM')} - ${moment(end).format('D MMM')}`;
}

function showNotification(m, t) {
    const a = document.getElementById('notification-area');
    if (!a) return;
    const n = document.createElement('div');
    n.className = `notification ${t}`;
    n.textContent = m;
    a.innerHTML = '';
    a.appendChild(n);
    setTimeout(() => { n.style.opacity = '1'; }, 10);
    setTimeout(() => {
        n.style.opacity = '0';
        setTimeout(() => n.remove(), 500);
    }, 5000);
}

function formatCurrency(v, s) {
    return (s || '') + (Number(v) || 0).toLocaleString('es-PE', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function addDateTagToCard(cardId, dateLabel) {
    const cardTitle = document.querySelector(`#${cardId} h2`);
    if (!cardTitle) return;
    let tag = cardTitle.querySelector('.date-tag');
    if (!tag) {
        tag = document.createElement('div');
        tag.className = 'date-tag';
        cardTitle.appendChild(tag);
    }
    tag.textContent = dateLabel;
}