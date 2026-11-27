/* Carte des prix au m² (Observatoire > Immobilier) : filtres, médianes calculées dans le navigateur, carte SVG.
   Données : static/immo/ventes.json, produit par app/infrastructure/opendata/dvf_carte.py (DVF géolocalisée). */
(function () {
  const racine = document.getElementById("immo");
  if (!racine) return;
  const svg = racine.querySelector("#immo-svg");
  const NS = "http://www.w3.org/2000/svg";
  const SEUIL = { commune: 10, hex: 5 };          // ventes minimum pour afficher une médiane
  const etat = { bien: "tous", pieces: new Set(), dep: "tous", terrain: "tous", neuf: "tous", periode: "tout", echelle: "commune", zone: null };
  let D = null;

  const css = v => getComputedStyle(document.body).getPropertyValue(v).trim();
  const euros = v => Math.round(v).toLocaleString("fr-FR");
  const mediane = t => { const s = Float64Array.from(t).sort(), n = s.length; return n ? (n % 2 ? s[(n - 1) / 2] : (s[n / 2 - 1] + s[n / 2]) / 2) : NaN; };
  const quantile = (s, q) => s[Math.min(s.length - 1, Math.max(0, Math.round(q * (s.length - 1))))];
  const el = (nom, attrs = {}) => { const e = document.createElementNS(NS, nom); for (const k in attrs) e.setAttribute(k, attrs[k]); return e; };

  /* ---------- Filtres : groupes de puces ---------- */
  racine.querySelectorAll("[data-filtre]").forEach(groupe => {
    const cle = groupe.dataset.filtre;
    groupe.addEventListener("click", e => {
      const b = e.target.closest("button");
      if (!b || b.disabled) return;
      if (cle === "pieces") {
        const p = +b.dataset.v;
        etat.pieces.has(p) ? etat.pieces.delete(p) : etat.pieces.add(p);
        b.setAttribute("aria-pressed", etat.pieces.has(p));
      } else {
        etat[cle] = b.dataset.v;
        groupe.querySelectorAll("button").forEach(x => x.setAttribute("aria-pressed", x === b));
      }
      if (cle === "echelle") etat.zone = null;
      // Le terrain ne concerne que les maisons ; choisir un terrain revient à chercher une maison
      const terrain = racine.querySelector('[data-filtre="terrain"]');
      terrain.querySelectorAll("button").forEach(x => x.disabled = etat.bien === "appartement" && x.dataset.v !== "tous");
      if (etat.bien === "appartement" && etat.terrain !== "tous") {
        etat.terrain = "tous";
        terrain.querySelectorAll("button").forEach(x => x.setAttribute("aria-pressed", x.dataset.v === "tous"));
      }
      dessiner();
    });
  });

  /* ---------- Sélection des ventes ---------- */
  function ventes() {
    const v = D.ventes, n = v.m.length, ok = [];
    const anMin = etat.periode === "recent" ? 2024 : 0;
    for (let i = 0; i < n; i++) {
      if (etat.bien === "maison" && v.t[i] !== 0) continue;
      if (etat.bien === "appartement" && v.t[i] !== 1) continue;
      if (etat.pieces.size && !etat.pieces.has(v.p[i])) continue;
      if (etat.dep !== "tous" && v.d[i] !== (etat.dep === "avec" ? 1 : 0)) continue;
      if (etat.terrain !== "tous" && v.j[i] !== +etat.terrain) continue;
      if (etat.neuf !== "tous" && v.n[i] !== (etat.neuf === "neuf" ? 1 : 0)) continue;
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

  /* ---------- Couleurs : 6 classes par quantiles des zones affichées ---------- */
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

  /* ---------- Rendu ---------- */
  function dessiner() {
    const idx = ventes(), v = D.ventes, parCommune = etat.echelle === "commune";
    const groupes = new Map();
    for (const i of idx) {
      const z = parCommune ? v.c[i] : v.h[i];
      if (z < 0) continue;
      (groupes.get(z) || groupes.set(z, []).get(z)).push(i);
    }
    const zones = new Map();
    groupes.forEach((g, z) => zones.set(z, g.length >= SEUIL[parCommune ? "commune" : "hex"] ? stats(g) : { n: g.length }));
    // Nom d'un hexagone : la commune où ont eu lieu la plupart de ses ventes (toutes ventes confondues)
    const nomZone = z => parCommune ? D.communes[z].nom : "Secteur de " + D.communes[D.communeHex[z]].nom;

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
      t.textContent = s.med ? `${nomZone(z)} · ${euros(s.med)} €/m² (${s.n} ventes)` : `${nomZone(z)} · trop peu de ventes (${s.n})`;
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
      const lim = [meds[0], ...bornes, meds[meds.length - 1]];
      cols.forEach((c, k) => {
        const s = document.createElement("span");
        s.innerHTML = `<i style="background:${c}"></i>` + (lim[k] === lim[k + 1] ? `${euros(lim[k])} €/m²` : `${euros(lim[k])} – ${euros(lim[k + 1])}`);
        leg.append(s);
      });
      const p = document.createElement("span");
      p.innerHTML = `<i class="immo-i-peu"></i>moins de ${SEUIL[parCommune ? "commune" : "hex"]} ventes`;
      leg.append(p);
    }

    // Résumé de la recherche, zone sélectionnée, classement
    const ile = stats(idx);
    const res = racine.querySelector("#immo-resume");
    res.innerHTML = ile.n
      ? `<div class="immo-chiffre">${euros(ile.med)} €/m²</div>
         <p>Prix médian au m² pour <b>${ile.n.toLocaleString("fr-FR")} ventes</b> sur toute l'île. La moitié des ventes se situe entre
         ${euros(ile.q1)} et ${euros(ile.q3)} €/m². Surface médiane ${euros(ile.surf)} m², prix médian ${euros(ile.prix)} €.</p>`
      : `<p>Aucune vente ne correspond à ces critères. Retirez un filtre.</p>`;

    const det = racine.querySelector("#immo-zone");
    const s = etat.zone !== null ? zones.get(etat.zone) : null;
    det.innerHTML = s && s.med
      ? `<h4>${nomZone(etat.zone)}</h4><div class="immo-chiffre">${euros(s.med)} €/m²</div>
         <p>${s.n} ventes · la moitié entre ${euros(s.q1)} et ${euros(s.q3)} €/m² · surface médiane ${euros(s.surf)} m² ·
         prix médian ${euros(s.prix)} € · ${s.med >= ile.med ? "+" : ""}${Math.round(100 * (s.med / ile.med - 1))} % par rapport à l'île.</p>`
      : s ? `<h4>${nomZone(etat.zone)}</h4><p>Seulement ${s.n} vente${s.n > 1 ? "s" : ""} avec ces critères : pas assez pour une médiane fiable.</p>`
      : `<p class="muted">Cliquez sur une ${parCommune ? "commune" : "zone"} de la carte pour voir son détail.</p>`;

    const tab = racine.querySelector("#immo-classement tbody");
    const lignes = [...groupes].map(([z, g]) => ({ z, s: zones.get(z) })).filter(o => o.s.med && parCommune)
      .sort((a, b) => b.s.med - a.s.med);
    racine.querySelector("#immo-classement").hidden = !parCommune;
    tab.innerHTML = lignes.map(({ z, s }) => `<tr data-z="${z}"${etat.zone === z ? ' class="immo-sel"' : ""}><td>${D.communes[z].nom}</td>
      <td class="n">${euros(s.med)}</td><td class="n">${s.n}</td></tr>`).join("");
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
    dessiner();
    matchMedia("(prefers-color-scheme: dark)").addEventListener("change", dessiner);
  }).catch(() => { racine.querySelector("#immo-resume").textContent = "Les ventes n'ont pas pu être chargées. Rechargez la page."; });
})();
