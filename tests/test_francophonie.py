from pathlib import Path

import pytest

from app.application.use_cases.francophonie import FrancophonieShowcase
from app.domain.francophonie import GEOS, PROVINCES_HQ, continuity_label
from app.infrastructure.sql.francophonie_repository import FICHIERS, DuckFrancophonieRepository
from app.infrastructure.sql.repository import Database

RAW = Path(__file__).resolve().parents[1] / "data" / "raw"


def test_domain():
    assert continuity_label(0.9) == "le français se transmet"
    assert continuity_label(0.4) == "l'anglais l'emporte à la maison"
    assert continuity_label(None) == "inconnu"
    codes = {c for c, _, _ in GEOS.values()}
    assert set(PROVINCES_HQ) <= codes and "QC" not in PROVINCES_HQ


@pytest.fixture(scope="module")
def page():
    if not all((RAW / f"{f}.csv").exists() for f in FICHIERS):
        pytest.skip("données Statistique Canada absentes : python -m app.infrastructure.opendata.fetch statcan_...")
    repo = DuckFrancophonieRepository(Database(":memory:"), RAW)
    assert repo.load()
    return FrancophonieShowcase(repo).page()


def test_every_province_survives_the_join(page):
    # « Saskatchewan » suivi d'une espace dans un tableau : sans trim, la province disparaît du bilinguisme
    sk = [r for r in page["fr_series"] if r["code"] == "SK"]
    assert len(sk) == 11 and all(r["bilingues_pct"] is not None for r in sk)


def test_recomputed_shares_match_published(page):
    ecarts = [r["valeur"] for r in page["fr_qualite"] if r["etape"].startswith("Écart max.")]
    assert len(ecarts) == 2 and all(0 <= e < 0.1 for e in ecarts)  # arrondis à une décimale, pas plus


def test_paradox_more_francophones_smaller_share(page):
    k = page["kpis"]
    assert k["hq_mat_fr_2021"] > k["hq_mat_fr_1951"] and k["hq_pct_2021"] < k["hq_pct_1951"] / 2
    first = page["fr_paradoxe"][0]
    assert first["an"] == 1951 and first["indice_fr"] == first["indice_pop"] == 100


def test_where_to_live(page):
    ou = page["fr_ou"]
    assert [r["code"] for r in ou[:2]] == ["ON", "NB"]
    assert abs(sum(r["part_hq"] for r in ou) - 100) < 0.5
    cont = {r["code"]: r for r in page["fr_continuite"]}
    assert cont["NB"]["c_2021"] == max(r["c_2021"] for r in page["fr_continuite"])
    assert cont["NB"]["lecture"] == "le français se transmet"


def test_ircc_masked_cells_stay_null(page):
    annees = {r["annee"]: r for r in page["fr_immig_annuel"]}
    # somme des cellules arrondies : proche du bilan officiel 2024 (30 550), jamais au-dessus
    assert 29_000 < annees[2024]["francophones"] <= 30_550
    assert annees[max(annees)]["mois"] <= 12
    masques = [r for r in page["fr_qualite"] if r["etape"].startswith("IRCC : cellules masquées")]
    assert masques and masques[0]["valeur"] > 0


def test_small_bases_get_no_ratio(page):
    for v in page["fr_immig_villes"]:
        if v["n_2019"] is None or v["n_2019"] < 50:
            assert v["multiplie_par"] is None


def test_every_city_has_every_indicator(page):
    from app.domain.francophonie import PILIERS, VILLES
    assert len(page["fr_villes_tableau"]) == len(VILLES)
    for r in page["fr_villes_tableau"]:
        for inds in PILIERS.values():
            assert all(r[col] is not None for col, _, _ in inds), r["nom"]


def test_scores_are_oriented(page):
    notes = page["fr_villes_notes_q"]
    for ind in {n["indicateur"] for n in notes}:
        rows = [n for n in notes if n["indicateur"] == ind]
        best = max(rows, key=lambda n: n["note"])
        worst = min(rows, key=lambda n: n["note"])
        assert best["note"] == 100 and worst["note"] == 0
        # « moins, c'est mieux » : la meilleure note va à la plus petite valeur
        assert (best["valeur"] < worst["valeur"]) == (best["sens"] < 0)
    ranks = [r["rang"] for r in page["fr_villes_classement"]]
    assert ranks == sorted(ranks)
    assert [p["pilier"] for p in page["piliers"]] == ["Francophonie", "Coût de la vie", "Emploi", "Cadre de vie"]
