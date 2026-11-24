"""Page Projets : import des sources, règles de nettoyage, et ce que les requêtes doivent tenir."""
import json
from pathlib import Path

import pytest

from app.application.use_cases.projets import ProjetsShowcase
from app.infrastructure.projets import importer
from app.infrastructure.sql.projets_repository import DuckProjetsRepository
from app.infrastructure.sql.repository import Database

_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet" xmlns:o="urn:schemas-microsoft-com:office:office"
 xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet">
<DocumentProperties xmlns="urn:schemas-microsoft-com:office:office">
<Title>Robot EURUSD,M15 2021.03.03-2021.04.02</Title><Created>2022-02-11T17:30:16Z</Created>
<Deposit>100000 EUR</Deposit><Leverage>30</Leverage></DocumentProperties>
<Worksheet ss:Name="R"><Table>
<Row>{head}</Row>{rows}
</Table></Worksheet></Workbook>"""
_COLS = ["Pass", "Result", "Profit", "Expected Payoff", "Profit Factor", "Recovery Factor", "Sharpe Ratio",
         "Custom", "Equity DD %", "Trades", "SL"]


def _cell(v):
    return f'<Cell><Data ss:Type="String">{v}</Data></Cell>'


@pytest.fixture()
def sources(tmp_path: Path) -> Path:
    """Un mini projet Le Wagon et un mini dossier Trading, avec les défauts des vrais."""
    lw = tmp_path / "ProjetFinal"
    lw.mkdir()
    pt = lambda lat, lon, kw: {"code_insee": "97411", "latitude": lat, "longitude": lon, "nbre_pdc": 1, "puissance_nominale": kw}
    (lw / "bornes_recharge_mensuel.json").write_text(json.dumps({
        "1930-01": [pt(45.6, 5.8, 22.0)],                          # date aberrante
        "2023-05": [pt(48.85, 2.35, 150.0), pt(48.85, 2.35, 0.0)],  # même site, une puissance manquante
        "2024-02": [pt(-20.88, 55.45, 22.0)],                       # La Réunion
    }), encoding="utf-8")
    tr = tmp_path / "Trading"
    (tr / "Optimisation").mkdir(parents=True)
    (tr / "BackTest").mkdir()
    passes = [[1, 0, 900, 0, 9, 1, 1, 0, 2.0, 8, 10], [2, 0, -400, 0, 0.5, 0, 0, 0, 12.0, 150, 20],
              [3, 0, 100, 0, 1.1, 1, 0.1, 0, 5.0, 40, 30]]
    (tr / "Optimisation" / "opt.xml").write_text(_XML.format(
        head="".join(_cell(c) for c in _COLS),
        rows="".join("<Row>" + "".join(_cell(v) for v in r) + "</Row>" for r in passes)), encoding="utf-8")
    (tr / "BackTest" / "rapport.html").write_text(
        "<table><tr><td>Expert:</td><td>Robot</td></tr><tr><td>Facteur de profit:</td><td>9.00</td></tr>"
        "<tr><td>Nb trades:</td><td>11</td></tr></table><table><tr><td>Ordres</td></tr></table>", encoding="utf-16")
    dest = tmp_path / "raw"
    importer.main(["--lewagon", str(lw), "--trading", str(tr), "--dest", str(dest)])
    return dest


@pytest.fixture()
def uc(sources: Path) -> ProjetsShowcase:
    repo = DuckProjetsRepository(Database(":memory:"), sources)
    assert repo.load()
    return ProjetsShowcase(repo)


def test_import_aplatit_sans_nettoyer(sources):
    assert len((sources / "bornes.csv").read_text(encoding="utf-8").strip().splitlines()) == 1 + 4
    meta = json.loads((sources / "trading_optimisations.json").read_text(encoding="utf-8"))
    assert meta[0]["symbole"] == "EURUSD" and meta[0]["debut"] == "2021-03-03"
    bt = json.loads((sources / "trading_backtests.json").read_text(encoding="utf-8"))
    assert bt[0]["resume"] == {"Expert": "Robot", "Facteur de profit": "9.00", "Nb trades": "11"}


def test_nettoyage_des_bornes_compte_chaque_regle(uc):
    page = uc.page()
    qualite = {q["regle"][:12]: q["lignes"] for q in page["bornes"]["qualite"]}
    assert qualite["Points livré"] == 4
    assert qualite["Écartés : mi"] == 1        # 1930 écarté…
    assert qualite["Gardés, puis"] == 1        # …0 kW gardé comme inconnu, pas comme borne à 0 kW
    assert qualite["Retenus pour"] == 3
    k = page["bornes"]["kpis"]
    assert (k["points"], k["sites"], k["points_reunion"]) == (3, 2, 1)
    assert k["part_hp"] == 50.0                # 1 sur les 2 points de puissance connue


def test_le_site_porte_la_date_de_son_premier_point(uc):
    sites = uc.donnees("bornes_sites")
    paris = next(s for s in sites if s["territoire"] == "Métropole")
    assert paris["points"] == 2 and paris["puissance_max"] == 150.0
    assert paris["rang"] == 12 * 13 + 4      # mai 2023, compté depuis janvier 2010


def test_trading_classe_les_passes_et_isole_les_faibles_volumes(uc):
    r = uc.page()["trading"]["resume"][0]
    assert (r["passes"], r["profit_max"], r["trades_meilleure"]) == (3, 900, 8)
    assert r["pct_rentables"] == 67
    vol = {f["volume"]: f["passes"] for f in uc.page()["trading"]["fiabilite"]}
    assert vol == {"< 30 trades": 1, "30-99 trades": 1, "≥ 100 trades": 1}


def test_donnees_en_liste_blanche(uc):
    with pytest.raises(ValueError):
        uc.donnees("pj_borne_brut; DROP TABLE pj_borne")


def test_absent_tant_que_l_import_n_a_pas_tourne(tmp_path):
    assert not DuckProjetsRepository(Database(":memory:"), tmp_path).load()
