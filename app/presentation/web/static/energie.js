/* Page Électricité de La Réunion — rendu uniquement : les chiffres viennent des requêtes SQL (energie_queries.sql). */
(() => {
  const el = document.getElementById("page-data");
  if (!el) return;
  const P = JSON.parse(el.textContent);
  const css = (v) => getComputedStyle(document.body).getPropertyValue(v).trim();
  const fmt = (v, d = 0) => v == null ? "–" : Number(v).toLocaleString("fr-FR", { maximumFractionDigits: d, minimumFractionDigits: d }).replace(/ /g, " ");
  const mobile = () => innerWidth < 640;
  const charts = {}, pending = new Set();

  // Fossile en gris (du plus sombre au plus clair), renouvelable en couleurs
  const COULEUR = {
    charbon: () => css("--text-secondary"), moteurs_diesel: () => css("--muted"), turbines_a_combustion_fioul: () => css("--axis"),
    bioenergie: () => css("--s3"), hydraulique: () => css("--s1"), solaire_photovoltaique: () => css("--s4"), eolien: () => css("--o1"),
  };
  const COULEUR_H = [() => css("--s2"), () => css("--muted"), () => css("--s1"), () => css("--s4"), () => css("--o1"), () => css("--s3")];

  const base = () => ({
    textStyle: { fontFamily: "system-ui, -apple-system, Segoe UI, sans-serif", color: css("--text-secondary") },
    grid: { left: 8, right: 24, top: mobile() ? 70 : 50, bottom: 8, containLabel: true },
    tooltip: { backgroundColor: css("--surface-1"), borderColor: css("--grid"), textStyle: { color: css("--text-primary"), fontSize: 12 }, confine: true },
    legend: { top: 0, left: 0, type: mobile() ? "scroll" : "plain", icon: "roundRect", itemWidth: 12, itemHeight: 8, textStyle: { color: css("--text-secondary") } },
  });
  const axe = (extra = {}) => ({
    axisLine: { lineStyle: { color: css("--axis") } }, axisTick: { show: false },
    axisLabel: { color: css("--muted"), fontSize: 11 }, splitLine: { lineStyle: { color: css("--grid") } },
    nameTextStyle: { color: css("--muted"), fontSize: 11 }, ...extra,
  });

  function dessiner(id, option) {
    const zone = document.querySelector(`[data-chart="${id}"] .chart`);
    if (!zone.offsetWidth) { pending.add(id); return; }  // onglet caché : on dessinera à l'affichage
    charts[id]?.dispose();
    charts[id] = echarts.init(zone, null, { renderer: "svg" });
    charts[id].setOption(option);
  }

  /* ---------------- Boutons « Tableau » et « SQL » ---------------- */
  const BRUT = new Set(["annee", "h", "rang", "ordre", "code_insee"]);
  function tableau(name) {
    const rows = P[name] || [];
    const cols = Object.keys(rows[0] || {});
    const td = (r, k) => typeof r[k] === "number" ? `<td class="n">${BRUT.has(k) ? r[k] : fmt(r[k], 1)}</td>` : `<td>${r[k] ?? "–"}</td>`;
    return `<div class="tbl"><table><thead><tr>${cols.map(c => `<th>${c}</th>`).join("")}</tr></thead>
      <tbody>${rows.map(r => `<tr>${cols.map(c => td(r, c)).join("")}</tr>`).join("")}</tbody></table></div>`;
  }
  document.querySelectorAll(".card[data-sql]").forEach(card => {
    const name = card.dataset.sql, q = P.sql[name];
    if (!q) return;
    const box = document.createElement("div");
    box.className = "card-actions";
    const bouton = (label, cls, contenu) => {
      const b = document.createElement("button");
      b.className = "btn-sm"; b.textContent = label;
      b.onclick = () => {
        const open = card.querySelector("." + cls);
        if (open) { open.remove(); return; }
        const div = document.createElement("div");
        div.className = cls; div.innerHTML = contenu();
        card.appendChild(div);
        div.querySelectorAll("code.language-sql").forEach(c => { c.textContent = q.sql; hljs.highlightElement(c); });
      };
      box.appendChild(b);
    };
    if (card.dataset.chart && P[name]) bouton("Tableau", "tbl-box", () => tableau(name));
    bouton("SQL", "sql-box", () => `<p class="sub">${q.description}</p><pre class="code"><code class="language-sql"></code></pre>`);
    card.appendChild(box);
  });

  /* ---------------- La bascule ---------------- */
  function mix() {
    const annees = P.en_part_q.map(r => r.annee);
    const series = P.filieres.map(f => ({
      name: f.libelle.split(" (")[0], type: "bar", stack: "mix", barMaxWidth: 46,
      color: COULEUR[f.filiere](), emphasis: { focus: "series" },
      data: annees.map(a => P.en_mix.find(m => m.annee === a && m.filiere === f.filiere)?.gwh ?? 0),
    }));
    series.push({ name: "Part renouvelable", type: "line", yAxisIndex: 1, color: css("--s3"), symbolSize: 7, lineStyle: { width: 3 },
      data: P.en_part_q.map(r => r.part_enr),
      label: { show: true, position: "top", formatter: p => fmt(p.value, 0) + " %", color: css("--text-primary"), fontWeight: 600, fontSize: 11 } });
    dessiner("mix", {
      ...base(),
      tooltip: { ...base().tooltip, trigger: "axis", axisPointer: { type: "shadow" },
        formatter: (ps) => `<b>${ps[0].axisValue}</b><br>` + ps.filter(p => p.value).map(p =>
          `${p.marker}${p.seriesName} : ${p.seriesType === "line" ? fmt(p.value, 1) + " %" : fmt(p.value) + " GWh"}`).join("<br>") },
      xAxis: axe({ type: "category", data: annees }),
      yAxis: [axe({ type: "value", name: "GWh" }), axe({ type: "value", max: 100, name: "% renouvelable", splitLine: { show: false },
        axisLabel: { color: css("--muted"), fontSize: 11, formatter: "{value} %" } })],
      series,
    });
  }

  function co2() {
    const r = P.en_co2_q;
    dessiner("co2", {
      ...base(), grid: { ...base().grid, top: 24 },
      tooltip: { ...base().tooltip, trigger: "axis", formatter: (ps) => { const x = r[ps[0].dataIndex];
        return `<b>${x.annee}</b><br>${fmt(x.kt)} kt de CO₂${x.variation_pct == null ? "" : `<br>${x.variation_pct > 0 ? "+" : ""}${fmt(x.variation_pct, 1)} % sur un an`}`; } },
      xAxis: axe({ type: "category", data: r.map(x => x.annee), axisLabel: { color: css("--muted"), fontSize: 11, interval: mobile() ? 1 : 0 } }),
      yAxis: axe({ type: "value" }),
      series: [{ type: "bar", barMaxWidth: 28, data: r.map(x => ({ value: x.kt, itemStyle: { color: x.annee >= 2022 ? css("--s3") : css("--muted"), borderRadius: [3, 3, 0, 0] } })),
        label: { show: true, position: "top", fontSize: 10, color: css("--text-secondary"), formatter: p => p.dataIndex >= r.length - 3 ? fmt(p.value) : "" } }],
    });
  }

  /* ---------------- Rythmes ---------------- */
  function journee() {
    const heures = [...new Set(P.en_journee.map(r => r.h))];
    dessiner("journee", {
      ...base(),
      tooltip: { ...base().tooltip, trigger: "axis",
        formatter: (ps) => `<b>${ps[0].axisValue} h</b><br>` + ps.filter(p => p.value > 0.5).reverse().map(p => `${p.marker}${p.seriesName} : ${fmt(p.value)} MW`).join("<br>")
          + `<br><b>Total : ${fmt(ps.reduce((s, p) => s + p.value, 0))} MW</b>` },
      xAxis: axe({ type: "category", data: heures, boundaryGap: false, axisLabel: { color: css("--muted"), fontSize: 11, formatter: "{value} h", interval: 2 } }),
      yAxis: axe({ type: "value", name: "MW" }),
      series: P.filieres_h.map((lib, i) => ({
        name: lib.split(" (")[0], type: "line", stack: "j", areaStyle: { opacity: 0.85 }, symbol: "none", lineStyle: { width: 0 },
        color: COULEUR_H[i](), data: heures.map(h => P.en_journee.find(r => r.h === h && r.ordre === i)?.mw ?? 0),
      })),
    });
  }

  function saisons() {
    const r = P.en_saisons;
    dessiner("saisons", {
      ...base(),
      tooltip: { ...base().tooltip, trigger: "axis", formatter: (ps) => `<b>${ps[0].axisValue} h</b><br>` + ps.map(p => `${p.marker}${p.seriesName} : ${fmt(p.value)} MW`).join("<br>") },
      xAxis: axe({ type: "category", data: r.map(x => x.h), boundaryGap: false, axisLabel: { color: css("--muted"), fontSize: 11, formatter: "{value} h", interval: 2 } }),
      yAxis: axe({ type: "value", name: "MW", min: 200 }),
      series: [
        { name: "Été austral (déc.-mars)", type: "line", data: r.map(x => x.ete_mw), color: css("--s2"), symbolSize: 4, lineStyle: { width: 3 } },
        { name: "Hiver austral (juin-sept.)", type: "line", data: r.map(x => x.hiver_mw), color: css("--s1"), symbolSize: 4, lineStyle: { width: 3 } },
      ],
    });
  }

  /* ---------------- Consommation ---------------- */
  function communes() {
    const r = [...P.en_communes].reverse();  // la plus forte consommation en haut
    const moyenne = P.en_communes.reduce((s, x) => s + x.mwh, 0) * 1000 / P.en_communes.reduce((s, x) => s + x.compteurs, 0);
    dessiner("communes", {
      ...base(), grid: { ...base().grid, top: 8, right: 48 },
      tooltip: { ...base().tooltip, trigger: "item", formatter: (p) => { const x = r[p.dataIndex];
        return `<b>${x.nom}</b>${x.hauts ? " · commune des Hauts" : ""}<br>${fmt(x.kwh_par_foyer)} kWh par foyer et par an<br>${fmt(x.compteurs)} compteurs résidentiels`; } },
      xAxis: axe({ type: "value", min: 2000 }),
      yAxis: axe({ type: "category", data: r.map(x => x.nom), axisLabel: { color: css("--text-secondary"), fontSize: 11 } }),
      series: [{ type: "bar", barMaxWidth: 14,
        data: r.map(x => ({ value: x.kwh_par_foyer, itemStyle: { color: x.hauts ? css("--s3") : css("--s1"), borderRadius: [0, 3, 3, 0] } })),
        label: { show: true, position: "right", fontSize: 10, color: css("--text-secondary"), formatter: p => fmt(p.value) },
        markLine: { symbol: "none", silent: true, lineStyle: { color: css("--text-secondary"), type: "dashed" },
          label: { formatter: `moyenne de l'île : ${fmt(moyenne)} kWh`, color: css("--text-secondary"), fontSize: 11, position: "insideEndTop" },
          data: [{ xAxis: moyenne }] } }],
    });
  }

  const RENDU = { mix, co2, journee, saisons, communes };
  const toutDessiner = () => Object.values(RENDU).forEach(f => f());

  /* ---------------- Onglets (l'adresse garde l'onglet : /energie#conso) ---------------- */
  function onglet(nom) {
    if (!document.getElementById("tab-" + nom)) nom = "bascule";
    document.querySelectorAll(".tab").forEach(t => t.setAttribute("aria-selected", t.dataset.tab === nom));
    document.querySelectorAll("[role=tabpanel]").forEach(p => p.hidden = p.id !== "tab-" + nom);
    history.replaceState(null, "", "#" + nom);
    [...pending].forEach(id => { pending.delete(id); RENDU[id](); });
    Object.values(charts).forEach(c => c.resize());
  }
  document.querySelectorAll(".tab").forEach(t => t.onclick = () => onglet(t.dataset.tab));
  addEventListener("hashchange", () => onglet(location.hash.slice(1)));
  onglet(location.hash.slice(1) || "bascule");
  if (document.readyState === "complete") toutDessiner(); else addEventListener("load", toutDessiner);
  hljs.highlightAll();
  addEventListener("resize", () => Object.values(charts).forEach(c => c.resize()));
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => { pending.clear(); toutDessiner(); });
})();
