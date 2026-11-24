from pathlib import Path

import pytest

from app.application.use_cases.territory_dashboard import TerritoryDashboard
from app.domain.territory import MICRO_REGIONS, correlation_strength, normalize_region
from app.infrastructure.sql.repository import Database
from app.infrastructure.sql.territory_repository import DuckTerritoryRepository

RAW = Path(__file__).resolve().parents[1] / "data" / "raw"


def test_domain_rules():
    assert len(MICRO_REGIONS) == 24
    assert normalize_region("Sud") == "Sud" and normalize_region("'; DROP TABLE x") == "ALL"
    assert correlation_strength(0.75) == "forte positive"
    assert correlation_strength(-0.5) == "modérée négative"
    assert correlation_strength(0.05) == "négligeable"


@pytest.fixture(scope="module")
def uc():
    if not (RAW / "dvf.csv").exists():
        pytest.skip("open data absente : python -m app.infrastructure.opendata.fetch")
    repo = DuckTerritoryRepository(Database(":memory:"), RAW)
    assert repo.load()
    return TerritoryDashboard(repo)


def test_panel_filters_by_region(uc):
    island, sud = uc.panel(None), uc.panel("Sud")
    assert island["kpis"]["nb_communes"] == 24 and sud["kpis"]["nb_communes"] == 10
    assert 0 < sud["kpis"]["pop"] < island["kpis"]["pop"]
    assert all(r["region"] == "Sud" for r in sud["prix_evol"])


def test_correlation_matrix_is_symmetric(uc):
    m = {(r["x"], r["y"]): r["pearson"] for r in uc.cross()["corr_matrix"]}
    assert all(abs(v - m[(y, x)]) < 1e-9 for (x, y), v in m.items())
    assert all(m[(x, x)] == 1 for x, _ in m)


def test_lineage_covers_every_source_and_query(uc):
    lin = uc.lineage()
    assert {s["name"] for s in lin["sources"]} >= {"dvf", "accidents", "meteo_gillot"}
    assert all(s["table_rows"] and s["rows"] >= s["table_rows"] for s in lin["sources"] if not s["name"].startswith("meteo"))
    assert len(lin["steps"]) == 12 and all(s["sql"].startswith("CREATE") for s in lin["steps"])
    assert {"kpis", "corr_matrix", "pair"} <= {q["name"] for q in lin["queries"]}


def test_pair_rejects_unknown_columns(uc):
    with pytest.raises(ValueError):
        uc.pair("prix_m2; DROP TABLE od_dvf", "revenu_median")
    p = uc.pair("revenu_median", "prix_m2")
    assert p["n"] >= 10 and -1 <= p["r"] <= 1
