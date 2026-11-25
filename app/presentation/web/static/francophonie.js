/* Page Francophonie canadienne — rendu uniquement : les chiffres viennent des requêtes SQL (francophonie_queries.sql). */
(() => {
  const el = document.getElementById("page-data");
  if (!el) return;
  const P = JSON.parse(el.textContent);
  const css = (v) => getComputedStyle(document.body).getPropertyValue(v).trim();
  const fmt = (v, d = 0) => v == null ? "–" : Number(v).toLocaleString("fr-FR", { maximumFractionDigits: d, minimumFractionDigits: d }).replace(/ /g, " ");
  const charts = {};
  const court = (r) => innerWidth < 640 ? r.code : r.nom;  // téléphone : abréviations officielles des provinces (NB, ON…)
  const pending = new Set();

  const base = () => ({
    textStyle: { fontFamily: "system-ui, -apple-system, Segoe UI, sans-serif", color: css("--text-secondary") },
    grid: { left: 8, right: 24, top: 40, bottom: 8, containLabel: true },
    tooltip: { backgroundColor: css("--surface-1"), borderColor: css("--grid"), textStyle: { color: css("--text-primary"), fontSize: 12 }, confine: true },
    legend: { top: 0, left: 0, type: innerWidth < 640 ? "scroll" : "plain", icon: "roundRect", itemWidth: 12, itemHeight: 8, textStyle: { color: css("--text-secondary") } },
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

  /* ---------------- Boutons « Tableau » et « SQL » de chaque bloc ---------------- */
  const COLS = {  // colonnes lisibles par requête (sinon : toutes)
    fr_paradoxe: [["an", "Année"], ["mat_fr", "Langue mat. française"], ["population", "Population"], ["mat_fr_pct", "Part %", 2], ["indice_fr", "Indice FR", 1], ["indice_pop", "Indice pop.", 1]],
    fr_haltere: [["nom", "Province"], ["pct_1951", "1951 %", 2], ["pct_2021", "2021 %", 2], ["ecart", "Écart (pts)", 1]],
    fr_variations: [["nom", "Province"], ["an_prec", "De"], ["an", "À"], ["variation_pct", "Variation %", 1]],
    fr_bilinguisme: [["nom", "Géographie"], ["an", "Année"], ["bilingues_pct", "Bilingues %", 2]],
    fr_ou: [["rang", "Rang"], ["nom", "Province / territoire"], ["plos_fr", "Francophones (PLOP)"], ["plos_fr_pct", "% de la province", 2], ["part_hq", "% du total hors Québec", 1]],
    fr_continuite: [["nom", "Province"], ["c_1971", "1971", 3], ["c_2021", "2021", 3], ["mat_fr_2021", "Langue mat. fr. 2021"], ["lecture", "Lecture"]],
    fr_series: [["nom", "Province"], ["an", "Année"], ["mat_fr_pct", "Langue mat. %", 2], ["maison_fr_pct", "Maison %", 2], ["plos_fr_pct", "1re langue off. %", 2], ["bilingues_pct", "Bilingues %", 2]],
    fr_immig_annuel: [["annee", "Année"], ["mois", "Mois"], ["francophones", "Francophones admis"], ["admissions_hq", "Toutes admissions hors Québec"], ["part_pct", "Part %", 1]],
    fr_immig_prov: [["nom", "Province"], ["francophones", "Francophones admis"], ["part_pct", "% des arrivants", 1]],
    fr_villes_classement: [["rang", "Rang"], ["nom", "Ville"], ["francophonie", "Francophonie", 0], ["cout", "Coût de la vie", 0], ["emploi", "Emploi", 0], ["cadre", "Cadre de vie", 0], ["total", "Total (poids égaux)", 1]],
    fr_villes_notes_q: [["nom", "Ville"], ["pilier", "Pilier"], ["libelle", "Indicateur"], ["valeur", "Valeur", 1], ["note", "Note /100", 0]],
  };
  function tableau(name) {
    const rows = P[name] || [];
    const cols = COLS[name] || Object.keys(rows[0] || {}).map(k => [k, k]);
    const brut = new Set(["an", "an_prec", "rang", "annee", "mois"]);
    const td = (r, [k, , d]) => typeof r[k] === "number" ? `<td class="n">${brut.has(k) ? r[k] : fmt(r[k], d ?? 0)}</td>` : `<td>${r[k] ?? "–"}</td>`;
    return `<div class="tbl"><table><thead><tr>${cols.map(([, l]) => `<th>${l}</th>`).join("")}</tr></thead>
      <tbody>${rows.map(r => `<tr>${cols.map(c => td(r, c)).join("")}</tr>`).join("")}</tbody></table></div>`;
  }
  document.querySelectorAll(".card[data-sql]").forEach(card => {
    const name = card.dataset.sql, q = P.sql[name];
    if (!q) return;
    const box = document.createElement("div");
    box.className = "card-actions";
    const bouton = (label, title, cls, contenu) => {
      const b = document.createElement("button");
      b.className = "btn-sm"; b.textContent = label; b.title = title;
      b.onclick = () => {
        const open = card.querySelector("." + cls);
        if (open) { open.remove(); return; }
        const div = document.createElement("div");
        div.className = cls;
        div.innerHTML = contenu();
        card.appendChild(div);
        div.querySelectorAll("code.language-sql").forEach(c => { c.textContent = q.sql; hljs.highlightElement(c); });
      };
      box.appendChild(b);
    };
    if (card.dataset.chart && P[name]) bouton("Tableau", "Voir les données de ce graphique", "tbl-box", () => tableau(name));
    bouton("SQL", "Voir la requête SQL de ce bloc", "sql-box", () => `<p class="sub">${q.description}</p><pre class="code"><code class="language-sql"></code></pre>`);
    card.appendChild(box);
  });

  /* ---------------- Évolution ---------------- */
  function paradoxe() {
    const r = P.fr_paradoxe;
    dessiner("paradoxe", {
      ...base(),
      tooltip: { ...base().tooltip, trigger: "axis", formatter: (ps) => {
        const x = r[ps[0].dataIndex];
        return `<b>${x.an}</b><br>Francophones : ${fmt(x.mat_fr)} (indice ${fmt(x.indice_fr)})<br>Population : ${fmt(x.population)} (indice ${fmt(x.indice_pop)})<br>Part : ${fmt(x.mat_fr_pct, 1)} %`;
      } },
      xAxis: axe({ type: "category", data: r.map(x => x.an), boundaryGap: false }),
      yAxis: axe({ type: "value", min: 0 }),
      series: [
        { name: "Population totale", type: "line", data: r.map(x => x.indice_pop), color: css("--muted"), symbolSize: 5, lineStyle: { width: 2 },
          endLabel: { show: true, formatter: p => fmt(p.value), color: css("--text-secondary") } },
        { name: "Langue maternelle française", type: "line", data: r.map(x => x.indice_fr), color: css("--s1"), symbolSize: 5, lineStyle: { width: 3 },
          endLabel: { show: true, formatter: p => fmt(p.value), color: css("--s1") } },
      ],
      grid: { ...base().grid, right: 40 },
    });
  }

  // Haltère : un trait dessiné entre les deux valeurs (série custom), un rond gris (avant) et un rond bleu (après).
  // Échelle log en option : un même rapport (÷2) occupe la même longueur, quelle que soit la province.
  function haltere(id, rows, kA, kB, labelA, labelB, { scale = 1, unit = " %", log = false } = {}) {
    const a = rows.map(r => r[kA] == null ? null : r[kA] * scale);
    const b = rows.map(r => r[kB] * scale);
    const fmtAxe = v => (v > 0 && v < 1 ? fmt(v, 2) : fmt(v)) + unit.trim();
    dessiner(id, {
      ...base(),
      grid: { ...base().grid, top: 30, right: 36 },
      tooltip: { ...base().tooltip, trigger: "axis", axisPointer: { type: "shadow" }, formatter: (ps) => {
        const i = ps[0].dataIndex, r = rows[i];
        const ratio = a[i] ? ` (×${fmt(b[i] / a[i], 2)})` : "";
        return `<b>${r.nom}</b><br>${labelA} : ${fmt(a[i], 1)}${unit}<br>${labelB} : ${fmt(b[i], 1)}${unit}${ratio}`;
      } },
      legend: { ...base().legend, data: [labelA, labelB] },
      xAxis: axe(log ? { type: "log", logBase: innerWidth < 640 ? 4 : 2, min: 0.25, max: 64, axisLabel: { color: css("--muted"), fontSize: 11, formatter: fmtAxe } }
                     : { type: "value", min: 0, max: 100, axisLabel: { color: css("--muted"), fontSize: 11, formatter: fmtAxe } }),
      yAxis: axe({ type: "category", data: rows.map(court), axisLabel: { color: css("--text-secondary"), fontSize: 11 } }),
      series: [
        { type: "custom", silent: true, z: 1, encode: { x: [0, 1], y: 2 },
          data: rows.map((r, i) => [a[i] ?? b[i], b[i], i]),
          renderItem: (p, api) => {
            const p1 = api.coord([api.value(0), api.value(2)]), p2 = api.coord([api.value(1), api.value(2)]);
            return { type: "line", shape: { x1: p1[0], y1: p1[1], x2: p2[0], y2: p2[1] }, style: { stroke: css("--axis"), lineWidth: 3 } };
          } },
        { name: labelA, type: "scatter", z: 2, data: a, symbolSize: 10, itemStyle: { color: css("--muted"), opacity: 1 } },
        { name: labelB, type: "scatter", z: 3, data: b.map((v, i) => ({ value: v, label: { position: a[i] != null && v < a[i] ? "left" : "right" } })),
          symbolSize: 11, itemStyle: { color: css("--s1"), opacity: 1 },
          label: { show: true, formatter: p => fmt(p.value, 1), color: css("--text-primary"), fontSize: 11 } },
      ],
    });
  }

  function variations() {
    const r = P.fr_variations;
    const periodes = [...new Set(r.map(x => `${x.an_prec}→${String(x.an).slice(2)}`))];
    const ordre = [...P.fr_haltere].reverse().map(x => x.nom);  // même ordre que l'haltère : la plus francophone en haut
    const lim = Math.max(...r.map(x => Math.abs(x.variation_pct)));
    dessiner("variations", {
      ...base(),
      grid: { ...base().grid, top: 8, bottom: 40 },
      tooltip: { ...base().tooltip, formatter: p => `<b>${ordre[p.value[1]]}</b><br>${periodes[p.value[0]]} : ${p.value[2] > 0 ? "+" : ""}${fmt(p.value[2], 1)} %` },
      xAxis: axe({ type: "category", data: periodes, splitArea: { show: false }, axisLabel: { color: css("--muted"), fontSize: 10, rotate: innerWidth < 640 ? 45 : 0 } }),
      yAxis: axe({ type: "category", data: P.fr_haltere.map(court), axisLabel: { color: css("--text-secondary"), fontSize: 11 } }),
      visualMap: { type: "continuous", min: -lim, max: lim, dimension: 2, orient: "horizontal", left: "center", bottom: 0, itemHeight: 160, itemWidth: 10,
                   text: ["hausse", "baisse"], textStyle: { color: css("--muted"), fontSize: 11 }, calculable: false,
                   inRange: { color: [css("--div-pos"), css("--div-mid"), css("--div-neg")] } },
      series: [{ type: "heatmap", itemStyle: { borderColor: css("--surface-1"), borderWidth: 1 },
        label: { show: innerWidth > 640, fontSize: 9, color: css("--text-primary"), formatter: p => fmt(p.value[2], 0) },
        data: r.map(x => [periodes.indexOf(`${x.an_prec}→${String(x.an).slice(2)}`), ordre.length - 1 - ordre.indexOf(x.nom), x.variation_pct]) }],
    });
  }

  function bilinguisme() {
    const geos = [["QC", "--s2"], ["NB", "--s3"], ["CA", "--s4"], ["HQ", "--s1"]];
    const ans = [...new Set(P.fr_bilinguisme.map(x => x.an))];
    dessiner("bilinguisme", {
      ...base(),
      grid: { ...base().grid, right: 48, top: 48 },
      tooltip: { ...base().tooltip, trigger: "axis", valueFormatter: v => fmt(v, 1) + " %" },
      xAxis: axe({ type: "category", data: ans, boundaryGap: false }),
      yAxis: axe({ type: "value", min: 0, axisLabel: { color: css("--muted"), fontSize: 11, formatter: v => v + " %" } }),
      series: geos.map(([code, c]) => {
        const rows = P.fr_bilinguisme.filter(x => x.code === code);
        return { name: rows[0].nom, type: "line", data: rows.map(x => x.bilingues_pct), color: css(c), symbolSize: 4, lineStyle: { width: code === "HQ" ? 3 : 2 },
                 endLabel: { show: true, formatter: p => fmt(p.value, 0) + " %", color: css(c), fontSize: 11 } };
      }),
    });
  }

  /* ---------------- Où vivre ---------------- */
  function ou() {
    const r = [...P.fr_ou].reverse();
    dessiner("ou", {
      ...base(),
      grid: { ...base().grid, top: 8, right: 70 },
      tooltip: { ...base().tooltip, trigger: "axis", axisPointer: { type: "shadow" }, formatter: ps => {
        const x = r[ps[0].dataIndex];
        return `<b>${x.nom}</b><br>${fmt(x.plos_fr)} francophones<br>${fmt(x.plos_fr_pct, 1)} % de la population<br>${fmt(x.part_hq, 1)} % des francophones hors Québec`;
      } },
      xAxis: axe({ type: "value", axisLabel: { color: css("--muted"), fontSize: 11, formatter: v => v >= 1000 ? fmt(v / 1000) + " k" : v } }),
      yAxis: axe({ type: "category", data: r.map(court), axisLabel: { color: css("--text-secondary"), fontSize: 11 } }),
      series: [{ type: "bar", data: r.map(x => x.plos_fr), barMaxWidth: 18, color: css("--s1"),
                 label: { show: true, position: "right", formatter: p => `${fmt(r[p.dataIndex].part_hq, 1)} %`, color: css("--text-secondary"), fontSize: 11 } }],
    });
  }

  let province = P.provinces[0];
  function fiche() {
    const rows = P.fr_series.filter(x => x.code === province);
    const hq = P.fr_series.filter(x => x.code === "HQ");
    const ans = [...new Set(P.fr_series.map(x => x.an))].sort();
    const at = (arr, k) => ans.map(a => arr.find(x => x.an === a)?.[k] ?? null);
    const S = [["mat_fr_pct", "Langue maternelle", "--s1"], ["maison_fr_pct", "Langue de la maison", "--s3"],
               ["plos_fr_pct", "1re langue officielle", "--s4"], ["bilingues_pct", "Bilingues", "--s2"]];
    dessiner("fiche", {
      ...base(),
      grid: { ...base().grid, top: 48, right: 48 },
      tooltip: { ...base().tooltip, trigger: "axis", valueFormatter: v => v == null ? "–" : fmt(v, 1) + " %" },
      xAxis: axe({ type: "category", data: ans, boundaryGap: false }),
      yAxis: axe({ type: "value", min: 0, axisLabel: { color: css("--muted"), fontSize: 11, formatter: v => v + " %" } }),
      series: [
        ...S.map(([k, l, c]) => ({ name: l, type: "line", data: at(rows, k), color: css(c), connectNulls: false, symbolSize: 4, lineStyle: { width: 2 } })),
        { name: "Hors Québec (langue mat.)", type: "line", data: at(hq, "mat_fr_pct"), color: css("--muted"), symbol: "none", lineStyle: { width: 1.5, type: "dashed" } },
      ],
    });
  }
  const chips = document.getElementById("provinces");
  const nomDe = Object.fromEntries(P.fr_series.map(x => [x.code, x.nom]));
  P.provinces.forEach(code => {
    const b = document.createElement("button");
    b.className = "chip"; b.textContent = nomDe[code]; b.setAttribute("aria-pressed", code === province);
    b.onclick = () => { province = code; chips.querySelectorAll(".chip").forEach(c => c.setAttribute("aria-pressed", c === b)); fiche(); };
    chips.appendChild(b);
  });

  /* ---------------- Immigration depuis 2015 ---------------- */
  function immigAnnuel() {
    const r = P.fr_immig_annuel;
    dessiner("immig_annuel", {
      ...base(),
      grid: { ...base().grid, top: 24 },
      tooltip: { ...base().tooltip, trigger: "axis", axisPointer: { type: "shadow" }, formatter: ps => {
        const x = r[ps[0].dataIndex];
        return `<b>${x.annee}</b>${x.mois < 12 ? ` (${x.mois} mois)` : ""}<br>${fmt(x.francophones)} francophones admis<br>${fmt(x.part_pct, 1)} % des admissions hors Québec`;
      } },
      xAxis: axe({ type: "category", data: r.map(x => x.annee) }),
      yAxis: axe({ type: "value", axisLabel: { color: css("--muted"), fontSize: 11, formatter: v => fmt(v / 1000) + " k" } }),
      series: [{ type: "bar", barMaxWidth: 28,
        data: r.map(x => ({ value: x.francophones, itemStyle: { color: x.mois < 12 ? css("--o1") : css("--s1") } })),
        label: { show: innerWidth > 640, position: "top", fontSize: 10, color: css("--text-secondary"), formatter: p => fmt(p.value / 1000, 1) + " k" } }],
    });
  }

  function immigPart() {
    const r = P.fr_immig_annuel, ans = r.map(x => x.annee);
    const cible = Object.fromEntries(P.cibles.map(c => [c.annee, c.cible_pct]));
    dessiner("immig_part", {
      ...base(),
      grid: { ...base().grid, top: 40, right: 40 },
      tooltip: { ...base().tooltip, trigger: "axis", valueFormatter: v => v == null ? "–" : fmt(v, 1) + " %" },
      xAxis: axe({ type: "category", data: ans, boundaryGap: false }),
      yAxis: axe({ type: "value", min: 0, axisLabel: { color: css("--muted"), fontSize: 11, formatter: v => v + " %" } }),
      series: [
        { name: "Part réalisée", type: "line", data: r.map(x => x.part_pct), color: css("--s1"), symbolSize: 6, lineStyle: { width: 3 },
          endLabel: { show: true, formatter: p => fmt(p.value, 1) + " %", color: css("--s1") } },
        { name: "Cible fédérale", type: "scatter", data: ans.map(a => cible[a] ?? null), color: css("--s2"), symbol: "diamond", symbolSize: 12 },
      ],
    });
  }

  function immigProv() {
    const r = [...P.fr_immig_prov].filter(x => x.francophones >= 50).reverse();
    dessiner("immig_prov", {
      ...base(),
      grid: { ...base().grid, top: 8, right: 60 },
      tooltip: { ...base().tooltip, trigger: "axis", axisPointer: { type: "shadow" }, formatter: ps => {
        const x = r[ps[0].dataIndex];
        return `<b>${x.nom}</b><br>${fmt(x.francophones)} francophones admis<br>${fmt(x.part_pct, 1)} % des arrivants de la province`;
      } },
      xAxis: axe({ type: "value", axisLabel: { color: css("--muted"), fontSize: 11, formatter: v => v >= 1000 ? fmt(v / 1000) + " k" : v } }),
      yAxis: axe({ type: "category", data: r.map(court), axisLabel: { color: css("--text-secondary"), fontSize: 11 } }),
      series: [{ type: "bar", data: r.map(x => x.francophones), barMaxWidth: 18, color: css("--s1"),
        label: { show: true, position: "right", formatter: p => `${fmt(r[p.dataIndex].part_pct, 1)} %`, color: css("--text-secondary"), fontSize: 11 } }],
    });
  }

  /* ---------------- Choisir sa ville ---------------- */
  const PILIERS = P.piliers.map(x => x.pilier);
  const CLE = { "Francophonie": "francophonie", "Coût de la vie": "cout", "Emploi": "emploi", "Cadre de vie": "cadre" };
  const COUL = { "Francophonie": "--s1", "Coût de la vie": "--s3", "Emploi": "--s4", "Cadre de vie": "--s2" };
  const poids = Object.fromEntries(PILIERS.map(p => [p, 1]));
  const zonePoids = document.getElementById("poids");
  PILIERS.forEach(p => {
    const l = document.createElement("label");
    l.className = "text-sm flex items-center gap-2";
    l.innerHTML = `<span style="min-width:9.5em"><i style="display:inline-block;width:10px;height:10px;border-radius:2px;background:var(${COUL[p]});margin-right:5px"></i>${p}</span>
      <input type="range" min="0" max="3" step="1" value="1" style="flex:1;accent-color:var(${COUL[p]})" aria-label="Poids du pilier ${p}"><b class="w-6 text-right">×1</b>`;
    const input = l.querySelector("input"), sortie = l.querySelector("b");
    input.oninput = () => { poids[p] = +input.value; sortie.textContent = "×" + input.value; classement(); };
    zonePoids.appendChild(l);
  });

  function classement() {
    const total = PILIERS.reduce((s, p) => s + poids[p], 0) || 1;
    const rows = P.fr_villes_classement.map(v => ({ ...v, score: PILIERS.reduce((s, p) => s + poids[p] * v[CLE[p]], 0) / total }))
      .sort((a, b) => a.score - b.score);
    dessiner("classement", {
      ...base(),
      grid: { ...base().grid, top: 30, right: 48 },
      tooltip: { ...base().tooltip, trigger: "axis", axisPointer: { type: "shadow" }, formatter: ps => {
        const v = rows[ps[0].dataIndex];
        return `<b>${v.nom}</b> · ${fmt(v.score, 0)}/100<br>` + PILIERS.map(p => `${p} : ${fmt(v[CLE[p]], 0)} (poids ×${poids[p]})`).join("<br>");
      } },
      legend: { ...base().legend, data: PILIERS },
      xAxis: axe({ type: "value", max: 100 }),
      yAxis: axe({ type: "category", data: rows.map(v => v.nom), axisLabel: { color: css("--text-secondary"), fontSize: 12 } }),
      series: PILIERS.map((p, i) => ({
        name: p, type: "bar", stack: "s", barMaxWidth: 22, color: css(COUL[p]),
        data: rows.map(v => +(poids[p] * v[CLE[p]] / total).toFixed(1)),
        label: i === PILIERS.length - 1 ? { show: true, position: "right", color: css("--text-primary"), fontSize: 12, fontWeight: 600,
                                            formatter: q => fmt(rows[q.dataIndex].score, 0) } : undefined,
      })),
    });
  }

  // Parallèle : axes en valeurs brutes, inversés quand « moins, c'est mieux », pour que le haut soit toujours le mieux
  const IND = P.piliers.flatMap(x => x.indicateurs.map(i => ({ ...i, pilier: x.pilier })));
  const valeurs = Object.fromEntries(P.fr_villes_tableau.map(v => [v.nom, v]));
  const VILLES = P.fr_villes_classement.map(v => v.nom);
  const choisies = new Set(VILLES.slice(0, 3));
  const COURT = { plop_fr_pct: "Francophones %", maison_fr_pct: "Français maison %", enfants_fr_pct: "Enfants fr. %",
                  part_fr_arrivees: "Arrivants fr. %", loyer: "Loyer $", mpc: "Panier $", pouvoir_achat: "Revenu ÷ panier",
                  chomage: "Chômage %", revenu: "Revenu $", criminalite: "Criminalité", satisfaction: "Satisfaits %" };
  function parallele() {
    const palette = ["--s1", "--s2", "--s3", "--s4"];
    let k = 0;
    const couleur = Object.fromEntries(VILLES.map(v => [v, choisies.has(v) ? css(palette[k++ % 4]) : css("--axis")]));
    const large = document.querySelector('[data-chart="parallele"]').offsetWidth > 560;
    dessiner("parallele", {
      ...base(),
      legend: { show: false },  // les puces au-dessus servent de légende, couleurs comprises
      tooltip: { ...base().tooltip, trigger: "item", formatter: p => `<b>${p.seriesName}</b>` },
      parallel: { left: 24, right: 48, top: 64, bottom: 16, parallelAxisDefault: {
        nameLocation: "end", nameGap: 12, nameRotate: innerWidth < 640 ? 60 : 25, nameTextStyle: { color: css("--text-secondary"), fontSize: 10 },
        axisLine: { lineStyle: { color: css("--axis") } }, axisTick: { show: false },
        axisLabel: { show: large, color: css("--muted"), fontSize: 9, formatter: v => fmt(v, v < 10 ? 1 : 0) }, splitLine: { show: false } } },
      parallelAxis: IND.map((ind, d) => {
        const xs = VILLES.map(v => valeurs[v][ind.indicateur]);
        const lo = Math.min(...xs), hi = Math.max(...xs), pad = (hi - lo) * 0.05;
        // axe inversé : son « haut » est le début de l'axe, le nom doit y rester
        return { dim: d, name: COURT[ind.indicateur] + (ind.sens < 0 ? " ↓" : ""), inverse: ind.sens < 0,
                 nameLocation: ind.sens < 0 ? "start" : "end", min: +(lo - pad).toFixed(2), max: +(hi + pad).toFixed(2) };
      }),
      series: VILLES.map(v => ({
        name: v, type: "parallel", smooth: false, z: choisies.has(v) ? 3 : 1,
        lineStyle: { color: couleur[v], width: choisies.has(v) ? 3 : 1, opacity: choisies.has(v) ? 1 : 0.5 },
        data: [IND.map(ind => valeurs[v][ind.indicateur])],
      })),
    });
  }
  const sel = document.getElementById("villes-sel");
  VILLES.forEach(v => {
    const b = document.createElement("button");
    b.className = "chip"; b.textContent = v; b.setAttribute("aria-pressed", choisies.has(v));
    b.onclick = () => {
      if (choisies.has(v)) choisies.delete(v); else { if (choisies.size >= 4) return; choisies.add(v); }  // 4 couleurs au plus
      b.setAttribute("aria-pressed", choisies.has(v)); parallele(); teinter();
    };
    sel.appendChild(b);
  });
  function teinter() {  // la puce d'une ville choisie prend la couleur de sa ligne
    const palette = ["--s1", "--s2", "--s3", "--s4"];
    let k = 0;
    sel.querySelectorAll(".chip").forEach(b => {
      const on = choisies.has(b.textContent);
      b.style.background = on ? `var(${palette[k++ % 4]})` : ""; b.style.color = on ? "#fff" : ""; b.style.borderColor = on ? "transparent" : "";
    });
  }
  teinter();

  function arbitrage() {
    const r = P.fr_villes_classement;
    dessiner("arbitrage", {
      ...base(),
      grid: { ...base().grid, top: 30, right: 40, bottom: 24 },
      tooltip: { ...base().tooltip, formatter: p => { const v = r[p.dataIndex];
        return `<b>${v.nom}</b><br>Francophonie : ${fmt(v.francophonie, 0)}<br>Coût de la vie : ${fmt(v.cout, 0)}<br>Emploi : ${fmt(v.emploi, 0)}`; } },
      xAxis: axe({ type: "value", min: 0, max: 100, name: "francophonie", nameLocation: "middle", nameGap: 26 }),
      yAxis: axe({ type: "value", min: 0, max: 100, name: "coût de la vie (100 = le plus abordable)", nameLocation: "end",
                   nameTextStyle: { color: css("--muted"), fontSize: 11, align: "left" } }),
      series: [{ type: "scatter", data: r.map(v => [v.francophonie, v.cout, v.emploi]), symbolSize: d => 8 + d[2] / 6,
        itemStyle: { color: css("--s1"), opacity: 0.85 },
        label: { show: true, position: "right", formatter: p => r[p.dataIndex].nom, color: css("--text-primary"), fontSize: 11 },
        labelLayout: { hideOverlap: true },
        markLine: { silent: true, symbol: "none", lineStyle: { color: css("--grid"), type: "dashed" }, label: { show: false },
                    data: [{ xAxis: 50 }, { yAxis: 50 }] } }],
    });
  }

  const RENDU = {
    paradoxe, variations, bilinguisme, ou, fiche,
    haltere: () => haltere("haltere", P.fr_haltere, "pct_1951", "pct_2021", "1951", "2021", { log: true }),
    continuite: () => haltere("continuite", [...P.fr_continuite].reverse(), "c_1971", "c_2021", "1971", "2021", { scale: 100, unit: "" }),
    immig_annuel: immigAnnuel, immig_part: immigPart, immig_prov: immigProv, classement, parallele, arbitrage,
  };
  const toutDessiner = () => Object.values(RENDU).forEach(f => f());

  /* ---------------- Onglets (l'adresse garde l'onglet : /francophonie#vivre) ---------------- */
  function onglet(nom) {
    if (!document.getElementById("tab-" + nom)) nom = "evolution";
    document.querySelectorAll(".tab").forEach(t => t.setAttribute("aria-selected", t.dataset.tab === nom));
    document.querySelectorAll("[role=tabpanel]").forEach(p => p.hidden = p.id !== "tab-" + nom);
    history.replaceState(null, "", "#" + nom);
    [...pending].forEach(id => { pending.delete(id); RENDU[id](); });
    Object.values(charts).forEach(c => c.resize());
  }
  document.querySelectorAll(".tab").forEach(t => t.onclick = () => onglet(t.dataset.tab));
  addEventListener("hashchange", () => onglet(location.hash.slice(1)));
  onglet(location.hash.slice(1) || "evolution");
  // Après « load » : Tailwind (CDN) a posé la grille, les blocs ont leur vraie largeur
  if (document.readyState === "complete") toutDessiner(); else addEventListener("load", toutDessiner);
  hljs.highlightAll();
  addEventListener("resize", () => Object.values(charts).forEach(c => c.resize()));
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => { pending.clear(); toutDessiner(); });
})();
