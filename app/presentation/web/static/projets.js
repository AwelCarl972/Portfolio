/* Page Projets — rendu uniquement : les chiffres viennent des requêtes SQL (projets_queries.sql). */
(() => {
  const el = document.getElementById("page-data");
  if (!el) return;
  const P = JSON.parse(el.textContent);
  const css = (v) => getComputedStyle(document.body).getPropertyValue(v).trim();
  const fmt = (v, d = 0) => v == null ? "–" : Number(v).toLocaleString("fr-FR", { maximumFractionDigits: d }).replace(/ /g, " ");
  const MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"];
  const charts = {};

  // Classes de puissance : une échelle ordinale (du plus lent au plus puissant), le gris pour l'inconnu
  const CLASSES = ["Normale (< 8 kW)", "Accélérée (8-22 kW)", "Rapide (23-99 kW)", "Haute puissance (≥ 100 kW)", "Non renseignée"];
  const classeCouleur = () => [css("--b1"), css("--b2"), css("--b4"), css("--b5"), css("--muted")];
  const classeDe = (kw) => kw == null ? 4 : kw < 8 ? 0 : kw <= 22.5 ? 1 : kw < 100 ? 2 : 3;

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
    const card = document.querySelector(`[data-chart="${id}"]`);
    const zone = card.querySelector(".chart");
    if (!zone.offsetWidth) return;  // onglet caché : on dessinera à l'affichage
    charts[id]?.dispose();
    charts[id] = echarts.init(zone, null, { renderer: "svg" });
    charts[id].setOption(option);
  }

  /* ---------------- Boutons « SQL » : la requête source de chaque bloc ---------------- */
  document.querySelectorAll(".card[data-sql]").forEach(card => {
    const q = P.sql[card.dataset.sql];
    if (!q) return;
    const box = document.createElement("div");
    box.className = "card-actions";
    const b = document.createElement("button");
    b.className = "btn-sm"; b.textContent = "SQL"; b.title = "Voir la requête SQL de ce bloc";
    b.onclick = () => {
      const open = card.querySelector(".sql-box");
      if (open) { open.remove(); return; }
      const div = document.createElement("div");
      div.className = "sql-box";
      div.innerHTML = `<p class="sub">${q.description}</p><pre class="code"><code class="language-sql"></code></pre>`;
      div.querySelector("code").textContent = q.sql;
      card.appendChild(div);
      hljs.highlightElement(div.querySelector("code"));
    };
    box.appendChild(b);
    card.appendChild(box);
  });

  /* ---------------- Bornes : graphique annuel ---------------- */
  function annuel() {
    const rows = P.bornes.annuel;
    const annees = [...new Set(rows.map(r => r.annee))].filter(a => a >= 2014);
    const couleurs = classeCouleur();
    dessiner("annuel", {
      ...base(),
      grid: { ...base().grid, top: 64 },
      tooltip: { ...base().tooltip, trigger: "axis", axisPointer: { type: "shadow" },
                 valueFormatter: v => fmt(v) + " points" },
      xAxis: axe({ type: "category", data: annees }),
      yAxis: axe({ type: "value", axisLabel: { color: css("--muted"), fontSize: 11, formatter: v => fmt(v) } }),
      series: CLASSES.map((c, i) => ({
        name: c, type: "bar", stack: "t", barMaxWidth: 28, itemStyle: { color: couleurs[i] },
        emphasis: { focus: "series" },
        data: annees.map(a => rows.find(r => r.annee === a && r.classe === c)?.n ?? 0),
      })),
    });
  }

  /* ---------------- Bornes : la carte animée ---------------- */
  // Cadres plutôt que centre + zoom : le zoom qui montre la France sur un écran large la coupe sur un téléphone
  const VUES = { metropole: [[41.4, -5.0], [51.1, 9.5]], reunion: [[-21.39, 55.21], [-20.87, 55.84]], antilles: [[14.38, -61.25], [16.52, -60.8]] };
  let carte, calque, sites = [], marqueurs = [], rangMax = 0, rang = 0, minuteur = null, fond = null;

  const rayon = (n) => 1.6 + Math.min(4.4, Math.sqrt(n) / 1.6);  // 30 000 sites : de petits ronds, sinon la France sature
  // Vue d'ensemble (petit zoom, téléphone) : ronds réduits, sinon le parc n'est plus qu'une tache
  const echelle = () => Math.max(0.45, Math.min(1, (carte.getZoom() - 3) / 4));
  const libelleRang = (r) => `${MOIS[r % 12]} ${2010 + Math.floor(r / 12)}`;
  const cumul = Object.fromEntries(P.bornes.cumul.map(c => [c.mois, c.cumul]));
  const cumulAu = (r) => {  // parc cumulé au dernier mois connu ≤ r
    for (let i = r; i >= 0; i--) {
      const m = `${2010 + Math.floor(i / 12)}-${String(i % 12 + 1).padStart(2, "0")}`;
      if (cumul[m] != null) return cumul[m];
    }
    return 0;
  };

  function fondDeCarte() {
    const sombre = matchMedia("(prefers-color-scheme: dark)").matches;
    // Fond OpenStreetMap standard (sans clé) ; en mode sombre, ses tuiles sont inversées par CSS
    document.getElementById("carte").classList.toggle("sombre", sombre);
    if (fond) return;
    fond = L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: "© contributeurs OpenStreetMap", maxZoom: 18,
    }).addTo(carte);
  }

  function afficher(r) {
    rang = r;
    const curseur = document.getElementById("mois");
    curseur.value = r;
    curseur.style.setProperty("--p", `${(100 * (r - curseur.min)) / ((curseur.max - curseur.min) || 1)}%`);
    marqueurs.forEach((m, i) => {
      const visible = sites[i].rang <= r;
      if (visible && !calque.hasLayer(m)) calque.addLayer(m);
      else if (!visible && calque.hasLayer(m)) calque.removeLayer(m);
    });
    document.getElementById("date-carte").innerHTML = `<b>${libelleRang(r)}</b> · ${fmt(cumulAu(r))} points ouverts`;
  }

  function lecture() {
    const b = document.getElementById("lecture");
    if (minuteur) { clearInterval(minuteur); minuteur = null; b.textContent = "▶ Lecture"; return; }
    if (rang >= rangMax) afficher(48);  // reprise au début de 2014, quand le parc décolle
    b.textContent = "❚❚ Pause";
    minuteur = setInterval(() => {
      if (rang >= rangMax) { lecture(); return; }
      afficher(rang + 1);
    }, 120);
  }

  async function initCarte() {
    if (carte) return;
    carte = L.map("carte", { preferCanvas: true, zoomSnap: 0.5, scrollWheelZoom: false });  // la molette fait défiler la page, pas la carte
    carte.fitBounds(VUES.metropole);
    fondDeCarte();
    matchMedia("(prefers-color-scheme: dark)").addEventListener("change", fondDeCarte);
    calque = L.layerGroup().addTo(carte);
    sites = await (await fetch("/projets/donnees/bornes_sites.json")).json();
    const renderer = L.canvas({ padding: 0.5 });
    const couleurs = classeCouleur();
    marqueurs = sites.map(s => L.circleMarker([s.lat, s.lon], {
      renderer, radius: rayon(s.points), weight: 0, fillOpacity: 0.8, fillColor: couleurs[classeDe(s.puissance_max)],
    }).bindTooltip(`${s.points} point${s.points > 1 ? "s" : ""} · ${s.puissance_max == null ? "puissance inconnue" : fmt(s.puissance_max, 1) + " kW max"}<br>ouvert en ${s.ouverture}`));
    // Fin de frise = dernier mois de mise en service, pas dernière ouverture de site : un site existant gagne encore des points
    const [fa, fm] = P.bornes.cumul.at(-1).mois.split("-").map(Number);
    rangMax = 12 * (fa - 2010) + fm - 1;
    const ajuster = () => { const k = echelle(); marqueurs.forEach((m, i) => m.setRadius(rayon(sites[i].points) * k)); };
    carte.on("zoomend", ajuster);
    ajuster();
    const curseur = document.getElementById("mois");
    curseur.min = 48; curseur.max = rangMax;  // la frise commence en 2014 : avant, 36 points en tout
    curseur.oninput = () => afficher(Number(curseur.value));
    document.getElementById("lecture").onclick = lecture;
    document.getElementById("legende").innerHTML = CLASSES.map((c, i) => `<span><i style="background:${couleurs[i]}"></i>${c}</span>`).join("")
      + `<span class="muted">· rond plus gros = plus de points sur le site</span>`;
    document.querySelectorAll("#territoires .chip").forEach(chip => chip.onclick = () => {
      document.querySelectorAll("#territoires .chip").forEach(c => c.setAttribute("aria-pressed", c === chip));
      carte.fitBounds(VUES[chip.dataset.vue]);
    });
    afficher(rangMax);
  }

  /* ---------------- Trading ---------------- */
  let nuage = null, opt = 1;
  const VOLUMES = [["< 30 trades", t => t < 30], ["30-99 trades", t => t >= 30 && t < 100], ["≥ 100 trades", t => t >= 100]];
  const volCouleur = () => [css("--s2"), css("--s4"), css("--s1")];

  function dessinerNuage() {
    if (!nuage) return;
    const pts = nuage.filter(p => p.optimisation === opt);
    const r = P.trading.resume.find(x => x.id === opt);
    document.getElementById("nuage-sub").textContent =
      `${fmt(pts.length)} jeux de paramètres sur ${r.jours} jours · meilleure passe : ${fmt(r.profit_max)} € avec ${r.trades_meilleure} trades · couleur = nombre de trades`;
    const c = volCouleur();
    dessiner("nuage", {
      ...base(),
      grid: { ...base().grid, top: 52 },
      tooltip: { ...base().tooltip, formatter: p => `Passe ${p.data[3]}<br>Gain : <b>${fmt(p.data[1])} €</b><br>Drawdown : ${fmt(p.data[0], 1)} %<br>${p.data[2]} trades` },
      xAxis: axe({ type: "value", name: "Drawdown maximal (%)", nameLocation: "middle", nameGap: 26 }),
      yAxis: axe({ type: "value", name: "Gain (€)", axisLabel: { color: css("--muted"), fontSize: 11, formatter: v => fmt(v / 1000) + " k" } }),
      series: VOLUMES.map(([nom, f], i) => ({
        name: nom, type: "scatter", symbolSize: 4, progressive: 0, itemStyle: { color: c[i], opacity: 0.55 },
        data: pts.filter(p => f(p.trades)).map(p => [p.dd, p.profit, p.trades, p.passe]),
        markLine: i === 0 ? { silent: true, symbol: "none", lineStyle: { color: css("--axis"), type: "dashed" }, label: { show: false }, data: [{ yAxis: 0 }] } : undefined,
      })),
    });
  }

  function dessinerFiabilite() {
    const rows = P.trading.fiabilite.filter(r => r.optimisation === opt && r.passes >= 5);
    const c = volCouleur();
    const idx = (v) => VOLUMES.findIndex(x => x[0] === v);
    dessiner("fiabilite", {
      ...base(),
      grid: { ...base().grid, top: 16 },
      tooltip: { ...base().tooltip, trigger: "item",
                 formatter: p => { const r = rows[p.dataIndex]; return `${r.volume} · ${fmt(r.passes)} passes<br>Médiane : <b>${fmt(r.mediane)} €</b><br>P5 → P95 : ${fmt(r.p5)} → ${fmt(r.p95)} €<br>Meilleure : ${fmt(r.meilleur)} €`; } },
      xAxis: axe({ type: "category", data: rows.map(r => `${r.volume}\n${fmt(r.passes)} passes`) }),
      yAxis: axe({ type: "value", name: "Gain (€)", axisLabel: { color: css("--muted"), fontSize: 11, formatter: v => fmt(v / 1000) + " k" } }),
      series: [
        { type: "custom", silent: true, data: rows.map((r, i) => [i, r.p5, r.p95]),
          renderItem: (params, api) => {
            const x = api.coord([api.value(0), 0])[0], lo = api.coord([0, api.value(1)])[1], hi = api.coord([0, api.value(2)])[1];
            const col = c[idx(rows[params.dataIndex].volume)];
            return { type: "group", children: [
              { type: "line", shape: { x1: x, y1: lo, x2: x, y2: hi }, style: { stroke: col, lineWidth: 2 } },
              { type: "line", shape: { x1: x - 8, y1: lo, x2: x + 8, y2: lo }, style: { stroke: col, lineWidth: 2 } },
              { type: "line", shape: { x1: x - 8, y1: hi, x2: x + 8, y2: hi }, style: { stroke: col, lineWidth: 2 } }] };
          } },
        { type: "scatter", symbolSize: 13, data: rows.map((r, i) => ({ value: [i, r.mediane], itemStyle: { color: c[idx(r.volume)] } })),
          markLine: { silent: true, symbol: "none", lineStyle: { color: css("--axis"), type: "dashed" }, label: { show: false }, data: [{ yAxis: 0 }] } },
      ],
    });
  }

  async function initTrading() {
    if (!nuage) nuage = await (await fetch("/projets/donnees/trading_nuage.json")).json();
    dessinerNuage(); dessinerFiabilite();
  }
  document.querySelectorAll("#optis .chip").forEach(chip => chip.onclick = () => {
    document.querySelectorAll("#optis .chip").forEach(c => c.setAttribute("aria-pressed", c === chip));
    opt = Number(chip.dataset.opt);
    dessinerNuage(); dessinerFiabilite();
  });

  /* ---------------- Onglets ---------------- */
  const TABS = ["bornes", "trading", "code"];
  function montrer(nom, push = true) {
    if (!TABS.includes(nom)) nom = TABS[0];
    document.querySelectorAll('[role="tab"]').forEach(b => b.setAttribute("aria-selected", b.dataset.tab === nom));
    document.querySelectorAll('[role="tabpanel"]').forEach(p => (p.hidden = p.id !== `tab-${nom}`));
    if (push) history.replaceState(null, "", `#${nom}`);
    if (nom === "bornes") { annuel(); initCarte().then(() => { carte.invalidateSize(); if (!carte._cadree) { carte.fitBounds(VUES.metropole); carte._cadree = true; } }); }
    if (nom === "trading") initTrading();
    if (nom === "code") document.querySelectorAll("#tab-code pre code:not(.hljs)").forEach(c => {
      hljs.highlightElement(c);
      // Les identifiants sont déjà remplacés dans le fichier ; le flou dit seulement au lecteur qu'il y avait là un secret
      c.innerHTML = c.innerHTML.replace(/••••••••/g, '<span class="flou" title="Identifiant masqué">••••••••</span>');
    });
  }
  document.querySelectorAll('[role="tab"]').forEach(b => b.onclick = () => montrer(b.dataset.tab));
  addEventListener("resize", () => Object.values(charts).forEach(c => c.resize()));
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => montrer(location.hash.slice(1), false));
  montrer(location.hash.slice(1), false);
})();
