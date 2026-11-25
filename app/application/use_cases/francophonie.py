"""Cas d'usage : la page Francophonie canadienne (aucun SQL ici, aucun HTML)."""
from app.domain.francophonie import CIBLES_IRCC, PILIERS, PROVINCES_HQ, continuity_label
from app.domain.ports import FrancophonieRepository

_REQUETES = ["fr_paradoxe", "fr_haltere", "fr_series", "fr_continuite", "fr_ou", "fr_variations",
             "fr_bilinguisme", "fr_qualite", "fr_immig_annuel", "fr_immig_prov", "fr_immig_villes",
             "fr_villes_tableau", "fr_villes_notes_q", "fr_villes_classement"]


class FrancophonieShowcase:
    def __init__(self, repo: FrancophonieRepository):
        self.repo = repo

    def available(self) -> bool:
        return self.repo.available()

    def page(self) -> dict:
        data = {q: self.repo.query(q) for q in _REQUETES}
        for r in data["fr_continuite"]:
            r["lecture"] = continuity_label(r["c_2021"])
        # liste et non dict : tojson trie les clés, et l'ordre des piliers compte à l'affichage
        piliers = [{"pilier": p, "indicateurs": [{"indicateur": c, "libelle": l, "sens": s} for c, l, s in inds]}
                   for p, inds in PILIERS.items()]
        return {"kpis": self.repo.query("fr_kpis")[0], **data, "provinces": PROVINCES_HQ, "piliers": piliers,
                "cibles": [{"annee": a, "cible_pct": c} for a, c in CIBLES_IRCC.items()],
                "sql": self.repo.sql(), "sources": self.repo.sources()}
