from pathlib import Path

import pytest

from app.application.use_cases.btp import BtpShowcase
from app.domain.btp import FAMILLES, HORS_NORME, famille, implantation, tranche, type_acheteur
from app.infrastructure.sql.btp_repository import FICHIERS, DuckBtpRepository
from app.infrastructure.sql.repository import Database

RAW = Path(__file__).resolve().parents[1] / "data" / "raw"


def test_domain():
    assert famille("45210000-2") == "batiment" and famille("45233140-2") == "reseaux"
    assert famille("45000000-7") == "generique" and famille(None) == "generique"
    prefixes = [p for _, _, ps in FAMILLES for p in ps]
    assert len(prefixes) == len(set(prefixes))  # un code CPV ne tombe que dans une famille
    assert tranche(99_999) == "Moins de 100 k€" and tranche(100_000) == "100 k€ à 1 M€" and tranche(9e6) == "Plus de 5 M€"
    assert type_acheteur("7210") == "Communes" and type_acheteur("7230") == "Région et Département"
    assert type_acheteur("7348") == "Intercommunalités et syndicats" and type_acheteur("5515") == "SEM, SPL et bailleurs sociaux"
    assert type_acheteur(None) == "Autres ou inconnus"
    assert implantation("97410") == "À La Réunion" and implantation("75008") == "Hors de La Réunion"


@pytest.fixture(scope="module")
def repo():
    if not all((RAW / f"{f}.csv").exists() for f in FICHIERS):
        pytest.skip("données absentes : python -m app.infrastructure.opendata.fetch decp_arrete2019 decp_arrete2022 sirene_decp permis population")
    r = DuckBtpRepository(Database(":memory:"), RAW)
    assert r.load()
    return r


@pytest.fixture(scope="module")
def page(repo):
    return BtpShowcase(repo).page()


def test_sql_classification_matches_domain(repo):
    # Le SQL classe par jointure sur des tables issues du domaine : il doit rendre exactement ce que disent les fonctions Python
    rows = repo.db.rows("SELECT DISTINCT cpv, famille FROM bt_marche")
    assert all(famille(r["cpv"]) == r["famille"] for r in rows)
    rows = repo.db.rows("SELECT DISTINCT montant, tranche FROM bt_marche")
    assert all(tranche(r["montant"]) == r["tranche"] for r in rows)
    rows = repo.db.rows("""SELECT a.type_acheteur, s.nature_juridique FROM bt_acheteur a
                           LEFT JOIN bt_sirene s ON s.siret = a.acheteur_siret""")
    assert all(type_acheteur(r["nature_juridique"]) == r["type_acheteur"] for r in rows)


def test_shared_ceilings_are_counted_once(repo):
    # Un plafond d'accord-cadre partagé : une seule ligne compte au total, et les parts des titulaires refont le montant
    r = repo.db.rows("""SELECT sum(montant) FILTER (WHERE compte_au_total) AS total, sum(montant_part) AS parts,
                               count(*) FILTER (WHERE nb_attributaires > 1) AS partages FROM bt_marche""")[0]
    assert r["partages"] > 0
    assert r["parts"] == pytest.approx(r["total"], rel=1e-9)


def test_no_duplicates_and_clean_identifiers(repo):
    assert repo.db.rows("""SELECT count(*) AS n FROM (SELECT acheteur_siret, id_marche, titulaire_siret, montant, date_notification
                           FROM bt_attribution GROUP BY ALL HAVING count(*) > 1)""")[0]["n"] == 0
    assert repo.db.rows("SELECT count(*) AS n FROM bt_attribution WHERE length(titulaire_siret) <> 14")[0]["n"] == 0
    assert {r["nature"] for r in repo.db.rows("SELECT DISTINCT nature FROM bt_attribution")} <= {"Marché", "Accord-cadre", "Marché subséquent"}


def test_global_contracts_are_set_apart(repo):
    # Un contrat global de 468 M€ fausserait tous les classements : il est montré à part, jamais compté
    assert repo.db.rows(f"SELECT max(montant) AS m FROM bt_marche")[0]["m"] < HORS_NORME
    assert repo.db.rows("SELECT count(*) AS n FROM bt_hors_norme")[0]["n"] >= 1


def test_one_company_one_line(repo, page):
    # Une entreprise qui signe depuis plusieurs établissements (plusieurs SIRET) n'apparaît qu'une fois au classement
    noms = [r["nom"] for r in page["bt_top_titulaires"] if r["nom"] != "(entrepreneur individuel)"]
    assert len(noms) == len(set(noms))


def test_individual_entrepreneurs_are_never_named(repo):
    noms = repo.db.rows("SELECT nom FROM bt_sirene WHERE starts_with(nature_juridique, '1')")
    assert noms and {r["nom"] for r in noms} == {"(entrepreneur individuel)"}


def test_page(page):
    k = page["kpis"]
    assert k["an_min"] == 2019 and k["marches"] > 3000
    assert 0 < k["part_locale_pct"] <= 100 and 0 < k["offre_unique_pct"] < 100
    assert sum(r["part_montant_pct"] for r in page["bt_acheteurs_type"]) == pytest.approx(100, abs=0.5)
    assert [r["premieres"] for r in page["bt_concentration"]] == [5, 10, 20, 50]
    parts = [r["part_pct"] for r in page["bt_concentration"]]
    assert parts == sorted(parts) and parts[-1] <= 100
    assert [r["annee"] for r in page["bt_logements_an"]] == list(range(2017, 2023))
    assert {r["region"] for r in page["bt_logements_region"]} == {"Nord", "Est", "Ouest", "Sud"}
    assert all(q in page["sql"] for q in ["bt_marche", "bt_par_an", "bt_qualite"])
