// La même carte, refaite pour ce portfolio : 30 113 sites agrégés en SQL (pj_site)
// au lieu de 126 790 points, dessinés une seule fois sur un canvas, puis seulement
// montrés ou cachés quand la frise avance.
const renderer = L.canvas({ padding: 0.5 });
const markers = sites.map(s => L.circleMarker([s.lat, s.lon], {
    renderer, radius: rayon(s.points), fillColor: couleur(s.puissance_max), weight: 0, fillOpacity: 0.75,
}));

function afficherJusqua(rang) {          // rang = mois depuis janvier 2010
    markers.forEach((m, i) => {
        const visible = sites[i].rang <= rang;
        if (visible && !calque.hasLayer(m)) calque.addLayer(m);
        else if (!visible && calque.hasLayer(m)) calque.removeLayer(m);
    });
}
