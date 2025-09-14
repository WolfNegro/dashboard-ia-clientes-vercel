// app/static/js/dashboard.js

(() => {
  const AD_ACCOUNTS = Array.isArray(window.AD_ACCOUNTS) ? window.AD_ACCOUNTS : [];
  let currentPreset = "hoy";
  let currentSince = "";
  let currentUntil = "";
  let currentCampaign = null;

  // --------- Helpers DOM ----------
  const $ = (sel) => document.querySelector(sel);
  const kpiSpendTotal       = $("#kpiSpendTotal");
  const kpiResultsTotal     = $("#kpiResultsTotal");
  const kpiCPR              = $("#kpiCPR");
  const kpiYesterdayResults = $("#kpiYesterdayResults");
  const kpiTodaySpend       = $("#kpiTodaySpend");

  const sumSpendEl   = $("#sumSpend");
  const sumResultsEl = $("#sumResults");
  const sumCPREl     = $("#sumCPR");

  const listEl   = $("#campaignList");
  const thumbsEl = $("#thumbs");

  const btns = Array.from(document.querySelectorAll(".btn-range"));
  const btnApply = $("#btnApply");
  const inpSince = $("#dateSince");
  const inpUntil = $("#dateUntil");

  // --------- UI: estado activo ----------
  function setActivePreset(preset) {
    btns.forEach(b => {
      const isActive = b.dataset.preset === preset;
      b.classList.toggle("active", isActive);
      b.setAttribute("aria-pressed", isActive ? "true" : "false");
    });
  }

  // --------- Fetch helpers ----------
  async function fetchJSON(url) {
    const r = await fetch(url);
    return r.json();
  }

  function buildQuery(extra = {}) {
    const q = new URLSearchParams();
    q.set("date_preset", currentPreset);
    if (currentPreset === "rango") {
      if (currentSince) q.set("since", currentSince);
      if (currentUntil) q.set("until", currentUntil);
    }
    Object.entries(extra).forEach(([k, v]) => q.set(k, v));
    return q.toString();
  }

  // --------- Render KPI ----------
  function renderKpisFromCampaigns(rows) {
    const spend = rows.reduce((a, r) => a + (Number(r.spend) || 0), 0);
    const res   = rows.reduce((a, r) => a + (Number(r.results) || 0), 0);
    const cpr   = res > 0 ? (spend / res) : 0;

    kpiSpendTotal.textContent   = `S/ ${spend.toFixed(2)}`;
    kpiResultsTotal.textContent = `${res}`;
    kpiCPR.textContent          = `S/ ${cpr.toFixed(2)}`;

    // Hoy: si el preset es hoy, lo mostramos; si no, dejamos guión.
    kpiTodaySpend.textContent   = (currentPreset === "hoy") ? `S/ ${spend.toFixed(2)}` : "—";

    // Resumen chips
    sumSpendEl.textContent   = `S/ ${spend.toFixed(2)}`;
    sumResultsEl.textContent = `${res}`;
    sumCPREl.textContent     = `S/ ${cpr.toFixed(2)}`;
  }

  // --------- Render campañas ----------
  function renderCampaigns(rows) {
    listEl.innerHTML = "";
    rows.forEach(c => {
      const item = document.createElement("button");
      item.className = "campaign-card";
      item.innerHTML = `
        <div class="title">${c.name || c.id}</div>
        <div class="chip-bar">
          <span class="metric-chip">S/ ${Number(c.spend || 0).toFixed(2)}</span>
          <span class="metric-chip">R: ${Number(c.results || 0)}</span>
          <span class="metric-chip">CPR: S/ ${Number(c.cpr || 0).toFixed(2)}</span>
        </div>
      `;
      item.addEventListener("click", () => {
        currentCampaign = c.id;
        loadThumbsForCampaign(c.id);
      });
      listEl.appendChild(item);
    });

    // Seleccionar automáticamente la primera campaña
    if (rows.length) {
      currentCampaign = rows[0].id;
      loadThumbsForCampaign(rows[0].id);
    } else {
      currentCampaign = null;
      thumbsEl.innerHTML = "";
    }
  }

  // --------- Render miniaturas ----------
  function renderThumbs(rows) {
    thumbsEl.innerHTML = "";
    rows.forEach(ad => {
      const card = document.createElement("div");
      card.className = "thumb-card ad-thumb";
      card.innerHTML = `
        <div class="thumb-img">
          <img src="${ad.thumbnail_url || "/static/img/placeholder.png"}" alt="${(ad.name||"Anuncio")}" />
        </div>
        <div class="thumb-info">
          <div class="name">${ad.name || ad.id}</div>
          <div class="chip-bar">
            <span class="metric-chip">S/ ${Number(ad.spend||0).toFixed(2)}</span>
            <span class="metric-chip">R: ${Number(ad.results||0)}</span>
            <span class="metric-chip">CPR: S/ ${Number(ad.cpr||0).toFixed(2)}</span>
          </div>
        </div>
      `;
      thumbsEl.appendChild(card);
    });
  }

  // --------- Cargas ----------
  async function loadCampaignsAndKpis() {
    // Tomamos la PRIMERA cuenta del cliente (como venías usando)
    const acc = AD_ACCOUNTS[0];
    if (!acc) {
      renderKpisFromCampaigns([]);
      renderCampaigns([]);
      return;
    }
    const q = buildQuery();
    const data = await fetchJSON(`/get_campaigns_active/${encodeURIComponent(acc)}?${q}`);
    const rows = (data && data.data) || [];
    renderKpisFromCampaigns(rows);
    renderCampaigns(rows);

    // Carga “Ayer” (si estamos en hoy, lo calculamos aparte para mostrar ese KPI)
    try {
      const qYesterday = new URLSearchParams({ date_preset: "ayer" }).toString();
      const yd = await fetchJSON(`/get_campaigns_active/${encodeURIComponent(acc)}?${qYesterday}`);
      const yrows = (yd && yd.data) || [];
      const yres = yrows.reduce((a, r) => a + (Number(r.results) || 0), 0);
      kpiYesterdayResults.textContent = `${yres}`;
    } catch (e) {
      kpiYesterdayResults.textContent = "—";
    }
  }

  async function loadThumbsForCampaign(campaignId) {
    const q = buildQuery();
    const data = await fetchJSON(`/get_ads_by_campaign/${encodeURIComponent(campaignId)}?${q}`);
    renderThumbs((data && data.data) || []);
  }

  // --------- Eventos ----------
  btns.forEach(b => {
    b.addEventListener("click", () => {
      const preset = b.dataset.preset;
      currentPreset = preset;
      setActivePreset(preset);

      // Mostrar/ocultar inputs de rango y botón aplicar
      const isRange = preset === "rango";
      inpSince.style.display = isRange ? "" : "none";
      inpUntil.style.display = isRange ? "" : "none";
      btnApply.style.display = isRange ? "" : "none";

      if (!isRange) {
        // Carga inmediata (sin botón aplicar)
        loadCampaignsAndKpis();
      }
    });
  });

  btnApply?.addEventListener("click", () => {
    currentSince = inpSince.value || "";
    currentUntil = inpUntil.value || "";
    loadCampaignsAndKpis();
  });

  // --------- Init ----------
  function init() {
    // Marcar hoy como seleccionado y cargar
    setActivePreset("hoy");
    currentPreset = "hoy";
    currentSince = "";
    currentUntil = "";

    // ocultar inputs de rango al inicio
    inpSince.style.display = "none";
    inpUntil.style.display = "none";

    loadCampaignsAndKpis();
  }

  document.addEventListener("DOMContentLoaded", init);
})();
/* === FIX KPI "Hoy": debe mostrar RESULTADOS, no gasto === */
(function () {
  const $ = s => document.querySelector(s);
  const CLIENT_ID = window.CLIENT_ID;
  const toInt = n => String(Math.round(Number(n || 0)));

  async function setTodayResults() {
    try {
      const res = await fetch('/api/overview?date_preset=today');
      const json = await res.json();
      const item = (json.data || []).find(x => x.client_id === CLIENT_ID);
      const todayResults = item ? item.results : 0;

      // Soporta ambos IDs/atributos por compatibilidad con tu HTML
      const el =
        document.getElementById('kpiToday') ||
        document.querySelector('[data-kpi="today"]') ||
        document.querySelector('#todayValue');

      if (el) el.textContent = toInt(todayResults);
    } catch (e) {
      // silencioso
    }
  }

  // 1) Primera carga
  setTodayResults();

  // 2) Reaplicar cuando cambie el preset (Hoy, Ayer, 7 días, etc.)
  document.addEventListener('click', ev => {
    const btn = ev.target.closest('[data-preset]');
    if (btn) setTimeout(setTodayResults, 0);
  });
})();
/* === FIX: KPI "Hoy" debe mostrar RESULTADOS (no gasto) === */
(function () {
  const CLIENT_ID = window.CLIENT_ID || '';

  async function fetchTodayResults() {
    try {
      const r = await fetch('/api/overview?date_preset=today', { cache: 'no-store' });
      const j = await r.json();
      const item = (j.data || []).find(x => x.client_id === CLIENT_ID);
      return item ? Number(item.results || 0) : 0;
    } catch {
      return 0;
    }
  }

  function paintToday(val) {
    // Encuentra el card cuyo título sea exactamente "Hoy"
    const titleEl = Array.from(document.querySelectorAll('h1,h2,h3,h4,strong,span,div'))
      .find(el => el.textContent.trim().toLowerCase() === 'hoy');
    if (!titleEl) return;

    const card = titleEl.closest('.card') || titleEl.parentElement;
    let valueEl =
      card.querySelector('[data-role="value"]') ||
      card.querySelector('.kpi-value,.kpi-number,.kpi-amount,.value,.num,.big') ||
      card.querySelector('strong,b,h2');

    if (!valueEl) return;

    valueEl.textContent = String(Math.round(val || 0)); // solo número (resultados)
  }

  async function refreshToday() {
    const results = await fetchTodayResults();
    paintToday(results);
  }

  // 1) Primera carga
  refreshToday();

  // 2) Cuando cambias “Hoy / Ayer / 7 días …” o aplicas rango
  document.addEventListener('click', (ev) => {
    if (ev.target.closest('[data-preset]') || ev.target.closest('#applyRange')) {
      refreshToday();
    }
  });
})();
