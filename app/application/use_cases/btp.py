"""Cas d'usage : la page BTP à La Réunion (aucun SQL ici, aucun HTML)."""
from app.domain.btp import FAMILLES, TRANCHES
from app.domain.ports import BtpRepository

_REQUETES = ["bt_par_an", "bt_familles", "bt_acheteurs_type", "bt_top_acheteurs", "bt_concurrence", "bt_procedures",
             "bt_top_titulaires", "bt_concentration", "bt_taille", "bt_logements_an", "bt_logements_region",
             "bt_top_communes", "bt_hors_norme_q", "bt_qualite"]


class BtpShowcase:
    def __init__(self, repo: BtpRepository):
        self.repo = repo

    def available(self) -> bool:
        return self.repo.available()

    def page(self) -> dict:
        data = {q: self.repo.query(q) for q in _REQUETES}
        # listes et non dicts : tojson trie les clés, et l'ordre des tranches compte
        return {"kpis": self.repo.query("bt_kpis")[0], **data,
                "tranches": [l for _, l in TRANCHES], "familles": [l for _, l, _ in FAMILLES],
                "sql": self.repo.sql(), "sources": self.repo.sources()}
