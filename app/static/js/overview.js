// app/static/js/overview.js
// Controla los filtros (Hoy, Ayer, 7 días, Mes actual, Mes pasado, Rango)
// y pinta el listado del overview con Spend, Results y CPR.

(function () {
  // ---------- Utilidades ----------
  const $ = (sel) => document.querySelector(sel);
  const $all = (sel) => Array.from(document.querySelectorAll(sel));

  const number = (n) => {
    const x = typeof n === "number" ? n : parseFloat(n || 0);
    return isFinite(x) ? x : 0;
  };

  const money = (n) =>
    new Intl.NumberFormat("es-PE", { style: "currency", currency: "PEN", maximumFractionDigits: 2 }).format(number(n));

  const fmt = (n) =>
    new Intl.NumberFormat("es-PE", { maximumFractionDigits: 2 }).format(number(n));

  // Mapea el texto del botón a la clave que entiende el backend
  const mapPreset = (label) => {
    const t = (label || "").toLowerCase().normalize("NFD").replace(/\p{Diacritic}/gu, "");
    if (t.includes("hoy")) return "hoy";
    if (t.includes("ayer")) return "ayer";
    if (t.includes("7") || t.includes("7 dias") || t.includes("7 dias")) return "7d";
    if (t.includes("mes actual")) return "mes_actual";
    if (t.includes("mes pasado")) return "mes_pasado";
    if (t.includes("rango")) return "rango";
    // Si llega un valor ya en formato Graph, lo pasamos tal cual
    return label;
  };

  // Lee fechas desde distintos posibles IDs de inputs
  const readDateInputs = () => {
    const since = ($("#since") || $("#fecha-desde") || $("#desde") || $("#range_since"))?.value || "";
    const until = ($("#until") || $("#fecha-hasta") || $("#hasta") || $("#range_until"))?.value || "";
    return { since, until };
  };

  // ---------- Fetch de datos ----------
  async function loadOverview(preset, opt = {}) {
    const params = new URLSearchParams();
    if (preset) params.set("date_preset", preset);
    if (preset === "rango") {
      const { since, until } = opt;
      if (since && until) {
        params.set("since", since);
        params.set("until", until);
      } else {
        // Si falta rango, vuelve a "hoy"
        params.set("date_preset", "hoy");
      }
    }
    const url = `/api/overview?${params.toString()}`;
    const res = await fetch(url);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const json = await res.json();
    return json?.data || [];
  }

  // ---------- Render ----------
  function ensureContainer() {
    // Intenta usar un contenedor existente; si no, crea uno
    let wrap =
      $("#overview-list") ||
      $(".overview-list") ||
      $("#overview-results") ||
      $("#overview") ||
      $("#results");
    if (!wrap) {
      wrap = document.createElement("div");
      wrap.id = "overview-list";
      wrap.style.marginTop = "16px";
      document.body.appendChild(wrap);
    }
    return wrap;
  }

  function setActive(btn) {
    // Quita estado activo del resto
    const all = $all("[data-preset]");
    all.forEach((b) => b.classList?.remove("active"));
    btn?.classList?.add("active");
  }

  function renderEmpty(container, text = "Sin datos en este rango.") {
    container.innerHTML = "";
    const card = document.createElement("div");
    card.className = "card empty";
    // estilos suaves por si no hay CSS de 'card'
    card.style.padding = "18px";
    card.style.borderRadius = "12px";
    card.style.background = "rgba(255,255,255,0.03)";
    card.style.border = "1px solid rgba(255,255,255,0.08)";
    card.textContent = text;
    container.appendChild(card);
  }

  function renderList(container, items) {
    container.innerHTML = "";
    if (!items || !items.length) {
      renderEmpty(container);
      return;
    }

    const grid = document.createElement("div");
    grid.style.display = "grid";
    grid.style.gridTemplateColumns = "repeat(auto-fit, minmax(260px, 1fr))";
    grid.style.gap = "12px";

    items.forEach((it) => {
      const { client_id, client_name, spend, results, cpr } = it || {};
      const card = document.createElement("div");
      card.className = "card";
      card.style.padding = "16px";
      card.style.borderRadius = "14px";
      card.style.background = "rgba(255,255,255,0.03)";
      card.style.border = "1px solid rgba(255,255,255,0.08)";

      const title = document.createElement("div");
      title.style.fontWeight = "600";
      title.style.marginBottom = "8px";
      title.textContent = client_name || client_id || "Cliente";

      const row = (label, value) => {
        const r = document.createElement("div");
        r.style.display = "flex";
        r.style.justifyContent = "space-between";
        r.style.margin = "4px 0";
        const l = document.createElement("span");
        l.style.opacity = "0.8";
        l.textContent = label;
        const v = document.createElement("strong");
        v.textContent = value;
        r.appendChild(l);
        r.appendChild(v);
        return r;
      };

      const link = document.createElement("a");
      link.href = `/dashboard/${encodeURIComponent(client_id)}`;
      link.textContent = "Abrir dashboard";
      link.style.display = "inline-block";
      link.style.marginTop = "10px";
      link.style.fontWeight = "600";
      link.style.textDecoration = "none";
      link.style.padding = "8px 10px";
      link.style.borderRadius = "10px";
      link.style.background = "rgba(59,130,246,0.15)";

      card.appendChild(title);
      card.appendChild(row("Gasto (Spend)", money(spend)));
      card.appendChild(row("Resultados", fmt(results)));
      card.appendChild(row("CPR", money(cpr)));
      card.appendChild(link);
      grid.appendChild(card);
    });

    container.appendChild(grid);
  }

  // ---------- Binding de botones ----------
  function findPresetButtons() {
    // Si ya tienen data-preset en el HTML, usamos eso. Si no, inferimos por texto.
    let buttons = $all("[data-preset]");
    if (buttons.length) return buttons;

    // fallback: busca botones por texto aproximado
    buttons = $all("button, a").filter((b) => {
      const t = (b.textContent || "").toLowerCase();
      return (
        t.includes("hoy") ||
        t.includes("ayer") ||
        t.includes("7") ||
        t.includes("mes actual") ||
        t.includes("mes pasado") ||
        t.includes("rango")
      );
    });
    // marca data-preset para manejarlos de forma uniforme
    buttons.forEach((b) => b.setAttribute("data-preset", mapPreset(b.textContent || "")));
    return buttons;
  }

  async function handleClick(btn) {
    const preset = btn.getAttribute("data-preset") || mapPreset(btn.textContent || "");
    setActive(btn);
    const container = ensureContainer();
    renderEmpty(container, "Cargando…");

    try {
      let data;
      if (preset === "rango") {
        const { since, until } = readDateInputs();
        data = await loadOverview("rango", { since, until });
      } else {
        data = await loadOverview(preset);
      }
      renderList(container, data);
    } catch (e) {
      renderEmpty(container, "No se pudo cargar. Intenta nuevamente.");
      // console.error(e);
    }
  }

  function bindRangeApply() {
    // Botón "Aplicar" (si existe)
    const apply =
      $("[data-apply-range]") ||
      $all("button, a").find((b) => (b.textContent || "").toLowerCase().includes("aplicar"));
    if (!apply) return;
    apply.addEventListener("click", (ev) => {
      ev.preventDefault();
      // Activa visualmente el botón de Rango si existe
      const rb = $all("[data-preset]").find((b) => (b.getAttribute("data-preset") || "").includes("rango"));
      if (rb) setActive(rb);
      handleClick(rb || apply); // hará lectura de fechas
    });
  }

  async function init() {
    const container = ensureContainer();
    renderEmpty(container, "Cargando…");

    const buttons = findPresetButtons();
    buttons.forEach((btn) => {
      btn.addEventListener("click", (ev) => {
        ev.preventDefault();
        handleClick(btn);
      });
    });

    bindRangeApply();

    // Carga inicial: intenta "Mes actual" si existe; si no, "Hoy"
    const prefer = buttons.find((b) => (b.getAttribute("data-preset") || "").includes("mes_actual"));
    await handleClick(prefer || buttons[0] || null);
  }

  document.addEventListener("DOMContentLoaded", init);
})();
