// app/static/js/dashboard.js

(function () {
  // ---------- helpers ----------
  const el = (id) => document.getElementById(id);
  const $ = (sel, ctx = document) => ctx.querySelector(sel);
  const $$ = (sel, ctx = document) => Array.from(ctx.querySelectorAll(sel));
  const fmtSoles = (v) => `S/ ${Number(v || 0).toFixed(2)}`;

  // pool de concurrencia para no saturar
  function pLimit(limit) {
    let running = 0, queue = [];
    const runNext = () => {
      if (running >= limit || queue.length === 0) return;
      const { fn, resolve, reject } = queue.shift();
      running++;
      Promise.resolve().then(fn).then((v) => {
        running--; resolve(v); runNext();
      }, (e) => {
        running--; reject(e); runNext();
      });
    };
    return (fn) => new Promise((resolve, reject) => {
      queue.push({ fn, resolve, reject }); runNext();
    });
  }
  const limit5 = pLimit(5);

  async function api(url) {
    const r = await fetch(url);
    if (!r.ok) return [];
    return r.json();
  }

  function summarize(rows) {
    let spend = 0, msgs = 0, ctr = 0, clicks = 0, impressions = 0;
    (rows || []).forEach(r => {
      spend += Number(r.spend || 0);
      clicks += Number(r.clicks || 0);
      impressions += Number(r.impressions || 0);

      let added = false;
      if (r.results != null) {
        const v = Number(r.results);
        if (!Number.isNaN(v)) { msgs += v; added = v > 0; }
      }
      if (!added && Array.isArray(r.actions)) {
        r.actions.forEach(a => {
          const t = String(a.action_type || "").toLowerCase();
          if (
            t.includes("onsite_conversion.messaging_conversation_started") ||
            t.includes("messaging_conversation_started") ||
            t.includes("messaging_conversations_started") ||
            t.includes("omni_messaging_conversation_started") ||
            t.includes("messaging_first_reply") ||
            t.includes("conversation_started")
          ) msgs += Number(a.value || 0);
        });
      }
    });
    ctr = impressions ? (clicks / impressions) * 100 : 0;
    const cpr = msgs ? (spend / msgs) : 0;
    return { spend, messages: msgs, cpr, ctr };
  }

  // ---------- estado ----------
  const state = {
    preset: "today",
    since: null,
    until: null,
    accounts: window.AD_ACCOUNTS || [],
    campaigns: [],
    selected: null,
    chart: null,
    thumbsObserver: null
  };

  // ---------- UI: fechas ----------
  const seg = el("seg");
  const rangeBox = el("range");
  const sinceInp = el("since");
  const untilInp = el("until");
  const applyBtn = el("apply");

  seg.addEventListener("click", (e) => {
    const btn = e.target.closest(".opt");
    if (!btn) return;
    $$(".opt", seg).forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    const p = btn.dataset.preset;
    state.preset = p;
    if (p === "range") rangeBox.classList.add("show");
    else { rangeBox.classList.remove("show"); state.since = state.until = null; }
  });

  applyBtn.addEventListener("click", async () => {
    // si es rango, validar
    if (state.preset === "range") {
      const s = sinceInp.value, u = untilInp.value;
      if (!s || !u) return; // no aplica sin ambos
      state.since = s; state.until = u;
    }
    await withLoading(loadCampaigns);
  });

  function setLoading(btn, on) {
    btn.classList.toggle("loading", on);
    btn.disabled = on;
  }
  async function withLoading(fn) {
    setLoading(applyBtn, true);
    try { await fn(); } finally { setLoading(applyBtn, false); }
  }

  // ---------- carga campañas ----------
  async function loadCampaigns() {
    const preset = state.preset;
    const useRange = preset === "range" && state.since && state.until;

    // 1) campañas por cuenta (en paralelo)
    const campByAcc = await Promise.all(state.accounts.map(acc =>
      api(`/get_campaigns/${encodeURIComponent(acc)}`)
    ));
    const all = campByAcc.flat().map(c => ({ ...c }));

    // 2) insights de campaña (limitando concurrencia)
    const enriched = await Promise.all(all.map(c => limit5(async () => {
      const url = useRange
        ? `/get_insights/campaign/${c.id}?time_increment=1&date_preset=this_month&since=${state.since}&until=${state.until}` // daily si hay rango
        : `/get_insights/campaign/${c.id}?date_preset=${encodeURIComponent(preset)}`;
      const ins = await api(url);
      const m = summarize(ins);
      return { ...c, metrics: m };
    })));

    // 3) filtrar campañas con actividad
    state.campaigns = enriched.filter(c => (c.metrics.spend > 0 || c.metrics.messages > 0))
                              .sort((a,b)=>b.metrics.spend-a.metrics.spend);

    paintCampaigns();
    paintTopKPIs();

    if (state.campaigns.length) selectCampaign(state.campaigns[0]);
    else clearDetail();
  }

  // ---------- KPIs ----------
  function paintTopKPIs() {
    let spend = 0, messages = 0;
    state.campaigns.forEach(c => { spend += c.metrics.spend; messages += c.metrics.messages; });
    const cpr = messages ? spend / messages : 0;

    el("kpi-spend").textContent = fmtSoles(spend);
    el("kpi-results").textContent = String(Math.round(messages));
    el("kpi-cpr").textContent = fmtSoles(cpr);

    // Ayer / Hoy sobre la campaña líder (rápido)
    const first = state.campaigns[0];
    if (!first) { el("kpi-yesterday").textContent = "—"; el("kpi-today").textContent = "—"; return; }
    Promise.all([
      api(`/get_insights/campaign/${first.id}?date_preset=yesterday`),
      api(`/get_insights/campaign/${first.id}?date_preset=today`)
    ]).then(([y, t]) => {
      el("kpi-yesterday").textContent = String(Math.round(summarize(y).messages));
      el("kpi-today").textContent = String(Math.round(summarize(t).messages));
    }).catch(()=>{});
  }

  // ---------- campañas ----------
  function paintCampaigns() {
    const wrap = el("campaigns");
    wrap.innerHTML = "";
    if (!state.campaigns.length) {
      wrap.innerHTML = `<div class="card" style="cursor:default">No hay campañas activas en este rango.</div>`;
      return;
    }
    state.campaigns.forEach(c => {
      const card = document.createElement("div");
      card.className = "card";
      card.innerHTML = `
        <div style="font-weight:700;margin-bottom:6px">${c.name || c.id}</div>
        <div class="badge">Gasto: ${fmtSoles(c.metrics.spend)}</div>
        <div class="badge">Resultados: ${Math.round(c.metrics.messages)}</div>
        <div class="badge">CPR: ${fmtSoles(c.metrics.cpr)}</div>
      `;
      card.addEventListener("click", () => selectCampaign(c));
      wrap.appendChild(card);
    });
  }

  function clearDetail() {
    el("camp-title").textContent = "Selecciona una campaña";
    el("camp-spend").textContent = "Gasto: —";
    el("camp-results").textContent = "Resultados: —";
    el("camp-cpr").textContent = "CPR: —";
    el("thumbs").innerHTML = "";
    if (state.chart) { state.chart.destroy(); state.chart = null; }
  }

  // ---------- detalle campaña ----------
  async function selectCampaign(c) {
    state.selected = c;
    el("camp-title").textContent = c.name || c.id;
    el("camp-spend").textContent = `Gasto: ${fmtSoles(c.metrics.spend)}`;
    el("camp-results").textContent = `Resultados: ${Math.round(c.metrics.messages)}`;
    el("camp-cpr").textContent = `CPR: ${fmtSoles(c.metrics.cpr)}`;

    // Gráfico diario (si preset es rango uso since/until; si no, time_increment=1 con preset)
    const useRange = state.preset === "range" && state.since && state.until;
    const url = useRange
      ? `/get_insights/campaign/${c.id}?time_increment=1&since=${state.since}&until=${state.until}`
      : `/get_insights/campaign/${c.id}?date_preset=${encodeURIComponent(state.preset)}&time_increment=1`;
    const daily = await api(url);

    const labels = [], msgs = [], spend = [];
    (daily || []).forEach(r => {
      labels.push(r.date_start || "");
      const m = summarize([r]); msgs.push(m.messages); spend.push(m.spend);
    });
    drawChart(labels, msgs, spend);

    // Miniaturas perezosas: arranca cuando se ve la sección
    lazyLoadThumbs(c);
  }

  function drawChart(labels, serieMsgs, serieSpend) {
    if (state.chart) state.chart.destroy();
    const ctx = el("chart").getContext("2d");
    state.chart = new Chart(ctx, {
      type: "line",
      data: {
        labels,
        datasets: [
          { label: "Resultados (mensajes)", data: serieMsgs, borderWidth: 2, tension: .3 },
          { label: "Gasto (S/)", data: serieSpend, borderWidth: 2, tension: .3 }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,   // usa .chart-box (altura fija)
        scales: { y: { beginAtZero: true } },
        animation: { duration: 250 },
        plugins: { legend: { position: "top" } }
      }
    });
  }

  async function loadThumbsNow(c) {
    const wrap = el("thumbs");
    wrap.innerHTML = "Cargando…";

    // Adsets
    const adsets = await api(`/get_adsets/${c.id}`);
    const ads = [];
    for (const as of adsets) {
      const row = await api(`/get_ads/${as.id}`);
      row.forEach(a => ads.push(a));
    }

    // limitar 12 y pedir insights con pool
    const top = ads.slice(0, 12);
    const blocks = await Promise.all(top.map(a => limit5(async () => {
      const url = (state.preset === "range" && state.since && state.until)
        ? `/get_insights/ad/${a.id}?since=${state.since}&until=${state.until}`
        : `/get_insights/ad/${a.id}?date_preset=${encodeURIComponent(state.preset)}`;
      const ins = await api(url);
      const m = summarize(ins);
      const thumb = a?.creative?.thumbnail_url || "";
      const ctr = m.ctr ? `${m.ctr.toFixed(2)}%` : "0%";
      return `
        <div class="thumb">
          <img src="${thumb}" alt="${(a.name||a.id)}" loading="lazy" />
          <div class="meta">
            <span class="chip">${fmtSoles(m.spend)}</span>
            <span class="chip">Msg: ${Math.round(m.messages)}</span>
            <span class="chip">CPR: ${fmtSoles(m.cpr)}</span>
            <span class="chip">CTR: ${ctr}</span>
          </div>
        </div>
      `;
    })));

    wrap.innerHTML = blocks.join("") || "<div class='muted'>Sin anuncios en esta campaña.</div>";
  }

  function lazyLoadThumbs(c) {
    const wrap = el("thumbs");
    wrap.innerHTML = "<div class='muted'>Las miniaturas se cargarán al mostrarse…</div>";
    if (state.thumbsObserver) { state.thumbsObserver.disconnect(); state.thumbsObserver = null; }
    state.thumbsObserver = new IntersectionObserver((entries) => {
      const v = entries[0];
      if (v && v.isIntersecting) {
        state.thumbsObserver.disconnect();
        loadThumbsNow(c);
      }
    }, { root:null, threshold:.1 });
    state.thumbsObserver.observe(wrap);
  }

  // ---------- init ----------
  (async function init() {
    // Preset por defecto “Hoy”
    await withLoading(loadCampaigns);
  })();
})();
