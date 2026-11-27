/* Carte des prix au m² (Observatoire > Immobilier), à l'achat et à la location.
   Achat : médianes calculées dans le navigateur sur les ventes DVF filtrées.
   Location : loyer d'annonce par commune de la carte des loyers (ANIL), pour un bien de référence.
   Données : static/immo/ventes.json, produit par app/infrastructure/opendata/dvf_carte.py. */
(function () {
  const racine = document.getElementById("immo");
  if (!racine) return;
  const svg = racine.querySelector("#immo-svg");
  const NS = "http://www.w3.org/2000/svg";
  const SEUIL = { commune: 10, hex: 5 };          // ventes minimum pour afficher une médiane
  const etat = { mode: "achat", bien: "tous", pieces: new Set(), dep: "tous", terrain: "tous", neuf: "tous",
                 periode: "tout", echelle: "commune", zone: null };
  const SANS_LOCATION = ["dep", "terrain", "neuf", "periode", "echelle"];   // critères absents de la carte des loyers
  const SEGMENTS = { app: "un appartement", app12: "un appartement T1-T2", app3: "un appartement T3 et plus", mai: "une maison" };
  let D = null;

  const css = v => getComputedStyle(document.body).getPropertyValue(v).trim();
  const euros = v => Math.round(v).toLocaleString("fr-FR");
  const eurosM2 = v => v.toLocaleString("fr-FR", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
  const mediane = t => { const s = Float64Array.from(t).sort(), n = s.length; return n ? (n % 2 ? s[(n - 1) / 2] : (s[n / 2 - 1] + s[n / 2]) / 2) : NaN; };
  const quantile = (s, q) => s[Math.min(s.length - 1, Math.max(0, Math.round(q * (s.length - 1))))];
  const el = (nom, attrs = {}) => { const e = document.createElementNS(NS, nom); for (const k in attrs) e.setAttribute(k, attrs[k]); return e; };
  const groupe = cle => racine.querySelector(`[data-filtre="${cle}"]`);
  const presser = (cle, v) => groupe(cle).querySelectorAll("button").forEach(x => x.setAttribute("aria-pressed", x.dataset.v === v));

  /* ---------- Filtres : groupes de puces ---------- */
  racine.querySelectorAll("[data-filtre]").forEach(g => {
    const cle = g.dataset.filtre;
    g.addEventListener("click", e => {
      const b = e.target.closest("button");
      if (!b || b.disabled) return;
      if (cle === "pieces") {
        const p = +b.dataset.v;
        etat.pieces.has(p) ? etat.pieces.delete(p) : etat.pieces.add(p);
        b.setAttribute("aria-pressed", etat.pieces.has(p));
      } else {
        etat[cle] = b.dataset.v;
        presser(cle, b.dataset.v);
      }
      if (cle === "echelle" || cle === "mode") etat.zone = null;
      if (etat.mode === "location" && etat.echelle !== "commune") { etat.echelle = "commune"; presser("echelle", "commune"); }
      if (etat.bien === "appartement" && etat.terrain !== "tous") { etat.terrain = "tous"; presser("terrain", "tous"); }
      activer();
      dessiner();
    });
  });

  // Grise les critères qui ne s'appliquent pas : terrain pour un appartement, la plupart des critères en location
  function activer() {
    const loc = etat.mode === "location";
    SANS_LOCATION.forEach(cle => groupe(cle).querySelectorAll("button").forEach(x => {
      x.disabled = loc || (cle === "terrain" && etat.bien === "appartement" && x.dataset.v !== "tous");
    }));
    groupe("pieces").querySelectorAll("button").forEach(x => x.disabled = loc && etat.bien === "maison");
    racine.querySelector("#immo-note-location").hidden = !loc;
  }

  /* ---------- Achat : sélection des ventes ---------- */
  function ventes(f = etat) {
    const v = D.ventes, n = v.m.length, ok = [];
    const anMin = f.periode === "recent" ? 2024 : 0;
    for (let i = 0; i < n; i++) {
      if (f.bien === "maison" && v.t[i] !== 0) continue;
      if (f.bien === "appartement" && v.t[i] !== 1) continue;
      if (f.pieces.size && !f.pieces.has(v.p[i])) continue;
      if (f.dep !== "tous" && v.d[i] !== (f.dep === "avec" ? 1 : 0)) continue;
      if (f.terrain !== "tous" && v.j[i] !== +f.terrain) continue;
      if (f.neuf !== "tous" && v.n[i] !== (f.neuf === "neuf" ? 1 : 0)) continue;
      if (v.a[i] < anMin) continue;
      ok.push(i);
    }
    return ok;
  }

  function stats(idx) {
    const v = D.ventes;
    const m = Float64Array.from(idx, i => v.m[i]).sort();
    return {
      n: idx.length, med: mediane(m), q1: quantile(m, .25), q3: quantile(m, .75),
      surf: mediane(idx.map(i => v.s[i])), prix: mediane(idx.map(i => v.m[i] * v.s[i])),
    };
  }

  /* ---------- Location : segment de la carte des loyers qui correspond aux critères ---------- */
  function segment() {
    if (etat.bien === "maison") return "mai";
    const p = [...etat.pieces];
    if (p.length && p.every(x => x <= 2)) return "app12";
    if (p.length && p.every(x => x >= 3)) return "app3";
    return "app";
  }

  // Prix d'achat médian au m² du même type de bien dans une commune, pour comparer au loyer
  function achatComparable(seg, z) {
    const v = D.ventes, appart = seg !== "mai";
    const garder = i => v.c[i] === z && v.t[i] === (appart ? 1 : 0)
      && (seg === "app12" ? v.p[i] <= 2 : seg === "app3" ? v.p[i] >= 3 : true);
    const recentes = [], toutes = [];
    for (let i = 0; i < v.m.length; i++) if (garder(i)) { toutes.push(v.m[i]); if (v.a[i] >= 2024) recentes.push(v.m[i]); }
    if (recentes.length >= SEUIL.commune) return { med: mediane(recentes), n: recentes.length, periode: "2024-2025" };
    if (toutes.length >= SEUIL.commune) return { med: mediane(toutes), n: toutes.length, periode: "2021-2025" };
    return null;
  }

  /* ---------- Couleurs : jusqu'à 6 classes par quantiles des zones affichées ---------- */
  function hex2rgb(h) { h = h.replace("#", ""); return [0, 2, 4].map(k => parseInt(h.slice(k, k + 2), 16)); }
  function palette(n) {
    const a = hex2rgb(css("--seq-lo")), b = hex2rgb(css("--seq-hi"));
    return Array.from({ length: n }, (_, k) => `rgb(${a.map((x, j) => Math.round(x + (b[j] - x) * k / (n - 1))).join(",")})`);
  }

  function hexagone(cx, cy, r) {
    return Array.from({ length: 6 }, (_, k) => {
      const a = Math.PI / 180 * (60 * k - 30);
      return `${(cx + r * Math.cos(a)).toFixed(1)},${(cy + r * Math.sin(a)).toFixed(1)}`;
    }).join(" ");
  }

  /* ---------- Zones à colorier, selon le mode ---------- */
  function zonesAchat() {
    const idx = ventes(), v = D.ventes, parCommune = etat.echelle === "commune";
    const groupes = new Map();
    for (const i of idx) {
      const z = parCommune ? v.c[i] : v.h[i];
      if (z < 0) continue;
      (groupes.get(z) || groupes.set(z, []).get(z)).push(i);
    }
    const zones = new Map();
    groupes.forEach((g, z) => zones.set(z, g.length >= SEUIL[parCommune ? "commune" : "hex"] ? stats(g) : { n: g.length }));
    return { zones, ile: stats(idx) };
  }

  function zonesLocation() {
    const seg = segment(), zones = new Map();
    D.loyers[seg].communes.forEach((r, z) => { if (r) zones.set(z, { med: r[0], lo: r[1], hi: r[2], nobs: r[3], maille: r[4] }); });
    return { zones, seg };
  }

  /* ---------- Rendu ---------- */
  function dessiner() {
    const loc = etat.mode === "location", parCommune = etat.echelle === "commune";
    const { zones, ile, seg } = loc ? zonesLocation() : zonesAchat();
    const nomZone = z => parCommune ? D.communes[z].nom : "Secteur de " + D.communes[D.communeHex[z]].nom;
    const unite = val => loc ? `${eurosM2(val)} €/m²` : `${euros(val)} €/m²`;

    const meds = [...zones.values()].filter(s => s.med).map(s => s.med).sort((a, b) => a - b);
    const nc = Math.min(6, new Set(meds).size);                 // moins de classes quand il y a peu de zones
    const cols = nc > 1 ? palette(nc) : [css("--seq-hi")];
    const bornes = Array.from({ length: Math.max(0, nc - 1) }, (_, k) => quantile(meds, (k + 1) / nc));
    const couleur = m => cols[bornes.filter(b => m > b).length];

    svg.replaceChildren();
    svg.setAttribute("viewBox", `0 0 ${D.vue[0]} ${D.vue[1]}`);
    const fond = el("g", { class: "immo-fond" });
    D.communes.forEach(c => fond.append(el("path", { d: c.d })));
    svg.append(fond);

    const couche = el("g", { class: "immo-zones" });
    const ajouter = (forme, z) => {
      const s = zones.get(z);
      if (!s) { if (parCommune) { forme.setAttribute("class", "immo-vide"); couche.append(forme); } return; }
      forme.setAttribute("class", s.med ? "immo-zone" : "immo-peu");
      if (s.med) forme.style.fill = couleur(s.med);
      if (etat.zone === z) forme.classList.add("immo-sel");
      const t = el("title");
      t.textContent = !s.med ? `${nomZone(z)} · trop peu de ventes (${s.n})`
        : loc ? `${nomZone(z)} · ${unite(s.med)} charges comprises${s.nobs < 30 ? " (peu d'annonces)" : ""}`
        : `${nomZone(z)} · ${unite(s.med)} (${s.n} ventes)`;
      forme.append(t);
      forme.dataset.z = z;
      couche.append(forme);
    };
    if (parCommune) D.communes.forEach((c, z) => ajouter(el("path", { d: c.d }), z));
    else D.hex.forEach(([cx, cy], z) => ajouter(el("polygon", { points: hexagone(cx, cy, D.rayon_hex * 0.97) }), z));
    svg.append(couche);
    if (!parCommune) {                    // contours des communes par-dessus les hexagones
      const traits = el("g", { class: "immo-traits" });
      D.communes.forEach(c => traits.append(el("path", { d: c.d })));
      svg.append(traits);
    }

    // Légende
    const leg = racine.querySelector("#immo-legende");
    leg.replaceChildren();
    if (meds.length) {
      const f = loc ? eurosM2 : euros;
      const lim = [meds[0], ...bornes, meds[meds.length - 1]];
      cols.forEach((c, k) => {
        const s = document.createElement("span");
        s.innerHTML = `<i style="background:${c}"></i>` + (lim[k] === lim[k + 1] ? `${f(lim[k])} €/m²` : `${f(lim[k])} – ${f(lim[k + 1])}`);
        leg.append(s);
      });
      if (!loc) {
        const p = document.createElement("span");
        p.innerHTML = `<i class="immo-i-peu"></i>moins de ${SEUIL[parCommune ? "commune" : "hex"]} ventes`;
        leg.append(p);
      }
    }

    // Résumé de la recherche
    const res = racine.querySelector("#immo-resume");
    if (loc) {
      const surf = D.loyers[seg].surface;
      const lignes = [...zones].sort((a, b) => a[1].med - b[1].med);
      const [zmin, smin] = lignes[0], [zmax, smax] = lignes[lignes.length - 1];
      res.innerHTML = `<div class="immo-chiffre">${eurosM2(smin.med)} à ${eurosM2(smax.med)} €/m²</div>
        <p>Loyer d'annonce pour <b>${SEGMENTS[seg]}</b> de ${surf} m² en location vide, charges comprises : de
        ${D.communes[zmin].nom} à ${D.communes[zmax].nom}, soit environ <b>${euros(smin.med * surf)} à ${euros(smax.med * surf)} € par mois</b>.</p>`;
    } else {
      res.innerHTML = ile.n
        ? `<div class="immo-chiffre">${euros(ile.med)} €/m²</div>
           <p>Prix médian au m² pour <b>${ile.n.toLocaleString("fr-FR")} ventes</b> sur toute l'île. La moitié des ventes se situe entre
           ${euros(ile.q1)} et ${euros(ile.q3)} €/m². Surface médiane ${euros(ile.surf)} m², prix médian ${euros(ile.prix)} €.</p>`
        : `<p>Aucune vente ne correspond à ces critères. Retirez un filtre.</p>`;
    }

    // Zone sélectionnée
    const det = racine.querySelector("#immo-zone");
    const s = etat.zone !== null ? zones.get(etat.zone) : null;
    if (!s) {
      det.innerHTML = `<p class="muted">Cliquez sur une ${parCommune ? "commune" : "zone"} de la carte pour voir son détail.</p>`;
    } else if (loc) {
      const surf = D.loyers[seg].surface, achat = achatComparable(seg, etat.zone);
      const fiab = s.maille
        ? `Estimé sur un groupe de communes voisines : seulement ${s.nobs} annonce${s.nobs > 1 ? "s" : ""} dans la commune.`
        : `Estimé sur ${s.nobs.toLocaleString("fr-FR")} annonces de la commune${s.nobs < 30 ? " : fiabilité faible" : ""}.`;
      det.innerHTML = `<h4>${nomZone(etat.zone)}</h4><div class="immo-chiffre">${eurosM2(s.med)} €/m²</div>
        <p>Soit environ <b>${euros(s.med * surf)} € par mois</b> pour ${SEGMENTS[seg]} de ${surf} m², charges comprises.
        Fourchette probable : ${eurosM2(s.lo)} à ${eurosM2(s.hi)} €/m². ${fiab}</p>`
        + (achat ? `<p>À l'achat, le même type de bien s'y vend ${euros(achat.med)} €/m² (médiane de ${achat.n} ventes ${achat.periode}),
            soit <b>${(achat.med / (12 * s.med)).toLocaleString("fr-FR", { maximumFractionDigits: 0 })} années de loyer</b>.</p>` : "");
    } else if (s.med) {
      det.innerHTML = `<h4>${nomZone(etat.zone)}</h4><div class="immo-chiffre">${euros(s.med)} €/m²</div>
        <p>${s.n} ventes · la moitié entre ${euros(s.q1)} et ${euros(s.q3)} €/m² · surface médiane ${euros(s.surf)} m² ·
        prix médian ${euros(s.prix)} € · ${s.med >= ile.med ? "+" : ""}${Math.round(100 * (s.med / ile.med - 1))} % par rapport à l'île.</p>`;
    } else {
      det.innerHTML = `<h4>${nomZone(etat.zone)}</h4><p>Seulement ${s.n} vente${s.n > 1 ? "s" : ""} avec ces critères : pas assez pour une médiane fiable.</p>`;
    }

    // Classement des communes
    const tableau = racine.querySelector("#immo-classement");
    tableau.hidden = !parCommune;
    tableau.querySelector("thead").innerHTML = `<tr><th>Commune</th><th class="n">€/m²</th><th class="n">${loc ? "Annonces" : "Ventes"}</th></tr>`;
    const lignes = !parCommune ? [] : [...zones].filter(([, s]) => s.med).sort((a, b) => b[1].med - a[1].med);
    tableau.querySelector("tbody").innerHTML = lignes.map(([z, s]) => `<tr data-z="${z}"${etat.zone === z ? ' class="immo-sel"' : ""}>
      <td>${D.communes[z].nom}</td><td class="n">${loc ? eurosM2(s.med) : euros(s.med)}</td>
      <td class="n">${loc ? s.nobs.toLocaleString("fr-FR") : s.n}</td></tr>`).join("");
  }

  const choisir = z => { etat.zone = etat.zone === z ? null : z; dessiner(); };
  svg.addEventListener("click", e => { const f = e.target.closest("[data-z]"); if (f) choisir(+f.dataset.z); });
  racine.querySelector("#immo-classement").addEventListener("click", e => { const r = e.target.closest("tr[data-z]"); if (r) choisir(+r.dataset.z); });

  fetch(racine.dataset.src).then(r => r.json()).then(d => {
    D = d;
    // Commune majoritaire de chaque hexagone
    const compte = d.hex.map(() => new Map());
    d.ventes.h.forEach((h, i) => { if (h >= 0) compte[h].set(d.ventes.c[i], (compte[h].get(d.ventes.c[i]) || 0) + 1); });
    D.communeHex = compte.map(m => [...m].sort((a, b) => b[1] - a[1])[0][0]);
    racine.querySelector("#immo-maj").textContent = d.maj;
    activer();
    dessiner();
    matchMedia("(prefers-color-scheme: dark)").addEventListener("change", dessiner);
  }).catch(() => { racine.querySelector("#immo-resume").textContent = "Les données n'ont pas pu être chargées. Rechargez la page."; });
})();
