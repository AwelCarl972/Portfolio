"""Cas d'usage : assembler le tableau de bord territorial (aucun SQL ici, aucun HTML)."""
from app.domain.ports import TerritoryRepository
from app.domain.territory import INDICATORS, REGIONS, correlation_strength, normalize_region

_FILTERED = ["prix_trend", "prix_box", "prix_evol", "acc_heatmap", "acc_gravite", "permis_trend"]
_GLOBAL = ["corr_matrix", "features", "pluie_accidents", "chomage_index",
           "climat_kpis", "stations", "rechauffement", "pluie_annuelle", "regimes", "records_pluie"]


class TerritoryDashboard:
    def __init__(self, repo: TerritoryRepository):
        self.repo = repo

    def available(self) -> bool:
        return self.repo.available()

    def panel(self, region: str | None) -> dict:
        """Indicateurs et séries qui suivent le filtre de micro-région."""
        region = normalize_region(region)
        data = {n: self.repo.query(n, region) for n in _FILTERED}
        return {"region": region, "kpis": self.repo.query("kpis", region)[0], **data}

    def cross(self) -> dict:
        """Analyses croisées sur les 24 communes (non filtrées : un filtre réduirait trop l'échantillon)."""
        return {n: self.repo.query(n) for n in _GLOBAL} | {
            "indicators": {k: {"short": v[0], "label": v[1], "unit": v[2]} for k, v in INDICATORS.items()},
            "order": list(INDICATORS),  # tojson trie les clés : l'ordre d'affichage est explicite
            "regions": REGIONS}

    def lineage(self) -> dict:
        """Sources, étapes de chargement/nettoyage, requêtes et tables : la traçabilité complète."""
        return self.repo.lineage()

    def pair(self, x: str, y: str) -> dict:
        rows = self.repo.pair(x, y)
        r = rows[0]["r"] if rows else None
        return {"x": x, "y": y, "points": rows, "r": r, "strength": correlation_strength(r),
                "r2": rows[0]["r2"] if rows else None, "n": len(rows),
                "slope": rows[0]["slope"] if rows else None, "intercept": rows[0]["intercept"] if rows else None}
