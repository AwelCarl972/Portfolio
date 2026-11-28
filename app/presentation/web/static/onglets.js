/* Rend évident qu'une page a plusieurs parties : une phrase qui l'annonce, des onglets numérotés et, en bas de
   chaque partie, un bouton vers la suivante. Commun à toutes les pages à onglets ; le changement d'onglet reste
   géré par le script de chaque page (on ne fait que cliquer sur l'onglet voulu). */
(() => {
  const nav = document.querySelector(".tabs[role=tablist]");
  if (!nav) return;
  const onglets = [...nav.querySelectorAll("[role=tab]")];
  const noms = onglets.map(t => t.textContent.trim());

  const annonce = document.createElement("p");
  annonce.className = "tabs-annonce";
  annonce.innerHTML = `Cette page compte <b>${onglets.length} parties</b> : cliquez pour passer de l'une à l'autre.`;
  nav.before(annonce);

  const doux = !matchMedia("(prefers-reduced-motion: reduce)").matches;
  onglets.forEach((t, i) => {
    t.insertAdjacentHTML("afterbegin", `<span class="tab-num" aria-hidden="true">${i + 1}</span>`);
    const partie = document.getElementById("tab-" + t.dataset.tab), suivant = onglets[i + 1];
    if (!partie || !suivant) return;
    const b = document.createElement("button");
    b.type = "button";
    b.className = "tab-suivant";
    b.innerHTML = `<span>Partie suivante</span><b>${i + 2}. ${noms[i + 1]}</b><span aria-hidden="true">→</span>`;
    b.onclick = () => { suivant.click(); annonce.scrollIntoView({ behavior: doux ? "smooth" : "auto", block: "start" }); };
    partie.append(b);
  });
})();
