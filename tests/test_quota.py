"""Quota de la démo IA : c'est la clé Anthropic du propriétaire qui paie chaque analyse."""
from app.presentation.web.quota import Quota


def test_plafond_par_visiteur_puis_reouverture_apres_la_fenetre():
    q = Quota(par_visiteur=2, fenetre_s=3600, par_jour=100)
    assert q.refus("a", now=0) is None and q.refus("a", now=10) is None
    assert "réessayez" in q.refus("a", now=20)
    assert q.refus("b", now=20) is None          # un autre visiteur n'est pas puni pour le premier
    assert q.refus("a", now=3601) is None        # la première analyse est sortie de la fenêtre


def test_plafond_du_jour_commun_a_tous():
    q = Quota(par_visiteur=10, fenetre_s=3600, par_jour=3)
    for i, v in enumerate("abc"):
        assert q.refus(v, now=i) is None
    assert "aujourd'hui" in q.refus("d", now=5)
    assert q.refus("d", now=86401) is None       # le lendemain, la première analyse est sortie


def test_un_refus_ne_consomme_rien():
    q = Quota(par_visiteur=1, fenetre_s=3600, par_jour=100)
    q.refus("a", now=0)
    for t in range(1, 50):
        q.refus("a", now=t)
    assert q.refus("b", now=60) is None and len(q._jour) == 2
