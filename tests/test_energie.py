from pathlib import Path

import pytest

from app.application.use_cases.energie import EnergieShowcase
from app.domain.energie import COMMUNES, FILIERES, HAUTS, renouvelable
from app.domain.territory import MICRO_REGIONS
from app.infrastructure.sql.energie_repository import FICHIERS, DuckEnergieRepository
from app.infrastructure.sql.repository import Database

RAW = Path(__file__).resolve().parents[1] / "data" / "raw"


def test_domain():
    assert set(COMMUNES) == set(MICRO_REGIONS) and HAUTS <= set(COMMUNES)
    assert renouvelable("hydraulique") and not renouvelable("charbon")
    assert [c for c, _, r in FILIERES if not r] == ["charbon", "moteurs_diesel", "turbines_a_combustion_fioul"]


@pytest.fixture(scope="module")
def repo():
    if not all((RAW / f"{f}.csv").exists() for f in FICHIERS):
        pytest.skip("données EDF absentes : python -m app.infrastructure.opendata.fetch edf_horaire edf_annuel edf_co2 edf_conso")
    r = DuckEnergieRepository(Database(":memory:"), RAW)
    assert r.load()
    return r


@pytest.fixture(scope="module")
def page(repo):
    return EnergieShowcase(repo).page()


def test_solar_peaks_at_the_same_local_hour_every_year(repo):
    # Sans correction du fuseau, le pic de 2024 tomberait à 12 h ou 13 h (heure de Paris) au lieu de 11 h
    pics = repo.db.rows("""SELECT year(heure) AS an, arg_max(h, pv) AS h FROM (
        SELECT heure, hour(heure) AS h, avg(photovoltaique_mw) OVER (PARTITION BY year(heure), hour(heure)) AS pv
        FROM en_horaire) GROUP BY 1""")
    assert {p["h"] for p in pics} == {11}


def test_one_row_per_hour(repo):
    n = repo.db.rows("SELECT count(*) AS n, count(DISTINCT heure) AS d FROM en_horaire")[0]
    assert n["n"] == n["d"]
    trous = repo.db.rows("""SELECT count(*) AS n FROM (SELECT date_diff('hour', heure, lead(heure) OVER (ORDER BY heure)) AS g
                            FROM en_horaire) WHERE g > 1""")[0]["n"]
    assert trous <= 1  # une heure de juin 2021 manque dans le fichier : on ne l'invente pas


def test_recomputed_renewable_share_matches_edf(page):
    for r in page["en_part_q"]:
        assert abs(r["part_enr"] - r["part_enr_publiee"]) < 0.1, r["annee"]


def test_the_switch(page):
    k = page["kpis"]
    assert k["part_enr_2021"] < 30 and k["part_enr"] > 90
    assert k["co2_kt"] < k["co2_kt_2021"] / 5


def test_every_commune_is_known(page):
    assert len(page["en_communes"]) == len(COMMUNES)
    cilaos = next(c for c in page["en_communes"] if c["code_insee"] == "97424")
    assert cilaos["rang"] == len(COMMUNES)  # bourg à 1 200 m : pas de climatisation
