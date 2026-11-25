/* Page BTP à La Réunion — rendu uniquement : les chiffres viennent des requêtes SQL (btp_queries.sql). */
(() => {
  const el = document.getElementById("page-data");
  if (!el) return;
  const P = JSON.parse(el.textContent);
  const css = (v) => getComputedStyle(document.body).getPropertyValue(v).trim();
  const fmt = (v, d = 0) => v == null ? "–" : Number(v).toLocaleString("fr-FR", { maximumFractionDigits: d, minimumFractionDigits: d }).replace(/ /g, " ");
  const mobile = () => innerWidth < 640;
  const charts = {}, pending = new Set();

  // Tranches de montant : séquence ordonnée du clair au foncé (une seule teinte, l'ordre se lit sans légende)
  const TRANCHE = [() => css("--b1"), () => css("--b2"), () => css("--b4"), () => css("--b5")];

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
  const BRUT = new Set(["annee", "rang", "ordre", "tranche_ordre", "premieres"]);
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

  /* ---------------- Commande publique ---------------- */
  function parAn() {
    const annees = [...new Set(P.bt_par_an.map(r => r.annee))];
    const cellule = (a, t) => P.bt_par_an.find(r => r.annee === a && r.tranche === t);
    dessiner("par_an", {
      ...base(),
      tooltip: { ...base().tooltip, trigger: "axis", axisPointer: { type: "shadow" },
        formatter: (ps) => `<b>${ps[0].axisValue}</b><br>` + [...ps].reverse().map(p => { const c = cellule(+p.axisValue, p.seriesName);
          return `${p.marker}${p.seriesName} : ${fmt(p.value)} marchés${c ? ` · ${fmt(c.montant_m, 1)} M€` : ""}`; }).join("<br>")
          + `<br><b>Total : ${fmt(ps.reduce((s, p) => s + (p.value || 0), 0))} marchés</b>` },
      xAxis: axe({ type: "category", data: annees }),
      yAxis: axe({ type: "value", name: "marchés" }),
      series: P.tranches.map((t, i) => ({
        name: t, type: "bar", stack: "an", barMaxWidth: 46, color: TRANCHE[i](), emphasis: { focus: "series" },
        data: annees.map(a => cellule(a, t)?.marches ?? 0),
      })),
    });
  }

  function barresH(id, rows, label, valeur, couleur, unite, extra) {
    const r = [...rows].reverse();  // la plus grande valeur en haut
    dessiner(id, {
      ...base(), grid: { ...base().grid, top: 8, right: 56 },
      tooltip: { ...base().tooltip, trigger: "item", formatter: (p) => extra(r[p.dataIndex]) },
      xAxis: axe({ type: "value" }),
      yAxis: axe({ type: "category", data: r.map(label), axisLabel: { color: css("--text-secondary"), fontSize: 11, width: mobile() ? 120 : 190, overflow: "truncate" } }),
      series: [{ type: "bar", barMaxWidth: 18, data: r.map(x => ({ value: valeur(x), itemStyle: { color: couleur(x), borderRadius: [0, 3, 3, 0] } })),
        label: { show: true, position: "right", fontSize: 10, color: css("--text-secondary"), formatter: p => fmt(p.value, p.value < 10 ? 1 : 0) + unite } }],
    });
  }

  const familles = () => barresH("familles", [...P.bt_familles].sort((a, b) => b.montant_m - a.montant_m), x => x.libelle, x => x.montant_m,
    x => x.libelle.startsWith("Non précisé") ? css("--muted") : css("--s1"), " M€",
    x => `<b>${x.libelle}</b><br>${fmt(x.marches)} marchés (${fmt(x.part_marches_pct, 1)} %)<br>${fmt(x.montant_m, 1)} M€ · marché médian ${fmt(x.median_k)} k€`);

  const acheteurs = () => barresH("acheteurs", P.bt_acheteurs_type, x => x.type_acheteur, x => x.montant_m,
    x => x.type_acheteur.startsWith("Autres") ? css("--muted") : css("--s4"), " M€",
    x => `<b>${x.type_acheteur}</b><br>${fmt(x.acheteurs)} acheteurs · ${fmt(x.marches)} marchés<br>${fmt(x.montant_m, 1)} M€ (${fmt(x.part_montant_pct, 1)} % du montant)`);

  function concurrence() {
    const r = P.bt_concurrence;
    const serie = (name, key, couleur) => ({ name, type: "bar", stack: "c", barMaxWidth: 34, color: couleur, data: r.map(x => x[key]),
      label: { show: !mobile(), formatter: p => p.value >= 8 ? fmt(p.value, 0) + " %" : "", color: "#fff", fontSize: 11 } });
    dessiner("concurrence", {
      ...base(), grid: { ...base().grid, right: 16 },
      tooltip: { ...base().tooltip, trigger: "axis", axisPointer: { type: "shadow" },
        formatter: (ps) => { const x = r[ps[0].dataIndex];
          return `<b>${x.tranche}</b> · ${fmt(x.marches)} marchés<br>` + ps.map(p => `${p.marker}${p.seriesName} : ${fmt(p.value, 1)} %`).join("<br>")
            + `<br>Médiane : ${fmt(x.offres_mediane, 1)} offres`; } },
      xAxis: axe({ type: "category", data: r.map(x => x.tranche), axisLabel: { color: css("--muted"), fontSize: 11, interval: 0,
        formatter: (v) => v.replace("Moins de ", "< ").replace("Plus de ", "> ").replace(" à ", " à\n") } }),
      yAxis: axe({ type: "value", max: 100, axisLabel: { color: css("--muted"), fontSize: 11, formatter: "{value} %" } }),
      series: [serie("Une seule offre", "une_offre_pct", css("--s2")), serie("2 ou 3 offres", "deux_trois_pct", css("--s4")),
               serie("4 offres ou plus", "quatre_plus_pct", css("--s3"))],
    });
  }

  /* ---------------- Entreprises ---------------- */
  function taille() {
    const cats = ["PME", "ETI", "GE", "Inconnue"].filter(c => P.bt_taille.some(r => r.categorie === c));
    const impl = [["À La Réunion", css("--s3")], ["Hors de La Réunion", css("--s2")], ["Inconnue", css("--muted")]];
    const cellule = (c, i) => P.bt_taille.find(r => r.categorie === c && r.implantation === i);
    const NOMS = { PME: "PME", ETI: "ETI (intermédiaires)", GE: "Grandes entreprises", Inconnue: "Taille inconnue" };
    dessiner("taille", {
      ...base(),
      tooltip: { ...base().tooltip, trigger: "axis", axisPointer: { type: "shadow" },
        formatter: (ps) => `<b>${ps[0].axisValue}</b><br>` + ps.filter(p => p.value).map(p => { const c = cellule(cats[p.dataIndex], p.seriesName);
          return `${p.marker}${p.seriesName} : ${fmt(p.value, 1)} % du montant<br>&nbsp;&nbsp;&nbsp;${fmt(c.entreprises)} entreprises, ${fmt(c.marches)} marchés`; }).join("<br>") },
      xAxis: axe({ type: "category", data: cats.map(c => NOMS[c]) }),
      yAxis: axe({ type: "value", axisLabel: { color: css("--muted"), fontSize: 11, formatter: "{value} %" } }),
      series: impl.map(([i, couleur]) => ({ name: i, type: "bar", stack: "t", barMaxWidth: 60, color: couleur,
        data: cats.map(c => cellule(c, i)?.part_montant_pct ?? 0) })),
    });
  }

  function concentration() {
    const r = P.bt_concentration;
    dessiner("concentration", {
      ...base(), grid: { ...base().grid, top: 16 },
      tooltip: { ...base().tooltip, trigger: "item", formatter: (p) => { const x = r[p.dataIndex];
        return `Les <b>${x.premieres}</b> premières entreprises (sur ${fmt(x.entreprises)})<br>captent ${fmt(x.part_pct, 1)} % du montant`; } },
      xAxis: axe({ type: "category", data: r.map(x => `${x.premieres} premières`) }),
      yAxis: axe({ type: "value", max: 100, axisLabel: { color: css("--muted"), fontSize: 11, formatter: "{value} %" } }),
      series: [{ type: "bar", barMaxWidth: 56, data: r.map(x => ({ value: x.part_pct, itemStyle: { color: css("--s1"), borderRadius: [3, 3, 0, 0] } })),
        label: { show: true, position: "top", color: css("--text-primary"), fontWeight: 600, formatter: p => fmt(p.value, 0) + " %" } }],
    });
  }

  /* ---------------- Logements ---------------- */
  function logements() {
    const r = P.bt_logements_an;
    dessiner("logements", {
      ...base(),
      tooltip: { ...base().tooltip, trigger: "axis", axisPointer: { type: "shadow" },
        formatter: (ps) => { const x = r[ps[0].dataIndex];
          return `<b>${x.annee}</b> · ${fmt(x.total)} logements${x.variation_pct == null ? "" : ` (${x.variation_pct > 0 ? "+" : ""}${fmt(x.variation_pct, 1)} %)`}<br>`
            + `${ps[0].marker}Individuel : ${fmt(x.individuel)}<br>${ps[1].marker}Collectif : ${fmt(x.collectif)}<br>${ps[2].marker}Part sociale : ${fmt(x.part_sociale_pct, 1)} %`; } },
      xAxis: axe({ type: "category", data: r.map(x => x.annee) }),
      yAxis: [axe({ type: "value", name: "logements" }), axe({ type: "value", max: 100, name: "% social", splitLine: { show: false },
        axisLabel: { color: css("--muted"), fontSize: 11, formatter: "{value} %" } })],
      series: [
        { name: "Individuel (maisons)", type: "bar", stack: "l", barMaxWidth: 46, color: css("--s4"), data: r.map(x => x.individuel) },
        { name: "Collectif (immeubles)", type: "bar", stack: "l", barMaxWidth: 46, color: css("--s1"), data: r.map(x => x.collectif) },
        { name: "Part de logements sociaux", type: "line", yAxisIndex: 1, color: css("--s2"), symbolSize: 7, lineStyle: { width: 3 },
          data: r.map(x => x.part_sociale_pct),
          label: { show: true, position: "top", formatter: p => fmt(p.value, 0) + " %", color: css("--text-primary"), fontSize: 11 } },
      ],
    });
  }

  const regions = () => barresH("regions", P.bt_logements_region, x => x.region, x => x.par_an_pour_1000hab, () => css("--s1"), "",
    x => `<b>${x.region}</b><br>${fmt(x.par_an_pour_1000hab, 1)} logements autorisés par an pour 1 000 habitants<br>${fmt(x.logements)} logements en 6 ans · ${fmt(x.part_collectif_pct, 0)} % en collectif`);

  const RENDU = { par_an: parAn, familles, acheteurs, concurrence, taille, concentration, logements, regions };
  const toutDessiner = () => Object.values(RENDU).forEach(f => f());

  /* ---------------- Onglets (l'adresse garde l'onglet : /btp#entreprises) ---------------- */
  function onglet(nom) {
    if (!document.getElementById("tab-" + nom)) nom = "commande";
    document.querySelectorAll(".tab").forEach(t => t.setAttribute("aria-selected", t.dataset.tab === nom));
    document.querySelectorAll("[role=tabpanel]").forEach(p => p.hidden = p.id !== "tab-" + nom);
    history.replaceState(null, "", "#" + nom);
    [...pending].forEach(id => { pending.delete(id); RENDU[id](); });
    Object.values(charts).forEach(c => c.resize());
  }
  document.querySelectorAll(".tab").forEach(t => t.onclick = () => onglet(t.dataset.tab));
  addEventListener("hashchange", () => onglet(location.hash.slice(1)));
  onglet(location.hash.slice(1) || "commande");
  if (document.readyState === "complete") toutDessiner(); else addEventListener("load", toutDessiner);
  hljs.highlightAll();
  addEventListener("resize", () => Object.values(charts).forEach(c => c.resize()));
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => { pending.clear(); toutDessiner(); });
})();
