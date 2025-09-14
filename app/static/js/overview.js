// app/static/js/overview.js
(function(){
  const el = (id)=>document.getElementById(id);
  const $$ = (s,ctx=document)=>Array.from(ctx.querySelectorAll(s));
  const fmtSoles=(v)=>`S/ ${Number(v||0).toFixed(2)}`;

  const state = { preset:"today", since:null, until:null };

  const seg = el("seg");
  const rangeBox = el("range");
  const sinceInp = el("since");
  const untilInp = el("until");
  const applyBtn = el("apply");
  const cards = el("cards");

  seg.addEventListener("click",(e)=>{
    const btn = e.target.closest(".opt"); if(!btn) return;
    $$(".opt",seg).forEach(b=>b.classList.remove("active"));
    btn.classList.add("active");
    const p = btn.dataset.preset; state.preset = p;
    if(p==="range") rangeBox.classList.add("show");
    else { rangeBox.classList.remove("show"); state.since = state.until = null; }
  });

  function setLoading(on){ applyBtn.classList.toggle("loading",on); applyBtn.disabled=on; }

  applyBtn.addEventListener("click", async ()=>{
    if(state.preset==="range"){
      const s=sinceInp.value,u=untilInp.value; if(!s||!u) return;
      state.since=s; state.until=u;
    }
    await load();
  });

  async function load(){
    setLoading(true);
    try{
      let url = `/api/overview?date_preset=${encodeURIComponent(state.preset)}`;
      if(state.preset==="range" && state.since && state.until){
        url = `/api/overview?date_preset=this_month&since=${state.since}&until=${state.until}`;
      }
      const r = await fetch(url); const data = r.ok ? await r.json():[];
      paint(data);
    }finally{ setLoading(false); }
  }

  function paint(list){
    cards.innerHTML="";
    if(!list.length){ cards.innerHTML = `<div class="card">Sin datos en este rango.</div>`; return; }
    list.forEach(item=>{
      const card = document.createElement("div");
      card.className="card";
      card.innerHTML = `
        <div style="font-weight:700;font-size:18px;margin-bottom:6px">${item.client_name}</div>
        <div class="muted" style="font-size:12px;margin-bottom:10px">ID: ${item.client_id}</div>
        <div class="badge">Gasto: ${fmtSoles(item.spend)}</div>
        <div class="badge">Mensajes: ${Math.round(item.messages)}</div>
        <div class="badge">CPR: ${fmtSoles(item.cpr)}</div>
        <div style="margin-top:12px">
          <a class="btn-link" href="/dashboard/${item.client_id}">Ver dashboard</a>
        </div>
      `;
      cards.appendChild(card);
    });
  }

  // init
  load();
})();
