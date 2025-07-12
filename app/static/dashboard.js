// Variable global para las instancias de los gráficos del dashboard
let chartInstances = {};
// Variable para la instancia del único gráfico en la modal
let modalChartInstance = null;

document.addEventListener('DOMContentLoaded', function() {
    // Muestra el contenido de la app y oculta el loader inicial
    document.getElementById('app-content').style.display = 'block';
    document.getElementById('loader').style.display = 'none';

    if (ERROR_MESSAGE) {
        showNotification(ERROR_MESSAGE, 'error');
    }
    
    // Configuración inicial de los componentes
    setupControlPanel();
    setupDatePicker();
    addEventListeners();
    setupModalEventListeners();
});

// --- FUNCIONES DE CONFIGURACIÓN INICIAL ---

function setupControlPanel() {
    const cuentaSelect = document.getElementById('cuenta-select');
    cuentaSelect.innerHTML = '';
    if (CUENTAS && CUENTAS.length > 0) {
        cuentaSelect.innerHTML = '<option value="">Seleccione una cuenta...</option>';
        CUENTAS.forEach(c => {
            const opt = document.createElement('option');
            opt.value = c.id;
            opt.textContent = `${c.name} (${c.id})`;
            cuentaSelect.appendChild(opt);
        });
        cuentaSelect.disabled = false;
    } else {
        cuentaSelect.innerHTML = ERROR_MESSAGE ? '<option>Error al cargar</option>' : '<option>No hay cuentas</option>';
        cuentaSelect.disabled = true;
    }
}

function setupDatePicker() {
    $('#fecha').daterangepicker({
        ranges: {
           'Hoy': [moment(), moment()],
           'Ayer': [moment().subtract(1, 'days'), moment().subtract(1, 'days')],
           'Últimos 7 Días': [moment().subtract(6, 'days'), moment()],
           'Últimos 30 Días': [moment().subtract(29, 'days'), moment()],
           'Este Mes': [moment().startOf('month'), moment().endOf('month')],
           'Mes Pasado': [moment().subtract(1, 'month').startOf('month'), moment().subtract(1, 'month').endOf('month')]
        },
        "locale": {
            "format": "YYYY-MM-DD", "separator": " - ", "applyLabel": "Aplicar", "cancelLabel": "Cancelar", "fromLabel": "Desde", "toLabel": "Hasta", "customRangeLabel": "Personalizado", "daysOfWeek": ["Do", "Lu", "Ma", "Mi", "Ju", "Vi", "Sa"], "monthNames": ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"],
        },
        "alwaysShowCalendars": true, "startDate": moment().subtract(6, 'days'), "endDate": moment()
    }, validateForm);
}

function addEventListeners() {
    document.getElementById('cuenta-select').addEventListener('change', (e) => {
        const accountId = e.target.value;
        const campanaSelect = document.getElementById('campana-select');
        campanaSelect.innerHTML = '<option>Seleccione cuenta</option>';
        campanaSelect.disabled = true;
        if (accountId) cargarCampanas(accountId);
        validateForm();
    });

    ['campana-select', 'descripcion-negocio', 'ubicacion-pais'].forEach(id => {
        const element = document.getElementById(id);
        element.addEventListener('change', validateForm);
        element.addEventListener('keyup', validateForm);
    });

    document.getElementById('analizar-btn').addEventListener('click', analizarCampana);
}

/**
 * <<< LÓGICA DE LA MODAL - INICIO (VERSIÓN CORREGIDA) >>>
 */
function setupModalEventListeners() {
    const modal = document.getElementById('chart-modal');
    const closeButton = document.querySelector('.close-button');

    closeButton.onclick = function() { closeModal(); }
    window.onclick = function(event) { if (event.target == modal) { closeModal(); } }
}

function closeModal() {
    const modal = document.getElementById('chart-modal');
    modal.style.display = "none";
    if (modalChartInstance) {
        modalChartInstance.destroy();
        modalChartInstance = null;
    }
}

/**
 * Abre la modal y dibuja una copia del gráfico seleccionado.
 * Este método evita JSON.stringify para manejar correctamente gradientes y funciones.
 * @param {Chart} chartInstance La instancia del gráfico original que se quiere ampliar.
 * @param {string} moneda El símbolo de la moneda para formatear los tooltips.
 */
function openModalWithChart(chartInstance, moneda) {
    const modal = document.getElementById('chart-modal');
    const originalConfig = chartInstance.config; // Obtenemos la config original

    // 1. Destruye cualquier gráfico previo en la modal
    if (modalChartInstance) {
        modalChartInstance.destroy();
        modalChartInstance = null;
    }

    // 2. Extraemos el título y el tipo del gráfico original
    const originalTitle = originalConfig.options.plugins.title.text;
    const chartType = originalConfig.type;
    
    // 3. Creamos una nueva configuración para la modal
    const modalConfig = {
        type: chartType,
        // Reutilizamos directamente el objeto 'data'. Es seguro porque no contiene funciones.
        data: originalConfig.data, 
        // Generamos un set de opciones NUEVO, específico para la modal
        options: chartOptions(originalTitle, true) 
    };

    // 4. Re-aplicamos el formateo de moneda en los tooltips de la modal (tu lógica actual es perfecta)
    modalConfig.options.plugins.tooltip.callbacks = {
        label: function(context) {
            let label = context.dataset.label || '';
            if (label) { label += ': '; }
            if (context.parsed.y !== null) {
                if (context.dataset.label.toLowerCase().includes('costo') || context.dataset.label.toLowerCase().includes('gasto')) {
                    label += formatCurrency(context.parsed.y, moneda);
                } else {
                    label += context.parsed.y.toLocaleString('es-ES');
                }
            }
            return label;
        }
    };
    
    // 5. HACEMOS VISIBLE LA MODAL ANTES DE DIBUJAR
    // Esto es crucial para que el canvas tenga dimensiones.
    modal.style.display = "flex";

    const modalCanvas = document.getElementById('modal-chart-canvas');
    const modalCanvasCtx = modalCanvas.getContext('2d');

    // 6. [FIX CLAVE] Si el gráfico original era el de área (Resultados),
    // debemos RECREAR el gradiente para el nuevo canvas de la modal.
    if (chartType === 'line' && originalConfig.data.datasets[0].fill === true) {
        const gradient = modalCanvasCtx.createLinearGradient(0, 0, 0, modalCanvas.clientHeight);
        gradient.addColorStop(0, 'rgba(54, 162, 235, 0.5)');
        gradient.addColorStop(1, 'rgba(54, 162, 235, 0.05)');
        // Aplicamos el nuevo gradiente a la configuración de la modal
        modalConfig.data.datasets[0].backgroundColor = gradient;
    }
    
    // 7. Creamos la nueva instancia del gráfico en la modal.
    modalChartInstance = new Chart(modalCanvasCtx, modalConfig);
}
/**
 * <<< LÓGICA DE LA MODAL - FIN >>>
 */

function validateForm() {
    const cuenta = document.getElementById('cuenta-select').value;
    const campana = document.getElementById('campana-select').value;
    const fecha = document.getElementById('fecha').value;
    const negocio = document.getElementById('descripcion-negocio').value;
    const pais = document.getElementById('ubicacion-pais').value;
    document.getElementById('analizar-btn').disabled = !(cuenta && campana && fecha && negocio && pais);
}

async function cargarCampanas(accountId) {
    const campanaSelect = document.getElementById('campana-select');
    campanaSelect.disabled = true;
    campanaSelect.innerHTML = '<option>Cargando campañas...</option>';
    try {
        const response = await fetch(`/get_campaigns/${accountId}`);
        if (!response.ok) throw new Error('Error del servidor.');
        const campaigns = await response.json();
        campanaSelect.innerHTML = '';
        if (campaigns && campaigns.length > 0) {
            campanaSelect.innerHTML = '<option value="">Seleccione una campaña...</option>';
            campaigns.forEach(c => {
                const opt = new Option(c.name, c.id);
                campanaSelect.appendChild(opt);
            });
            campanaSelect.disabled = false;
        } else {
            campanaSelect.innerHTML = '<option>No hay campañas activas</option>';
        }
    } catch (error) {
        campanaSelect.innerHTML = '<option>Error al cargar</option>';
        showNotification('No se pudieron cargar las campañas.', 'error');
    }
}

async function analizarCampana() {
    const btn = document.getElementById('analizar-btn');
    const loader = document.getElementById('loader');
    const dashboard = document.getElementById('dashboard-container');

    btn.disabled = true;
    btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Analizando...';
    loader.style.display = 'flex';
    dashboard.style.display = 'none';

    const payload = {
        cuenta_id: document.getElementById('cuenta-select').value,
        campaign_id: document.getElementById('campana-select').value,
        date_range: document.getElementById('fecha').value,
        descripcion_negocio: document.getElementById('descripcion-negocio').value,
        pais: document.getElementById('ubicacion-pais').value,
    };

    try {
        const response = await fetch('/analizar_campana', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const result = await response.json();
        if (!response.ok) throw new Error(result.error || 'Error desconocido.');
        
        renderDashboard(result);
        dashboard.style.display = 'block';
        showNotification('Análisis completado con éxito.', 'success');
    } catch (error) {
        showNotification(`Error: ${error.message}`, 'error');
    } finally {
        btn.disabled = false;
        btn.innerHTML = 'Analizar Campaña';
        loader.style.display = 'none';
    }
}

function showNotification(message, type = 'info') {
    const notificationArea = document.getElementById('notification-area');
    const notification = document.createElement('div');
    notification.className = `notification ${type === 'error' ? 'error' : 'success'}`;
    notification.textContent = message;
    notificationArea.innerHTML = '';
    notificationArea.appendChild(notification);
    setTimeout(() => {
        notification.style.transition = 'opacity 0.5s ease';
        notification.style.opacity = '0';
        setTimeout(() => notification.remove(), 500);
    }, 5000);
}

function renderDashboard(data) {
    Object.values(chartInstances).forEach(chart => chart.destroy());
    chartInstances = {};
    renderMetricas(data.metricas_totales, data.moneda);
    renderBriefing(data.analisis_ia);
    renderGraficos(data.metricas_diarias, data.moneda);
    renderTopAds(data.top_anuncios, data.moneda);
}

function formatCurrency(value, currencySymbol) {
    const numberValue = Number(value) || 0;
    return `${currencySymbol}${numberValue.toLocaleString('es-ES', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function renderMetricas(metricas, moneda) {
    const container = document.getElementById('metricas-grid-container');
    container.innerHTML = `
        <div class="metric"><div class="metric-label">Gasto Total</div><div class="metric-value">${formatCurrency(metricas.spend, moneda)}</div></div>
        <div class="metric"><div class="metric-label">Resultados (Msg)</div><div class="metric-value">${(metricas.messages || 0).toLocaleString('es-ES')}</div></div>
        <div class="metric"><div class="metric-label">Costo por Resultado</div><div class="metric-value">${formatCurrency(metricas.cost_per_message, moneda)}</div></div>
        <div class="metric"><div class="metric-label">CTR</div><div class="metric-value">${(metricas.ctr || 0).toFixed(2)}%</div></div>
    `;
}

function renderBriefing(analisis) {
    document.getElementById('briefing-content').innerHTML = marked.parse(analisis || "No se pudo generar el análisis.");
}

function chartOptions(title, isModal = false) {
    const textColor = '#E0E0E0';
    const mutedTextColor = '#a0a0a0';
    const gridColor = 'rgba(255, 255, 255, 0.1)';

    return {
        responsive: true,
        maintainAspectRatio: false,
        animation: {
            duration: isModal ? 500 : 1000 // Animación más rápida en la modal
        },
        interaction: { mode: 'index', intersect: false },
        plugins: {
            legend: { display: isModal, position: 'top', labels: { color: textColor, font: {size: 14} } },
            title: {
                display: true,
                text: title,
                color: textColor,
                font: { size: isModal ? 20 : 16, weight: '500' },
                padding: { top: 10, bottom: isModal ? 25 : 10 }
            },
            subtitle: {
                display: !isModal,
                text: 'Haz clic para ampliar',
                color: '#888',
                font: { size: 12, style: 'italic' },
                padding: { bottom: 15 }
            },
            tooltip: {
                backgroundColor: 'rgba(13, 17, 23, 0.9)',
                borderColor: 'rgba(255, 255, 255, 0.2)',
                borderWidth: 1,
                titleFont: { size: 14, weight: 'bold' },
                bodyFont: { size: 12 },
                padding: 12,
                cornerRadius: 6,
            }
        },
        scales: {
            y: { beginAtZero: true, ticks: { color: mutedTextColor, font: { size: 12 } }, grid: { color: gridColor, borderColor: gridColor } },
            x: { ticks: { color: mutedTextColor, font: { size: 12 } }, grid: { display: false } }
        }
    };
}

function renderGraficos(metricasDiarias, moneda) {
    const labels = Object.keys(metricasDiarias).sort();
    const resultadosData = labels.map(l => metricasDiarias[l].messages || 0);
    const cprData = labels.map(l => metricasDiarias[l].cost_per_message || 0);
    const gastoData = labels.map(l => metricasDiarias[l].spend || 0);

    const tooltipCallbacks = {
        callbacks: {
            label: function(context) {
                let label = context.dataset.label || '';
                if (label) label += ': ';
                if (context.parsed.y !== null) {
                    if (context.dataset.label.toLowerCase().includes('costo') || context.dataset.label.toLowerCase().includes('gasto')) {
                        label += formatCurrency(context.parsed.y, moneda);
                    } else {
                        label += context.parsed.y.toLocaleString('es-ES');
                    }
                }
                return label;
            }
        }
    };

    // 1. Gráfico de Resultados
    const ctxResultados = document.getElementById('grafico-resultados').getContext('2d');
    const gradientResultados = ctxResultados.createLinearGradient(0, 0, 0, 250);
    gradientResultados.addColorStop(0, 'rgba(54, 162, 235, 0.5)');
    gradientResultados.addColorStop(1, 'rgba(54, 162, 235, 0.05)');
    const opcionesResultados = chartOptions('Resultados por Día');
    opcionesResultados.plugins.tooltip = {...opcionesResultados.plugins.tooltip, ...tooltipCallbacks};
    
    chartInstances.resultados = new Chart(ctxResultados, {
        type: 'line',
        data: { labels, datasets: [{ label: 'Resultados', data: resultadosData, borderColor: '#36A2EB', backgroundColor: gradientResultados, tension: 0.4, fill: true, borderWidth: 2, pointRadius: 0 }] },
        options: opcionesResultados
    });
    ctxResultados.canvas.onclick = () => openModalWithChart(chartInstances.resultados, moneda);

    // 2. Costo por Resultado
    const ctxCpr = document.getElementById('grafico-cpr').getContext('2d');
    const opcionesCpr = chartOptions(`Costo por Resultado (${moneda})`);
    opcionesCpr.plugins.tooltip = {...opcionesCpr.plugins.tooltip, ...tooltipCallbacks};

    chartInstances.cpr = new Chart(ctxCpr, {
        type: 'line',
        data: { labels, datasets: [{ label: 'Costo por Resultado', data: cprData, borderColor: '#E0E0E0', tension: 0.4, fill: false, borderWidth: 2, pointRadius: 0 }] },
        options: opcionesCpr
    });
    ctxCpr.canvas.onclick = () => openModalWithChart(chartInstances.cpr, moneda);

    // 3. Gasto Diario
    const ctxGasto = document.getElementById('grafico-gasto').getContext('2d');
    const opcionesGasto = chartOptions(`Gasto Diario (${moneda})`);
    opcionesGasto.plugins.tooltip = {...opcionesGasto.plugins.tooltip, ...tooltipCallbacks};
    
    chartInstances.gasto = new Chart(ctxGasto, {
        type: 'bar',
        data: { labels, datasets: [{ label: 'Gasto Diario', data: gastoData, backgroundColor: 'rgba(54, 162, 235, 0.7)', borderColor: '#36A2EB', borderWidth: 1, borderRadius: 3 }] },
        options: opcionesGasto
    });
    ctxGasto.canvas.onclick = () => openModalWithChart(chartInstances.gasto, moneda);
}

function renderTopAds(anuncios, moneda) {
    const container = document.getElementById('top-ads-grid');
    container.innerHTML = '';

    if (!anuncios || anuncios.length === 0) {
        container.innerHTML = '<p style="color: var(--text-medium); text-align: center; grid-column: 1 / -1;">No se encontraron datos de anuncios para analizar.</p>';
        return;
    }

    anuncios.forEach(ad => {
        container.innerHTML += `
            <div class="top-ad-card">
                <img src="${ad.imagen}" alt="Creativo del anuncio" onerror="this.onerror=null;this.src='https://via.placeholder.com/400?text=Imagen+no+disponible';">
                <div class="top-ad-content">
                    <div class="top-ad-metrics">
                        <div class="top-ad-metric"><div class="metric-label">Gasto</div><div class="metric-value">${formatCurrency(ad.metricas.spend, moneda)}</div></div>
                        <div class="top-ad-metric"><div class="metric-label">Resultados</div><div class="metric-value">${(ad.metricas.messages || 0).toLocaleString()}</div></div>
                        <div class="top-ad-metric"><div class="metric-label">CPR</div><div class="metric-value">${formatCurrency(ad.metricas.cost_per_message, moneda)}</div></div>
                    </div>
                    <div class="top-ad-analysis">${marked.parse(ad.analisis_copy || '')}</div>
                    <div class="top-ad-id">ID: ${ad.id || 'N/A'}</div>
                </div>
            </div>`;
    });
}