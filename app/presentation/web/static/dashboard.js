/* Observatoire Réunion — rendu ECharts. Toute l'analytique vient du SQL ; ici uniquement de l'affichage. */
(() => {
  const charts = {};      // id -> instance ECharts
  const tables = {};      // id -> {cols, rows} : vue tableau de chaque graphique
  const DOW = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"];
  const MOIS = ["Jan", "Fév", "Mar", "Avr", "Mai", "Juin", "Juil", "Août", "Sep", "Oct", "Nov", "Déc"];
  const GRAV = ["Léger", "Grave (hospitalisé)", "Mortel"];
  let cross = null, panel = null, corrMode = "pearson";

  const css = (v) => getComputedStyle(document.body).getPropertyValue(v).trim();
  const fmt = (v, d = 0) => v == null ? "–" : Number(v).toLocaleString("fr-FR", { maximumFractionDigits: d });
  const T = () => ({  // tokens lus à chaque rendu : clair / sombre
    surface: css("--surface-1"), ink: css("--text-primary"), ink2: css("--text-secondary"), muted: css("--muted"),
    grid: css("--grid"), axis: css("--axis"), s: [css("--s1"), css("--s2"), css("--s3"), css("--s4")],
    o: [css("--o1"), css("--o2"), css("--o3")], seq: [css("--seq-lo"), css("--seq-hi")],
    div: [css("--div-neg"), css("--div-mid"), css("--div-pos")],
    b: [1, 2, 3, 4, 5].map(i => css(`--b${i}`)),
  });

  function base(t) {
    return {
      textStyle: { fontFamily: "system-ui, -apple-system, Segoe UI, sans-serif", color: t.ink2 },
      grid: { left: 8, right: 24, top: 36, bottom: 8, containLabel: true },
      tooltip: { backgroundColor: t.surface, borderColor: t.grid, textStyle: { color: t.ink, fontSize: 12 },
                 confine: true },
      legend: { top: 0, left: 0, type: innerWidth < 640 ? "scroll" : "plain", icon: "roundRect", itemWidth: 12, itemHeight: 8, textStyle: { color: t.ink2 } },
    };
  }
  const axis = (t, extra = {}) => ({
    axisLine: { lineStyle: { color: t.axis } }, axisTick: { show: false },
    axisLabel: { color: t.muted, fontSize: 11 }, splitLine: { lineStyle: { color: t.grid, width: 1 } },
    nameTextStyle: { color: t.muted, fontSize: 11, align: "left" }, ...extra,
  });

  const pending = {};     // id -> [option, after] : graphiques d'un onglet caché, rendus à l'affichage

  // Boutons d'action d'une carte : « Tableau » (vue accessible) et « SQL » (requête source)
  function actions(card) {
    if (card.querySelector(".card-actions")) return card.querySelector(".card-actions");
    const box = document.createElement("div");
    box.className = "card-actions";
    card.appendChild(box);
    if (card.dataset.sql) {
      const s = document.createElement("button");
      s.className = "btn-sm"; s.textContent = "SQL"; s.title = "Voir la requête SQL de ce graphique";
      s.onclick = () => showSql(card.dataset.sql);
      box.appendChild(s);
    }
    return box;
  }

  function mount(id, option, table, after) {
    const card = document.querySelector(`[data-chart="${id}"]`);
    if (!card) return;
    const el = card.querySelector(".chart");
    tables[id] = table;
    const box = actions(card);
    if (!box.querySelector(".tbl-btn")) {
      const b = document.createElement("button");
      b.className = "btn-sm tbl-btn"; b.textContent = "Tableau";
      b.onclick = () => {
        const tv = card.querySelector(".tbl");
        if (tv) { tv.remove(); el.hidden = false; b.textContent = "Tableau"; flushPending(); return; }
        el.hidden = true; b.textContent = "Graphique";
        el.insertAdjacentElement("afterend", renderTable(tables[id]));
      };
      box.prepend(b);
    }
    card.querySelector(".tbl")?.replaceWith(renderTable(table));  // vue tableau ouverte : on la rafraîchit
    if (!el.offsetWidth) { pending[id] = [option, after]; return; }  // onglet caché : rendu différé
    delete pending[id];
    if (charts[id]) charts[id].dispose();
    charts[id] = echarts.init(el, null, { renderer: "svg" });
    charts[id].setOption(option);
    after?.(charts[id]);
  }

  function flushPending() {
    for (const [id, [option, after]] of Object.entries(pending)) mount(id, option, tables[id], after);
    Object.values(charts).forEach(c => c.getDom().offsetWidth && c.resize());
  }

  /* ---------------- Onglets ---------------- */
  const TABS = ["immobilier", "securite", "emploi", "climat", "correlations", "donnees"];

  function showTab(name, push = true) {
    if (!TABS.includes(name)) name = TABS[0];
    document.querySelectorAll('[role="tab"]').forEach(b => b.setAttribute("aria-selected", b.dataset.tab === name));
    document.querySelectorAll('[role="tabpanel"]').forEach(p => (p.hidden = p.id !== `tab-${name}`));
    if (push) history.replaceState(null, "", `#${name}`);
    flushPending();
  }

  function showSql(name) {
    showTab("donnees");
    const d = document.getElementById(`sql-${name}`);
    if (!d) return;
    d.open = true;
    d.scrollIntoView({ behavior: "smooth", block: "start" });
    d.classList.add("flash");
    setTimeout(() => d.classList.remove("flash"), 1800);
  }

  function renderTable({ cols, rows }) {
    const div = document.createElement("div");
    div.className = "tbl";
    div.innerHTML = `<table><thead><tr>${cols.map(c => `<th>${c[1]}</th>`).join("")}</tr></thead><tbody>${
      rows.map(r => `<tr>${cols.map(c => `<td>${typeof r[c[0]] === "number" ? fmt(r[c[0]], 2) : (r[c[0]] ?? "–")}</td>`).join("")}</tr>`).join("")
    }</tbody></table>`;
    return div;
  }

  // Étiquette directe en bout de ligne (sélective : une par série)
  const endLabel = (t) => ({ show: true, formatter: "{a}", color: t.ink2, fontSize: 11, distance: 6 });

  /* ---------------- Section filtrée ---------------- */

  function prixTrend(t, rows) {
    const years = [...new Set(rows.map(r => r.annee))];
    const types = ["Maison", "Appartement"];
    const by = (ty) => years.map(y => rows.find(r => r.annee === y && r.type_bien === ty) || null);
    mount("prix_trend", {
      ...base(t),
      grid: { ...base(t).grid, right: 90 },
      tooltip: { ...base(t).tooltip, trigger: "axis", axisPointer: { type: "line", lineStyle: { color: t.axis } },
        formatter: (ps) => `<b>${ps[0].axisValue}</b><br>` + ps.map(p => {
          const r = by(p.seriesName)[p.dataIndex];
          return r ? `${p.marker}${p.seriesName} : <b>${fmt(r.med)} €/m²</b> (Q1-Q3 ${fmt(r.q1)}-${fmt(r.q3)}, ${fmt(r.n)} ventes)` : "";
        }).join("<br>") },
      xAxis: axis(t, { type: "category", data: years, boundaryGap: false, splitLine: { show: false } }),
      yAxis: axis(t, { type: "value", scale: true, axisLabel: { color: t.muted, fontSize: 11, formatter: (v) => `${fmt(v)} €` } }),
      series: types.map((ty, i) => ({
        name: ty, type: "line", data: by(ty).map(r => r?.med ?? null), color: t.s[i],
        lineStyle: { width: 2 }, symbol: "circle", symbolSize: 8, showSymbol: false,
        endLabel: endLabel(t), labelLayout: { moveOverlap: "shiftY" }, emphasis: { focus: "series" },
      })),
    }, { cols: [["annee", "Année"], ["type_bien", "Type"], ["med", "Médiane €/m²"], ["q1", "Q1"], ["q3", "Q3"], ["n", "Ventes"]], rows });
  }

  function prixBox(t, rows) {
    const r = [...rows].reverse();  // le plus cher en haut
    mount("prix_box", {
      ...base(t),
      tooltip: { ...base(t).tooltip, trigger: "item", formatter: (p) => {
        const x = r[p.dataIndex]; const q = x.q;
        return `<b>${x.nom}</b> (${fmt(x.n)} ventes)<br>P90 ${fmt(q[4])} · Q3 ${fmt(q[3])}<br><b>Médiane ${fmt(q[2])} €/m²</b><br>Q1 ${fmt(q[1])} · P10 ${fmt(q[0])}`; } },
      xAxis: axis(t, { type: "value", axisLabel: { color: t.muted, fontSize: 11, formatter: (v) => `${fmt(v)} €` } }),
      yAxis: axis(t, { type: "category", data: r.map(x => x.nom), splitLine: { show: false } }),
      series: [{ type: "boxplot", data: r.map(x => x.q), boxWidth: [6, 14],
        itemStyle: { color: t.s[0] + "33", borderColor: t.s[0], borderWidth: 1.5 } }],
    }, { cols: [["nom", "Commune"], ["n", "Ventes"], ["p10", "P10"], ["q1", "Q1"], ["med", "Médiane"], ["q3", "Q3"], ["p90", "P90"]],
         rows: rows.map(x => ({ nom: x.nom, n: x.n, p10: x.q[0], q1: x.q[1], med: x.q[2], q3: x.q[3], p90: x.q[4] })) });
  }

  function prixEvol(t, rows) {
    const r = [...rows].reverse();
    mount("prix_evol", {
      ...base(t),
      tooltip: { ...base(t).tooltip, trigger: "item", formatter: (p) => {
        const x = r[p.dataIndex]; return `<b>${x.nom}</b> (${x.region})<br>${x.evol_prix_pct > 0 ? "+" : ""}${fmt(x.evol_prix_pct, 1)} %<br>Prix 2023-25 : ${fmt(x.prix_m2)} €/m²<br>${fmt(x.n_ventes)} ventes`; } },
      xAxis: axis(t, { type: "value", axisLabel: { color: t.muted, fontSize: 11, formatter: "{value} %" } }),
      yAxis: axis(t, { type: "category", data: r.map(x => x.nom), splitLine: { show: false }, axisLabel: { color: t.muted, fontSize: 11, interval: 0 } }),
      series: [{ type: "bar", data: r.map(x => x.evol_prix_pct), color: t.s[0], barMaxWidth: 14,
        itemStyle: { borderRadius: [0, 4, 4, 0] },
        label: { show: true, position: "right", color: t.ink2, fontSize: 10,
                 formatter: (p) => (p.dataIndex === 0 || p.dataIndex === r.length - 1) ? `${fmt(p.value, 1)} %` : "" } }],
    }, { cols: [["nom", "Commune"], ["region", "Micro-région"], ["evol_prix_pct", "Évolution %"], ["prix_m2", "Prix 2023-25"], ["n_ventes", "Ventes"]], rows });
  }

  function accHeatmap(t, rows) {
    const max = Math.max(...rows.map(r => r.n));
    const peak = rows.reduce((a, b) => (b.n > a.n ? b : a));
    mount("acc_heatmap", {
      ...base(t),
      grid: { ...base(t).grid, top: 10, bottom: 50 },
      tooltip: { ...base(t).tooltip, trigger: "item", formatter: (p) => `${DOW[p.value[1]]} ${p.value[0]}h-${p.value[0] + 1}h : <b>${fmt(p.value[2])}</b> accidents` },
      xAxis: axis(t, { type: "category", data: [...Array(24).keys()].map(h => `${h}h`), splitLine: { show: false } }),
      yAxis: axis(t, { type: "category", data: DOW, inverse: true, splitLine: { show: false } }),
      visualMap: { min: 0, max, orient: "horizontal", left: "center", bottom: 0, itemHeight: 160, itemWidth: 10,
        inRange: { color: t.seq }, textStyle: { color: t.muted, fontSize: 11 }, text: ["plus", "moins"], calculable: false },
      series: [{ type: "heatmap", data: rows.map(r => [r.heure, r.dow - 1, r.n]),
        itemStyle: { borderColor: t.surface, borderWidth: 1, borderRadius: 2 },
        label: { show: true, color: t.surface, fontSize: 10, formatter: (p) => p.value[0] === peak.heure && p.value[1] === peak.dow - 1 ? p.value[2] : "" } }],
    }, { cols: [["jour", "Jour"], ["heure", "Heure"], ["n", "Accidents"]], rows: rows.map(r => ({ jour: DOW[r.dow - 1], heure: r.heure, n: r.n })) });
  }

  function stackedBars(id, t, years, series, tableCols, tableRows, tooltipExtra) {
    mount(id, {
      ...base(t),
      tooltip: { ...base(t).tooltip, trigger: "axis", axisPointer: { type: "shadow", shadowStyle: { color: t.grid + "66" } },
        formatter: (ps) => `<b>${ps[0].axisValue}</b><br>` + ps.slice().reverse().map(p => `${p.marker}${p.seriesName} : <b>${fmt(p.value)}</b>`).join("<br>")
          + (tooltipExtra ? tooltipExtra(ps[0].dataIndex) : "") },
      xAxis: axis(t, { type: "category", data: years, splitLine: { show: false } }),
      yAxis: axis(t, { type: "value" }),
      series: series.map((s, i) => ({ ...s, type: "bar", stack: "s", barMaxWidth: 28,
        itemStyle: { color: s.color, borderColor: t.surface, borderWidth: 1,
                     borderRadius: i === series.length - 1 ? [4, 4, 0, 0] : 0 } })),
    }, { cols: tableCols, rows: tableRows });
  }

  function accGravite(t, rows) {
    const years = [...new Set(rows.map(r => r.annee))];
    const get = (y, g) => rows.find(r => r.annee === y && r.gravite === g)?.n ?? 0;
    const tr = years.map(y => ({ annee: y, ...Object.fromEntries(GRAV.map(g => [g, get(y, g)])) }));
    stackedBars("acc_gravite", t, years,
      GRAV.map((g, i) => ({ name: g, data: years.map(y => get(y, g)), color: t.o[i] })),
      [["annee", "Année"], ...GRAV.map(g => [g, g])], tr);
  }

  function permisTrend(t, rows) {
    stackedBars("permis_trend", t, rows.map(r => r.annee), [
      { name: "Individuel", data: rows.map(r => r.individuel), color: t.s[0] },
      { name: "Collectif", data: rows.map(r => r.collectif), color: t.s[1] },
    ], [["annee", "Année"], ["individuel", "Individuel"], ["collectif", "Collectif"], ["dont_social", "Dont prêt locatif social"]], rows,
    (i) => `<br><span style="color:${t.ink2}">dont social : ${fmt(rows[i].dont_social)}</span>`);
  }

  function renderPanel() {
    const node = document.getElementById("panel-data");
    if (!node) return;
    panel = JSON.parse(node.textContent);
    const t = T();
    prixTrend(t, panel.prix_trend); prixBox(t, panel.prix_box); prixEvol(t, panel.prix_evol);
    accHeatmap(t, panel.acc_heatmap); accGravite(t, panel.acc_gravite); permisTrend(t, panel.permis_trend);
  }

  /* ---------------- Analyses croisées ---------------- */

  function corrMatrix(t) {
    const ind = cross.indicators, keys = cross.order;
    const cell = (x, y) => cross.corr_matrix.find(r => r.x === x && r.y === y);
    const data = [];
    keys.forEach((x, i) => keys.forEach((y, j) => { const c = cell(x, y); data.push([i, j, c ? c[corrMode] : null, c?.n ?? 0]); }));
    mount("corr", {
      ...base(t),
      grid: { ...base(t).grid, top: 10, bottom: 50 },
      tooltip: { ...base(t).tooltip, trigger: "item", formatter: (p) => {
        const [i, j, r, n] = p.value;
        return `<b>${ind[keys[i]].label}</b><br>× <b>${ind[keys[j]].label}</b><br>${corrMode === "pearson" ? "Pearson" : "Spearman"} r = <b>${fmt(r, 2)}</b> · n = ${n}`; } },
      xAxis: axis(t, { type: "category", data: keys.map(k => ind[k].short), splitLine: { show: false },
        axisLabel: { color: t.muted, fontSize: 10, rotate: 40, interval: 0 } }),
      yAxis: axis(t, { type: "category", data: keys.map(k => ind[k].short), inverse: true, splitLine: { show: false },
        axisLabel: { color: t.muted, fontSize: 10, interval: 0 } }),
      visualMap: { min: -1, max: 1, dimension: 2, orient: "horizontal", left: "center", bottom: 0, itemHeight: 180, itemWidth: 10,
        inRange: { color: t.div }, text: ["+1", "−1"], textStyle: { color: t.muted, fontSize: 11 } },
      series: [{ type: "heatmap", data, itemStyle: { borderColor: t.surface, borderWidth: 2, borderRadius: 3 },
        label: { show: true, fontSize: 10, color: t.ink, formatter: (p) => p.value[0] === p.value[1] ? "" : fmt(Math.abs(p.value[2]) < 0.05 ? 0 : p.value[2], 1) },
        emphasis: { itemStyle: { borderColor: t.ink, borderWidth: 2 } } }],
    }, { cols: [["x", "Indicateur A"], ["y", "Indicateur B"], ["pearson", "Pearson"], ["spearman", "Spearman"], ["n", "n"]],
         rows: cross.corr_matrix.filter(r => keys.indexOf(r.x) < keys.indexOf(r.y)).map(r => ({ ...r, x: ind[r.x].label, y: ind[r.y].label })) },
    (c) => c.on("click", (p) => { if (p.value[0] !== p.value[1]) loadPair(keys[p.value[0]], keys[p.value[1]]); }));
  }

  async function loadPair(x, y) {
    document.getElementById("sx").value = x; document.getElementById("sy").value = y;
    const res = await fetch(`/observatoire/pair?x=${x}&y=${y}`);
    scatter(T(), await res.json());
  }

  function scatter(t, d) {
    const ind = cross.indicators, X = ind[d.x], Y = ind[d.y];
    const pts = d.points;
    // Étiquettes sélectives : 4 plus grandes communes + 2 plus gros résidus
    const resid = (p) => Math.abs(p.y - (d.slope * p.x + d.intercept));
    const named = new Set([...[...pts].sort((a, b) => b.pop_2016 - a.pop_2016).slice(0, 4),
                           ...[...pts].sort((a, b) => resid(b) - resid(a)).slice(0, 2)].map(p => p.nom));
    const xs = pts.map(p => p.x), x0 = Math.min(...xs), x1 = Math.max(...xs);
    document.querySelector('[data-chart="scatter"] .card-title').textContent = `${Y.short} en fonction de ${X.short}`;
    document.getElementById("scatter-stats").innerHTML = d.n < 3 ? "Échantillon insuffisant." :
      `Corrélation <b>${d.strength}</b> : r = <b>${fmt(d.r, 2)}</b>, R² = ${fmt(d.r2, 2)}, n = ${d.n} communes · `
      + `pente : ${fmt(d.slope, 3)} ${Y.unit} par ${X.unit || "unité"}`;
    mount("scatter", {
      ...base(t),
      grid: { ...base(t).grid, top: 34, right: 30 },
      tooltip: { ...base(t).tooltip, trigger: "item", formatter: (p) => p.seriesIndex ? "Droite des moindres carrés" :
        `<b>${pts[p.dataIndex].nom}</b> (${pts[p.dataIndex].region})<br>${X.short} : ${fmt(p.value[0], 2)} ${X.unit}<br>${Y.short} : ${fmt(p.value[1], 2)} ${Y.unit}<br>Population : ${fmt(pts[p.dataIndex].pop_2016)}` },
      xAxis: axis(t, { type: "value", name: X.label, nameLocation: "middle", nameGap: 26, scale: true }),
      yAxis: axis(t, { type: "value", name: Y.unit, scale: true }),
      series: [
        { type: "scatter", data: pts.map(p => [p.x, p.y]), symbolSize: 10, color: t.s[0],
          itemStyle: { borderColor: t.surface, borderWidth: 2 },
          label: { show: innerWidth >= 640, position: "right", fontSize: 10, color: t.ink2,
                   formatter: (p) => named.has(pts[p.dataIndex].nom) ? pts[p.dataIndex].nom : "" },
          labelLayout: { hideOverlap: true },
          emphasis: { scale: 1.4 } },
        { type: "line", data: d.n >= 3 ? [[x0, d.slope * x0 + d.intercept], [x1, d.slope * x1 + d.intercept]] : [],
          showSymbol: false, lineStyle: { color: t.ink2, width: 1.5 }, z: 1, silent: true },
      ],
    }, { cols: [["nom", "Commune"], ["region", "Micro-région"], ["x", X.short], ["y", Y.short], ["pop_2016", "Population"]], rows: pts });
  }

  function errorBars(t) {
    return { type: "custom", z: 10, silent: true, tooltip: { show: false },
      renderItem: (params, api) => {
        const i = api.value(0), lo = api.coord([i, api.value(1)]), hi = api.coord([i, api.value(2)]), w = 5;
        const st = { stroke: t.ink2, lineWidth: 1.5 };
        return { type: "group", children: [
          { type: "line", shape: { x1: lo[0], y1: lo[1], x2: hi[0], y2: hi[1] }, style: st },
          { type: "line", shape: { x1: lo[0] - w, y1: lo[1], x2: lo[0] + w, y2: lo[1] }, style: st },
          { type: "line", shape: { x1: hi[0] - w, y1: hi[1], x2: hi[0] + w, y2: hi[1] }, style: st }] };
      }, encode: { x: 0, y: [1, 2] }, data: [] };
  }

  function pluie(t) {
    const rows = cross.pluie_accidents;
    const eb = errorBars(t); eb.data = rows.map((r, i) => [i, r.acc_par_jour - r.ic95, r.acc_par_jour + r.ic95]);
    const forte = rows[rows.length - 1];
    const overlap = rows.every(r => r.acc_par_jour - r.ic95 <= rows[0].acc_par_jour + rows[0].ic95);
    document.getElementById("pluie-stats").innerHTML =
      `Jours de forte pluie : risque relatif <b>×${fmt(forte.risque_relatif, 2)}</b> par rapport aux jours secs · corrélation quotidienne r = ${fmt(forte.corr_jour, 3)} · `
      + (overlap ? "<b>intervalles de confiance chevauchants : pas d'effet significatif</b> à ce niveau d'agrégation." : "écart significatif au seuil de 95 %.");
    mount("pluie", {
      ...base(t),
      tooltip: { ...base(t).tooltip, trigger: "item", formatter: (p) => { const r = rows[p.dataIndex];
        return `<b>${r.classe}</b><br>${fmt(r.acc_par_jour, 3)} accidents/jour (± ${fmt(r.ic95, 3)})<br>${fmt(r.jours)} jours · ${fmt(r.accidents)} accidents<br>Risque relatif : ×${fmt(r.risque_relatif, 2)}`; } },
      xAxis: axis(t, { type: "category", data: rows.map(r => r.classe), splitLine: { show: false },
        axisLabel: { color: t.muted, fontSize: 10, interval: 0, formatter: (v) => v.replace(" (", "\n(") } }),
      yAxis: axis(t, { type: "value", name: "accidents / jour" }),
      series: [{ type: "bar", data: rows.map(r => r.acc_par_jour), color: t.s[0], barMaxWidth: 46, itemStyle: { borderRadius: [4, 4, 0, 0] } }, eb],
    }, { cols: [["classe", "Pluie du jour"], ["jours", "Jours"], ["accidents", "Accidents"], ["acc_par_jour", "Acc./jour"], ["ic95", "± IC 95 %"], ["risque_relatif", "Risque relatif"]], rows });
  }

  function chomage(t) {
    const rows = cross.chomage_index, months = [...new Set(rows.map(r => r.mois))];
    mount("chomage", {
      ...base(t),
      grid: { ...base(t).grid, right: 60 },
      tooltip: { ...base(t).tooltip, trigger: "axis", axisPointer: { type: "line", lineStyle: { color: t.axis } },
        formatter: (ps) => `<b>${ps[0].axisValue.slice(0, 7)}</b><br>` + ps.map(p => {
          const r = rows.find(x => x.region === p.seriesName && x.mois === p.axisValue);
          return `${p.marker}${p.seriesName} : indice <b>${fmt(p.value, 1)}</b> (${fmt(r?.inscrits)} inscrits)`; }).join("<br>") },
      xAxis: axis(t, { type: "category", data: months, boundaryGap: false, splitLine: { show: false },
        axisLabel: { color: t.muted, fontSize: 11, formatter: (v) => v.slice(0, 4), interval: 11 } }),
      yAxis: axis(t, { type: "value", scale: true }),
      series: cross.regions.map((reg, i) => ({
        name: reg, type: "line", color: t.s[i], showSymbol: false, symbolSize: 8, lineStyle: { width: 2 },
        data: months.map(m => rows.find(r => r.region === reg && r.mois === m)?.indice ?? null),
        endLabel: endLabel(t), emphasis: { focus: "series" },
        markLine: i ? undefined : { silent: true, symbol: "none", lineStyle: { color: t.axis, type: "solid" },
          label: { show: false }, data: [{ yAxis: 100 }] } })),
    }, { cols: [["region", "Micro-région"], ["mois", "Mois"], ["inscrits", "Inscrits"], ["indice", "Indice"]], rows });
  }

  /* ---------------- Climat (base Météo-France, toutes stations) ---------------- */
  const EXPO = ["Au vent (est)", "Sous le vent (ouest)", "Nord / Sud"];
  const nomStation = (s) => s.replace(/_SAPC$/, "").toLowerCase().replace(/(^|[\s'-])\S/g, (c) => c.toUpperCase());
  const signed = (v, d = 1) => `${v > 0 ? "+" : ""}${fmt(v, d)}`;
  const stationCols = [["station", "Station"], ["alti", "Altitude (m)"], ["exposition", "Exposition"],
                       ["pluie_normale", "Pluie normale (mm/an)"], ["t_normale", "T° normale (°C)"], ["annees_pluie", "Années"]];

  function carteStations(t, st) {
    const bins = [0, 1000, 2000, 3500, 5000, Infinity];
    const label = new Set([st[0], st[1], st[st.length - 1], st[st.length - 2]].map(s => s.station));
    mount("carte_stations", {
      ...base(t),
      grid: { left: 8, right: 8, top: 8, bottom: 40, containLabel: true },
      tooltip: { ...base(t).tooltip, trigger: "item", formatter: (p) => { const s = st[p.dataIndex];
        return `<b>${nomStation(s.station)}</b> (${fmt(s.alti)} m)<br>Pluie normale : <b>${fmt(s.pluie_normale)} mm/an</b>${s.t_normale != null ? `<br>Température : ${fmt(s.t_normale, 1)} °C` : ""}<br>${s.exposition}`; } },
      xAxis: axis(t, { type: "value", min: 55.2, max: 55.85, splitLine: { show: false },
        axisLabel: { color: t.muted, fontSize: 10, formatter: (v) => `${fmt(v, 2)}° E` } }),
      yAxis: axis(t, { type: "value", min: -21.42, max: -20.84, splitLine: { show: false },
        axisLabel: { color: t.muted, fontSize: 10, formatter: (v) => `${fmt(-v, 2)}° S` } }),
      visualMap: { type: "piecewise", dimension: 2, orient: "horizontal", left: "center", bottom: 0, itemWidth: 12, itemHeight: 10,
        textStyle: { color: t.muted, fontSize: 11 },
        pieces: bins.slice(0, -1).map((lo, i) => ({ min: lo, max: bins[i + 1] === Infinity ? 99999 : bins[i + 1], color: t.b[i],
          label: bins[i + 1] === Infinity ? `≥ ${fmt(lo)} mm` : `${fmt(lo)}-${fmt(bins[i + 1])}` })) },
      series: [{ type: "scatter", data: st.map(s => [s.lon, s.lat, s.pluie_normale]), symbolSize: 13,
        itemStyle: { borderColor: t.surface, borderWidth: 1.5 },
        label: { show: true, position: "right", fontSize: 10, color: t.ink2,
          formatter: (p) => label.has(st[p.dataIndex].station) ? `${nomStation(st[p.dataIndex].station)} · ${fmt(st[p.dataIndex].pluie_normale)} mm` : "" },
        labelLayout: { hideOverlap: true } }],
    }, { cols: stationCols, rows: st });
  }

  function pluieAltitude(t, st) {
    const stat = EXPO.map(e => st.find(s => s.exposition === e)).filter(Boolean);
    document.getElementById("pluie-alti-stats").innerHTML = stat.map(s =>
      `<b>${s.exposition}</b> : médiane ${fmt(s.pluie_mediane_expo)} mm, r(pluie, altitude) = ${fmt(s.r_pluie_alti, 2)}`).join(" · ");
    mount("pluie_alti", {
      ...base(t),
      grid: { ...base(t).grid, right: 30, bottom: 26 },
      tooltip: { ...base(t).tooltip, trigger: "item", formatter: (p) => { const s = p.data[2];
        return `<b>${nomStation(s.station)}</b><br>${fmt(s.alti)} m · <b>${fmt(s.pluie_normale)} mm/an</b><br>${s.exposition}`; } },
      xAxis: axis(t, { type: "value", name: "altitude (m)", nameLocation: "middle", nameGap: 24 }),
      yAxis: axis(t, { type: "log", min: 300, axisLabel: { color: t.muted, fontSize: 11, formatter: (v) => `${fmt(v)} mm` } }),
      series: EXPO.map((e, i) => ({ name: e, type: "scatter", color: t.s[i], symbolSize: 10,
        itemStyle: { borderColor: t.surface, borderWidth: 1.5 },
        data: st.filter(s => s.exposition === e).map(s => [s.alti, s.pluie_normale, s]) })),
    }, { cols: stationCols, rows: st });
  }

  function gradient(t, st) {
    const pts = st.filter(s => s.t_normale != null), g = pts[0];
    const xmax = Math.max(...pts.map(s => s.alti));
    document.getElementById("gradient-stats").innerHTML =
      `Pente <b>${fmt(g.gradient_100m, 2)} °C par 100 m</b> · R² = ${fmt(g.r2_temp, 2)} · n = ${g.n_temp} stations · `
      + `${fmt(g.t_niveau_mer, 1)} °C extrapolés au niveau de la mer`;
    mount("gradient", {
      ...base(t),
      grid: { ...base(t).grid, top: 20, right: 30, bottom: 26 },
      tooltip: { ...base(t).tooltip, trigger: "item", formatter: (p) => { if (p.seriesIndex) return "Droite des moindres carrés";
        const s = pts[p.dataIndex]; const res = s.t_normale - (g.t_niveau_mer + g.gradient_100m * s.alti / 100);
        return `<b>${nomStation(s.station)}</b><br>${fmt(s.alti)} m · <b>${fmt(s.t_normale, 1)} °C</b><br>Écart à la droite : ${signed(res, 1)} °C`; } },
      xAxis: axis(t, { type: "value", name: "altitude (m)", nameLocation: "middle", nameGap: 24 }),
      yAxis: axis(t, { type: "value", scale: true, axisLabel: { color: t.muted, fontSize: 11, formatter: (v) => `${fmt(v)} °C` } }),
      series: [
        { type: "scatter", data: pts.map(s => [s.alti, s.t_normale]), color: t.s[0], symbolSize: 10,
          itemStyle: { borderColor: t.surface, borderWidth: 1.5 } },
        { type: "line", data: [[0, g.t_niveau_mer], [xmax, g.t_niveau_mer + g.gradient_100m * xmax / 100]],
          showSymbol: false, lineStyle: { color: t.ink2, width: 1.5 }, silent: true, z: 1 },
      ],
    }, { cols: stationCols, rows: pts });
  }

  function records(t, rows) {
    const r = [...rows].reverse();
    const lab = (x) => `${nomStation(x.station)} · ${String(x.jour).padStart(2, "0")}/${String(x.mois).padStart(2, "0")}/${x.annee}`;
    mount("records", {
      ...base(t),
      grid: { ...base(t).grid, top: 10, right: 110 },
      tooltip: { ...base(t).tooltip, trigger: "item", formatter: (p) => { const x = r[p.dataIndex];
        return `<b>${lab(x)}</b> (${fmt(x.alti)} m)<br>${fmt(x.pluie_24h, 1)} mm en 24 h<br>${fmt(x.pluie_du_mois)} mm sur le mois${x.cyclone ? `<br>Cyclone ${x.cyclone}` : ""}`; } },
      xAxis: axis(t, { type: "value", min: 0, axisLabel: { show: false }, splitLine: { show: false } }),  // valeurs portées par les étiquettes
      yAxis: axis(t, { type: "category", data: r.map(lab), splitLine: { show: false }, axisLabel: { color: t.muted, fontSize: 10, interval: 0 } }),
      series: [{ type: "bar", data: r.map(x => x.pluie_24h), color: t.s[0], barMaxWidth: 14, itemStyle: { borderRadius: [0, 4, 4, 0] },
        label: { show: true, position: "right", color: t.ink2, fontSize: 10,
          formatter: (p) => `${fmt(p.value)} mm${r[p.dataIndex].cyclone ? ` · ${r[p.dataIndex].cyclone}` : ""}` } }],
    }, { cols: [["station", "Station"], ["alti", "Altitude"], ["jour", "Jour"], ["mois", "Mois"], ["annee", "Année"],
                ["pluie_24h", "Pluie 24 h (mm)"], ["pluie_du_mois", "Pluie du mois (mm)"], ["cyclone", "Cyclone"]], rows });
  }

  function rechauffement(t, rows) {
    const r0 = rows[0];
    const recents = [...rows].sort((a, b) => b.anomalie - a.anomalie).slice(0, 3).map(x => x.annee).join(", ");
    document.getElementById("rechauffement-stats").innerHTML =
      `Tendance <b>${signed(r0.tendance_decennie, 2)} °C par décennie</b> depuis ${r0.annee} (R² = ${fmt(r0.r2, 2)}) · `
      + `années les plus chaudes : ${recents} · de 5 à ${Math.max(...rows.map(x => x.stations))} stations par année`;
    mount("rechauffement", {
      ...base(t),
      grid: { ...base(t).grid, right: 30 },
      legend: { ...base(t).legend, data: ["Anomalie annuelle", "Moyenne glissante 10 ans"] },
      tooltip: { ...base(t).tooltip, trigger: "axis", axisPointer: { type: "shadow", shadowStyle: { color: t.grid + "66" } },
        formatter: (ps) => { const x = rows[ps[0].dataIndex];
          return `<b>${x.annee}</b><br>Anomalie : <b>${signed(x.anomalie, 2)} °C</b><br>Moyenne 10 ans : ${signed(x.moy_10ans, 2)} °C<br>${x.stations} stations`; } },
      xAxis: axis(t, { type: "category", data: rows.map(x => x.annee), splitLine: { show: false } }),
      yAxis: axis(t, { type: "value", axisLabel: { color: t.muted, fontSize: 11, formatter: (v) => `${signed(v)} °C` } }),
      series: [
        { name: "Anomalie annuelle", type: "bar", barMaxWidth: 12, color: t.div[2],
          data: rows.map(x => ({ value: x.anomalie, itemStyle: { color: x.anomalie >= 0 ? t.div[2] : t.div[0],
                                                                  borderRadius: x.anomalie >= 0 ? [3, 3, 0, 0] : [0, 0, 3, 3] } })) },
        { name: "Moyenne glissante 10 ans", type: "line", data: rows.map(x => x.moy_10ans), color: t.ink,
          showSymbol: false, symbolSize: 8, lineStyle: { width: 2 } },
      ],
    }, { cols: [["annee", "Année"], ["anomalie", "Anomalie (°C)"], ["moy_10ans", "Moyenne 10 ans"], ["stations", "Stations"]], rows });
  }

  function pluieAnnuelle(t, rows) {
    mount("pluie_annuelle", {
      ...base(t),
      grid: { ...base(t).grid, top: 30, right: 30 },
      tooltip: { ...base(t).tooltip, trigger: "item", formatter: (p) => { const x = rows[p.dataIndex];
        return `<b>${x.annee}</b> : <b>${signed(x.ecart_pct)} %</b> vs normale<br>Rang : ${x.rang_humide}ᵉ année la plus humide sur ${rows.length}<br>${x.stations} stations${x.cyclones ? `<br>Cyclone(s) : ${x.cyclones}` : ""}`; } },
      xAxis: axis(t, { type: "category", data: rows.map(x => x.annee), splitLine: { show: false } }),
      yAxis: axis(t, { type: "value", axisLabel: { color: t.muted, fontSize: 11, formatter: (v) => `${signed(v, 0)} %` } }),
      series: [{ type: "bar", barMaxWidth: 12,
        data: rows.map(x => ({ value: x.ecart_pct, itemStyle: { color: x.ecart_pct >= 0 ? t.div[0] : t.div[2],
                                                                 borderRadius: x.ecart_pct >= 0 ? [3, 3, 0, 0] : [0, 0, 3, 3] } })),
        label: { show: true, position: "top", color: t.ink2, fontSize: 10,
          formatter: (p) => rows[p.dataIndex].cyclones && rows[p.dataIndex].ecart_pct > 0 ? rows[p.dataIndex].cyclones : "" } }],
    }, { cols: [["annee", "Année"], ["ecart_pct", "Écart à la normale (%)"], ["rang_humide", "Rang (humide)"], ["stations", "Stations"], ["cyclones", "Cyclones"]], rows });
  }

  function regimes(t, rows) {
    const st = [...new Set(rows.map(r => r.station))];
    const info = Object.fromEntries(rows.map(r => [r.station, r]));
    const ylab = (s) => `${nomStation(s)} (${fmt(info[s].pluie_normale)} mm)`;
    mount("regimes", {
      ...base(t),
      grid: { ...base(t).grid, top: 10, bottom: 50 },
      tooltip: { ...base(t).tooltip, trigger: "item", formatter: (p) => { const r = rows.find(x => x.station === st[p.value[1]] && x.mois === p.value[0] + 1);
        return `<b>${nomStation(r.station)}</b> (${fmt(r.alti)} m, ${r.exposition})<br>${MOIS[r.mois - 1]} : <b>${fmt(r.pluie)} mm</b> soit ${fmt(r.part_annuelle_pct, 1)} % de l'année`; } },
      xAxis: axis(t, { type: "category", data: MOIS, splitLine: { show: false } }),
      yAxis: axis(t, { type: "category", data: st.map(ylab), inverse: true, splitLine: { show: false }, axisLabel: { color: t.muted, fontSize: 10, interval: 0 } }),
      visualMap: { min: 0, max: Math.ceil(Math.max(...rows.map(r => r.part_annuelle_pct))), dimension: 2, orient: "horizontal",
        left: "center", bottom: 0, itemHeight: 180, itemWidth: 10, inRange: { color: t.seq },
        text: ["% du cumul annuel", "0"], textStyle: { color: t.muted, fontSize: 11 } },
      series: [{ type: "heatmap", data: rows.map(r => [r.mois - 1, st.indexOf(r.station), r.part_annuelle_pct]),
        itemStyle: { borderColor: t.surface, borderWidth: 1, borderRadius: 2 } }],
    }, { cols: [["station", "Station"], ["exposition", "Exposition"], ["mois", "Mois"], ["pluie", "Pluie (mm)"], ["part_annuelle_pct", "% de l'année"]], rows });
  }

  function climat(t) {
    const st = cross.stations;
    carteStations(t, st); pluieAltitude(t, st); gradient(t, st); records(t, cross.records_pluie);
    rechauffement(t, cross.rechauffement); pluieAnnuelle(t, cross.pluie_annuelle); regimes(t, cross.regimes);
  }

  function featuresTable() {
    const ind = cross.indicators;
    const cols = [["nom", "Commune"], ["region", "Micro-région"], ["pop_2016", "Population 2016"],
                  ...cross.order.map(k => [k, `${ind[k].short}${ind[k].unit ? ` (${ind[k].unit})` : ""}`])];
    const box = document.getElementById("features-table");
    box.replaceChildren(renderTable({ cols, rows: cross.features }).querySelector("table"));
  }

  function renderCross() {
    const node = document.getElementById("cross-data");
    if (!node) return;
    cross = JSON.parse(node.textContent);
    const t = T();
    corrMatrix(t); pluie(t); chomage(t); climat(t); featuresTable();
    const sx = document.getElementById("sx"), sy = document.getElementById("sy");
    if (!sx.options.length) {
      for (const s of [sx, sy]) {
        s.innerHTML = cross.order.map(k => `<option value="${k}">${cross.indicators[k].label}</option>`).join("");
        s.onchange = () => loadPair(sx.value, sy.value);
      }
      sx.value = "revenu_median"; sy.value = "prix_m2";
    }
    loadPair(sx.value, sy.value);
  }

  document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll('[role="tab"]').forEach(b => (b.onclick = () => showTab(b.dataset.tab)));
    showTab(location.hash.slice(1), false);                 // onglet partageable par URL (#climat…)
    document.querySelectorAll("[data-chart]").forEach(actions);
    renderPanel(); renderCross();
    window.hljs?.highlightAll();
    document.getElementById("corr-toggle")?.addEventListener("click", (e) => {
      corrMode = corrMode === "pearson" ? "spearman" : "pearson";
      e.currentTarget.innerHTML = `coefficient : <b>${corrMode === "pearson" ? "Pearson" : "Spearman"}</b>`;
      corrMatrix(T());
    });
  });
  document.body.addEventListener("htmx:afterSettle", (e) => { if (e.detail.target.id === "panel") renderPanel(); });
  window.addEventListener("resize", () => Object.values(charts).forEach(c => c.resize()));
  window.addEventListener("hashchange", () => showTab(location.hash.slice(1), false));
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => { renderPanel(); renderCross(); });
})();
