"""Téléchargement des jeux open data : La Réunion (data.regionreunion.com, API Opendatasoft) et Statistique Canada.

Filtrage et agrégation faits côté serveur (select / where / group_by) : on ne rapatrie que l'utile.
    python -m app.infrastructure.opendata.fetch
"""
import gzip
import io
import json
import sys
import urllib.parse
import urllib.request
import zipfile
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


# Statistique Canada, tableaux historiques des recensements (1951-2021) : archive zip, on n'en garde que le CSV
STATCAN = "https://www150.statcan.gc.ca/n1/tbl/csv/{pid}-eng.zip"
TABLES: dict[str, str] = {
    "statcan_langue_maternelle": "15100031",   # langue maternelle, 1951-2021
    "statcan_plos": "15100032",                # première langue officielle parlée, 1971-2021
    "statcan_connaissance": "15100004",        # connaissance des langues officielles (bilinguisme), 1951-2021
    "statcan_langue_maison": "15100033",       # langue parlée le plus souvent à la maison, 1971-2021
}
# Comparatif des villes : tableaux récents, recompressés en gzip (le revenu seul pèse 45 Mo décompressé)
TABLES_GZ: dict[str, str] = {
    "statcan_mbm": "11100066",          # seuils de la mesure du panier de consommation (MPC), 2002-2025
    "statcan_loyers": "34100133",       # loyers moyens SCHL par ville et taille de logement, 1987-2025
    "statcan_revenus": "11100190",      # revenu médian après impôt par type de famille, 1976-2024
    "statcan_chomage_rmr": "14100385",  # enquête sur la population active, annuel par ville, 2006-2024
    "statcan_criminalite": "35100026",  # indice de gravité de la criminalité, 1998-2025
    "statcan_satisfaction": "13100843", # satisfaction à l'égard de la vie par province, 2021-2025
}
# Immigration, Réfugiés et Citoyenneté Canada : résidents permanents par ville de destination, mensuel depuis 2015
IRCC = "https://www.ircc.canada.ca/opendata-donneesouvertes/data/"
IRCC_FILES: dict[str, str] = {
    "ircc_francophones_rmr": "ODP-French-speaking-PR-CMA.csv",  # résidents permanents d'expression française, hors Québec
    "ircc_rp_rmr": "ODP-PR-PT_CMA.csv",                         # tous les résidents permanents
}
_AGENT = {"User-Agent": "opendata-fetch/1.0"}  # les deux serveurs rejettent l'agent par défaut « Python-urllib » (403)

# Recensement 2021 par ville (tableau 98-10-0192-01, 29 Mo zippé) : l'API web de Statistique Canada ne renvoie que les
# cellules demandées. Coordonnée = géographie.genre.âge.langue_maison.première_langue_officielle (+ 5 zéros)
WDS = "https://www150.statcan.gc.ca/t1/wds/rest/getDataFromCubePidCoordAndLatestNPeriods"
RECENSEMENT_PID = 98100192
RECENSEMENT_GEOS = {24: "Moncton (CMA), N.B.", 12: "Halifax (CMA), N.S.", 86: "Ottawa - Gatineau (Ontario part) (CMA), Ont.",
                    68: "Greater Sudbury (CMA), Ont.", 100: "Toronto (CMA), Ont.", 110: "Winnipeg (CMA), Man.",
                    126: "Edmonton (CMA), Alta.", 123: "Calgary (CMA), Alta.", 166: "Vancouver (CMA), B.C."}
RECENSEMENT_CELLULES = {  # (âge, langue de la maison, première langue officielle) : 1 = total ; âge 2 = 0-14 ans ; maison 5 = français ; PLOP 3 = français
    "population": (1, 1, 1), "plop_fr": (1, 1, 3), "plop_fr_maison_fr": (1, 5, 3),
    "enfants": (2, 1, 1), "enfants_plop_fr": (2, 1, 3),
}


def _recensement_villes() -> bytes:
    demandes = [{"productId": RECENSEMENT_PID, "coordinate": f"{g}.1.{a}.{m}.{p}.0.0.0.0.0", "latestN": 1}
                for g in RECENSEMENT_GEOS for a, m, p in RECENSEMENT_CELLULES.values()]
    req = urllib.request.Request(WDS, data=json.dumps(demandes).encode(), headers={**_AGENT, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        reponses = json.loads(r.read())
    cle = {coord: (RECENSEMENT_GEOS[g], nom) for g in RECENSEMENT_GEOS for nom, (a, m, p) in RECENSEMENT_CELLULES.items()
           for coord in [f"{g}.1.{a}.{m}.{p}.0.0.0.0.0"]}
    lignes = ["geo,mesure,valeur"]
    for rep in reponses:
        o = rep["object"]
        geo, mesure = cle[o["coordinate"]]
        lignes.append(f'"{geo}",{mesure},{o["vectorDataPoint"][0]["value"]}')
    return ("\n".join(lignes) + "\n").encode()


def _get(url: str) -> bytes:
    with urllib.request.urlopen(urllib.request.Request(url, headers=_AGENT), timeout=300) as r:
        return r.read()


def fetch(name: str) -> Path:
    if name in TABLES or name in TABLES_GZ:
        pid = TABLES.get(name) or TABLES_GZ[name]
        with zipfile.ZipFile(io.BytesIO(_get(STATCAN.format(pid=pid)))) as z:
            csv = z.read(f"{pid}.csv")  # le fichier _MetaData n'est pas chargé
        out = RAW / f"{name}.csv" if name in TABLES else RAW / f"{name}.csv.gz"
        out.write_bytes(csv if name in TABLES else gzip.compress(csv))
        return out
    if name in IRCC_FILES:
        out = RAW / f"{name}.csv"
        out.write_bytes(_get(IRCC + IRCC_FILES[name]))
        return out
    if name == "statcan_recensement_villes":
        out = RAW / f"{name}.csv"
        out.write_bytes(_recensement_villes())
        return out
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
    for n in sys.argv[1:] or [*DATASETS, *FILES, *TABLES, *TABLES_GZ, *IRCC_FILES, "statcan_recensement_villes"]:
        p = fetch(n)
        print(f"{n:22} {p.stat().st_size / 1024:9.0f} Ko")
