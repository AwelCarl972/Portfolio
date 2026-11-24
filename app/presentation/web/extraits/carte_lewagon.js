// Extrait simplifié du projet final Le Wagon (2025), fidèle à sa logique : chargement des données
// et rendu des points. Deux défauts, corrigés dans cette page (voir ci-dessous).
async loadData() {
    const fileName = this.state.isQuarterly
        ? 'bornes_recharge_trimestriel.json'   // clés « 2025-Q%q » : trimestre jamais calculé
        : 'bornes_recharge_mensuel.json';
    const response = await fetch(fileName);     // 20 Mo de JSON, un objet par point de charge
    this.state.currentData = await response.json();
    this.state.dates = Object.keys(this.state.currentData)
        .sort()
        .filter(date => date >= "2014-01");    // masque les dates de 1930… sans les compter
}

renderMarkers(currentDate) {
    // À chaque image de l'animation : tout est effacé puis redessiné depuis le début,
    // jusqu'à 126 790 marqueurs SVG. Le navigateur sature vers 2023.
    for (let i = 0; i <= this.state.currentDateIndex; i++) {
        this.state.currentData[this.state.dates[i]]?.forEach(p => this.createMarker(p));
    }
}
