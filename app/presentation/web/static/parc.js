/* Page Parc & IA — rendu uniquement : le score vient de la requête SQL fleet_risk. */
(() => {
  const P = JSON.parse(document.getElementById("page-data").textContent);
  const SQL = JSON.parse(document.getElementById("page-sql").textContent);
  const css = (v) => getComputedStyle(document.body).getPropertyValue(v).trim();
  const fmt = (v, d = 0) => v == null ? "–" : Number(v).toLocaleString("fr-FR", { maximumFractionDigits: d, minimumFractionDigits: d }).replace(/ /g, " ");
  const NIVEAU = { "CRITIQUE": "--div-pos", "ÉLEVÉ": "--s2", "À SURVEILLER": "--s4", "OK": "--s3" };
  let chart;

  function risque() {
    const zone = document.querySelector('[data-chart="risque"] .chart');
    const rows = [...P.risques].reverse();  // le plus risqué en haut
    chart?.dispose();
    chart = echarts.init(zone, null, { renderer: "svg" });
    chart.setOption({
      textStyle: { fontFamily: "system-ui, -apple-system, Segoe UI, sans-serif", color: css("--text-secondary") },
      grid: { left: 8, right: 40, top: 28, bottom: 8, containLabel: true },
      legend: { top: 0, left: 0, icon: "roundRect", itemWidth: 12, itemHeight: 8, textStyle: { color: css("--text-secondary") },
                data: Object.keys(NIVEAU), selectedMode: false },
      tooltip: { trigger: "item", backgroundColor: css("--surface-1"), borderColor: css("--grid"), confine: true,
        textStyle: { color: css("--text-primary"), fontSize: 12 },
        formatter: (p) => { const r = rows[p.dataIndex]; return `<b>${r.plaque}</b> · ${r.libelle}<br>${r.commune}<br>
          Risque <b>${r.score}</b>/100 (${r.niveau})<br>${r.pannes} panne(s) en 12 mois · ${fmt(r.cout)} €<br>
          Écart entre pannes : ${r.derive == null ? "–" : "×" + fmt(r.derive, 2) + " (sous 1 : elles se rapprochent)"}`; } },
      xAxis: { type: "value", max: 100, axisLabel: { color: css("--muted"), fontSize: 11 }, splitLine: { lineStyle: { color: css("--grid") } } },
      yAxis: { type: "category", data: rows.map(r => r.plaque), axisTick: { show: false },
               axisLine: { lineStyle: { color: css("--axis") } }, axisLabel: { color: css("--text-secondary"), fontSize: 11 } },
      series: [
        { type: "bar", barMaxWidth: 16, cursor: "pointer",
          data: rows.map(r => ({ value: r.score, itemStyle: { color: css(NIVEAU[r.niveau]), borderRadius: [0, 3, 3, 0] } })),
          label: { show: true, position: "right", color: css("--text-secondary"), fontSize: 11 } },
        // séries vides : seulement pour la légende des couleurs
        ...Object.entries(NIVEAU).map(([nom, c]) => ({ name: nom, type: "bar", data: [], itemStyle: { color: css(c) } })),
      ],
    });
    chart.on("click", (p) => {
      const r = rows[p.dataIndex];
      const sel = document.getElementById("vehicule");
      sel.value = [...sel.options].find(o => o.text.startsWith(r.plaque + " "))?.value ?? sel.value;
      document.getElementById("ia").scrollIntoView({ behavior: "smooth" });
      sel.form.requestSubmit();
    });
  }

  /* Boutons « Tableau » et « SQL » */
  function tableau() {
    return `<div class="tbl"><table><thead><tr><th>Véhicule</th><th>Commune</th><th>Pannes 12 m</th><th>Coût 12 m</th><th>Écart entre pannes</th><th>Risque</th></tr></thead>
      <tbody>${P.risques.map(r => `<tr><td>${r.plaque} · ${r.libelle}</td><td>${r.commune}</td><td>${r.pannes}</td>
      <td>${fmt(r.cout)} €</td><td>${r.derive == null ? "–" : "×" + fmt(r.derive, 2)}</td><td>${r.score} · ${r.niveau}</td></tr>`).join("")}</tbody></table></div>`;
  }
  document.querySelectorAll(".card[data-sql]").forEach(card => {
    const q = SQL[card.dataset.sql];
    if (!q) return;
    const box = document.createElement("div");
    box.className = "card-actions";
    const ajouter = (label, contenu) => {
      const b = document.createElement("button");
      b.className = "btn-sm"; b.textContent = label;
      b.onclick = () => {
        const ouvert = card.querySelector(`.extra[data-for="${label}"]`);
        card.querySelectorAll(".extra").forEach(e => e.remove());
        if (ouvert) return;
        const d = document.createElement("div");
        d.className = "extra mt-2"; d.dataset.for = label; d.innerHTML = contenu();
        card.appendChild(d);
        d.querySelectorAll("code").forEach(c => window.hljs?.highlightElement(c));
      };
      box.appendChild(b);
    };
    if (card.dataset.chart) ajouter("Tableau", tableau);
    ajouter("SQL", () => {
      const pre = document.createElement("pre"); const code = document.createElement("code");
      pre.className = "code"; code.className = "language-sql"; code.textContent = q; pre.appendChild(code);
      return pre.outerHTML;
    });
    card.prepend(box);
  });

  document.getElementById("exemple").onclick = () => {
    document.getElementById("texte").value = "OT-4999 — Transports Payet Express. Camion FG-482-RT immobilisé au 12 chemin des Lataniers, Le Port. "
      + "Fuite injecteur à 85 000 km, deuxième en quatre mois. Client à rappeler au 0262 42 18 07.";
  };

  addEventListener("load", risque);
  let t; addEventListener("resize", () => { clearTimeout(t); t = setTimeout(() => chart?.resize(), 150); });
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", risque);
})();
