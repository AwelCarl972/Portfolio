"""Téléchargement des jeux open data de La Réunion (data.regionreunion.com, API Opendatasoft).

Filtrage et agrégation faits côté serveur (select / where / group_by) : on ne rapatrie que l'utile.
    python -m app.infrastructure.opendata.fetch
"""
import sys
import urllib.parse
import urllib.request
from pathlib import Path

BASE = "https://data.regionreunion.com/api/explore/v2.1/catalog/datasets"
RAW = Path("data/raw")

DATASETS: dict[str, tuple[str, dict]] = {
    # Transactions immobilières (DVF) 2014-2025 : maisons et appartements vendus
    "dvf": ("demande-de-valeurs-foncierespublic", {
        "select": "datemut, l_codinsee, valeurfonc, sbati, libtypbien, vefa",
        "where": "libnatmut = 'Vente' AND libtypbien IN ('UNE MAISON', 'UN APPARTEMENT')"}),
    # Revenus, pauvreté, inégalités à l'IRIS (INSEE Filosofi 2014)
    "revenus_iris": ("revenus-declares-pauvrete-et-niveau-de-vie-en-2015-irispublic", {
        "select": "iris, libiris, com, libcom, dec_med14, dec_tp6014, dec_gi14, dec_d114, dec_d914, "
                  "dec_pcho14, dec_ppen14, pop_menages_en_2014_princ",
        "where": "code_dep = '974'"}),
    # Population légale des communes (tous millésimes)
    "population": ("population-francaise-communespublic", {
        "select": "code_insee, nom_de_la_commune, population_municipale, superficie, annee_recensement",
        "where": "code_departement = '974'"}),
    # Demandeurs d'emploi inscrits, par commune et par mois
    "chomage": ("demandeurs-d-emploi-inscrits-a-pole-emploi-par-commune-a-la-reunion", {
        "select": "code_commune_insee, nom_de_la_commune, date, inscrits"}),
    # Permis de construire créant des logements
    "permis": ("liste-des-permis-de-construire-et-autres-autorisations-d-urbanisme-a-la-reunion", {
        "select": "num_dau, comm, type_dau, date_reelle_autorisation, nb_lgt_tot_crees, nb_lgt_ind_crees, "
                  "nb_lgt_col_crees, nb_lgt_pret_loc_social, surf_hab_creee"}),
    # Accidents corporels de la circulation (BAAC) 2016-2019, une ligne par usager
    "accidents": ("bases-de-donnees-annuelles-des-accidents-corporels-de-la-circulation-routiere", {
        "select": "num_acc, datetime, an, mois, hrmn, com, nom_com, lum, atm, agg, catr, surf, grav, "
                  "catu, catv, sexe, an_nais, lat, long"}),
    # Météo SYNOP tri-horaire, station Gillot-Aéroport (seule station 974 du jeu), 2010 -> aujourd'hui
    "meteo_gillot": ("donnees-synop-essentielles-ommpublic", {
        "select": "date, tc, u, rr3, ff, raf10, pmer_hpa",
        "where": "code_dep = '974'"}),
}

# Fichiers téléchargés tels quels (pas d'API de filtrage) : base climatologique Météo-France,
# relevés mensuels de toutes les stations de La Réunion (data.gouv.fr / meteo.data.gouv.fr)
MF = "https://meteofrance.s3.sbg.io.cloud.ovh.net/data/synchro_ftp/BASE/MENS"
FILES: dict[str, str] = {
    "meteo_mens_1950_2024": f"{MF}/MENSQ_974_previous-1950-2024.csv.gz",
    "meteo_mens_2025_2026": f"{MF}/MENSQ_974_latest-2025-2026.csv.gz",
}


def fetch(name: str) -> Path:
    if name in FILES:
        url, out = FILES[name], RAW / f"{name}.csv.gz"
    else:
        dataset, params = DATASETS[name]
        url = f"{BASE}/{dataset}/exports/csv?" + urllib.parse.urlencode({"delimiter": ";", **params})
        out = RAW / f"{name}.csv"
    with urllib.request.urlopen(url, timeout=300) as r:
        out.write_bytes(r.read())
    return out


if __name__ == "__main__":
    RAW.mkdir(parents=True, exist_ok=True)
    for n in sys.argv[1:] or [*DATASETS, *FILES]:
        p = fetch(n)
        print(f"{n:22} {p.stat().st_size / 1024:9.0f} Ko")
