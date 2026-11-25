"""Cas d'usage : la page Électricité de La Réunion (aucun SQL ici, aucun HTML)."""
from app.domain.energie import FILIERES, FILIERES_HORAIRES
from app.domain.ports import EnergieRepository

_REQUETES = ["en_mix", "en_part_q", "en_co2_q", "en_journee", "en_saisons", "en_pointe", "en_communes",
             "en_secteurs", "en_qualite"]


class EnergieShowcase:
    def __init__(self, repo: EnergieRepository):
        self.repo = repo

    def available(self) -> bool:
        return self.repo.available()

    def page(self) -> dict:
        data = {q: self.repo.query(q) for q in _REQUETES}
        for r in data["en_pointe"]:  # une date n'est pas sérialisable en JSON : on la rend lisible ici
            r["heure_pointe"] = r["heure_pointe"].strftime("%d/%m à %H h")
        ecart = next(r["valeur"] for r in data["en_qualite"] if "bilan annuel" in r["etape"])
        # listes et non dicts : tojson trie les clés, et l'ordre d'empilement compte
        return {"kpis": self.repo.query("en_kpis")[0], **data, "ecart_horaire_pct": ecart,
                "filieres": [{"filiere": c, "libelle": l, "renouvelable": r} for c, l, r in FILIERES],
                "filieres_h": [l for _, l in FILIERES_HORAIRES],
                "sql": self.repo.sql(), "sources": self.repo.sources()}
