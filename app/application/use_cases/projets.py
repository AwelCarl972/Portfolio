"""Cas d'usage : la page Projets, qui reprend des travaux antérieurs au portfolio (aucun SQL ici, aucun HTML)."""
from app.domain.ports import ProjetsRepository

# Libellés lus dans les rapports MetaTrader 5 (en français, tels que le testeur les écrit)
_BACKTEST_CLES = ["Expert", "Symbole", "Période", "Dépôt initial", "Profit Total Net", "Facteur de profit",
                  "Nb trades", "Positions gagnantes (% du total)", "Plus large position gagnante",
                  "Fond Drawdown Relatif", "Ratio de Sharpe"]

# Requêtes servies en JSON à la demande (liste blanche : le nom vient de l'URL)
DONNEES = {"bornes_sites", "trading_nuage"}


class ProjetsShowcase:
    def __init__(self, repo: ProjetsRepository):
        self.repo = repo

    def available(self) -> bool:
        return self.repo.available()

    def page(self) -> dict:
        """Tout ce que la page affiche au chargement ; les deux gros jeux (carte, nuage) arrivent ensuite en JSON."""
        q = self.repo.query
        return {
            "bornes": {"kpis": q("bornes_kpis")[0], "annuel": q("bornes_annuel"), "cumul": q("bornes_cumul"),
                       "territoires": q("bornes_territoires"), "qualite": q("bornes_qualite")},
            "trading": {"resume": q("trading_resume"), "fiabilite": q("trading_fiabilite"),
                        "backtests": [{"fichier": b["fichier"],
                                       "resume": {k: b["resume"][k] for k in _BACKTEST_CLES if k in b["resume"]}}
                                      for b in self.repo.backtests()]},
            "sql": self.repo.sql(),
        }

    def donnees(self, name: str) -> list[dict]:
        if name not in DONNEES:
            raise ValueError("jeu de données inconnu")
        return self.repo.query(name)
