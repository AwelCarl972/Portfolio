"""Quota de la démo IA en ligne : c'est la clé Anthropic du propriétaire qui paie chaque analyse.

Deux plafonds, parce qu'ils ne protègent pas de la même chose : par visiteur (une personne qui
clique en boucle) et par jour (beaucoup de visiteurs, ou un script qui change d'adresse).
En mémoire et non en base : un redémarrage remet les compteurs à zéro, ce qui coûte au pire un
quota de plus — un prix acceptable pour ne rien stocker des adresses des visiteurs.
"""
import os
import threading
import time
from collections import defaultdict, deque


class Quota:
    def __init__(self, par_visiteur: int, fenetre_s: int, par_jour: int):
        self.par_visiteur, self.fenetre_s, self.par_jour = par_visiteur, fenetre_s, par_jour
        self._visiteurs: dict[str, deque] = defaultdict(deque)
        self._jour: deque = deque()
        self._lock = threading.Lock()

    def refus(self, visiteur: str, now: float | None = None) -> str | None:
        """None si l'analyse est permise (et la compte), sinon la raison à afficher."""
        now = time.time() if now is None else now
        with self._lock:
            mes = self._visiteurs[visiteur]
            while mes and mes[0] <= now - self.fenetre_s:
                mes.popleft()
            while self._jour and self._jour[0] <= now - 86400:
                self._jour.popleft()
            if len(self._jour) >= self.par_jour:
                return "La démo a atteint son plafond d'analyses pour aujourd'hui. Revenez demain."
            if len(mes) >= self.par_visiteur:
                attente = int(self.fenetre_s - (now - mes[0])) // 60 + 1
                return f"Vous avez fait {self.par_visiteur} analyses : réessayez dans {attente} min."
            mes.append(now)
            self._jour.append(now)
            if len(self._visiteurs) > 10_000:  # borne la mémoire : on oublie les visiteurs sans analyse récente
                for k in [k for k, v in self._visiteurs.items() if not v]:
                    del self._visiteurs[k]
            return None


def depuis_env() -> Quota:
    return Quota(par_visiteur=int(os.getenv("LLM_QUOTA_VISITEUR", "5")), fenetre_s=3600,
                 par_jour=int(os.getenv("LLM_QUOTA_JOUR", "100")))
