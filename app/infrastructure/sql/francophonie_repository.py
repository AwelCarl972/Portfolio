"""Adaptateur DuckDB de la page Francophonie canadienne (Statistique Canada, recensements 1951-2021)."""
from pathlib import Path

from app.domain.francophonie import GEOS, PILIERS, VILLES

from .repository import Database, _load_queries
from .territory_repository import _lead_comments

_DIR = Path(__file__).parent
_SCHEMA = "francophonie_schema.sql"
_QUERIES = "francophonie_queries.sql"
FICHIERS = ["statcan_langue_maternelle", "statcan_plos", "statcan_connaissance", "statcan_langue_maison",
            "ircc_francophones_rmr", "ircc_rp_rmr", "statcan_recensement_villes"]
FICHIERS_GZ = ["statcan_mbm", "statcan_loyers", "statcan_revenus", "statcan_chomage_rmr", "statcan_criminalite",
               "statcan_satisfaction"]


class DuckFrancophonieRepository:
    def __init__(self, db: Database, raw_dir: Path):
        self.db, self.raw_dir = db, raw_dir
        self._ok = False

    def load(self) -> bool:
        """(Re)construit les tables fr_* depuis les CSV de Statistique Canada. False s'ils n'ont pas été téléchargés."""
        if not all(p.exists() for p in self._fichiers()):
            return False
        self.db.execute("CREATE OR REPLACE TABLE fr_geo (geo_en VARCHAR, code VARCHAR, nom VARCHAR, type VARCHAR)")
        self.db.many("INSERT INTO fr_geo VALUES (?, ?, ?, ?)", [(en, *v) for en, v in GEOS.items()])
        self.db.execute("CREATE OR REPLACE TABLE fr_ville (code VARCHAR, nom VARCHAR, province VARCHAR, geo_mpc VARCHAR, "
                        "geo_loyer VARCHAR, geo_revenu VARCHAR, geo_crime VARCHAR, geo_chomage VARCHAR, rmr_ircc VARCHAR, "
                        "geo_recensement VARCHAR)")
        self.db.many("INSERT INTO fr_ville VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", VILLES)
        self.db.execute("CREATE OR REPLACE TABLE fr_pilier (pilier VARCHAR, indicateur VARCHAR, libelle VARCHAR, sens INT)")
        self.db.many("INSERT INTO fr_pilier VALUES (?, ?, ?, ?)",
                     [(pilier, col, lib, sens) for pilier, inds in PILIERS.items() for col, lib, sens in inds])
        sql = (_DIR / _SCHEMA).read_text(encoding="utf-8")
        self.db.execute(sql.replace("{raw}", self.raw_dir.resolve().as_posix()))
        self._ok = True
        return True

    def _fichiers(self) -> list[Path]:
        return [self.raw_dir / f"{f}.csv" for f in FICHIERS] + [self.raw_dir / f"{f}.csv.gz" for f in FICHIERS_GZ]

    def available(self) -> bool:
        return self._ok

    def query(self, name: str) -> list[dict]:
        return self.db.rows(self.db.q[name])

    def sql(self) -> dict[str, dict]:
        """Chaque requête et chaque étape de chargement, avec sa description (boutons « SQL » et onglet Données)."""
        out = {}
        schema = (_DIR / _SCHEMA).read_text(encoding="utf-8")
        for chunk in schema.split(";\n\n"):
            body = chunk.split("\n\n")[-1]
            if "CREATE OR REPLACE TABLE" not in body:
                continue
            desc, code = _lead_comments(body)
            name = code.split("CREATE OR REPLACE TABLE ", 1)[1].split()[0]
            out[name] = {"description": desc, "sql": code.rstrip().rstrip(";") + ";", "etape": True}
        for name, sql in _load_queries(_QUERIES).items():
            desc, code = _lead_comments(sql)
            out[name] = {"description": desc, "sql": code, "etape": False}
        return out

    def sources(self) -> list[dict]:
        """Fichiers bruts : taille et lignes, pour le tableau des sources."""
        out = []
        for p in self._fichiers():
            delim = "	" if p.name.startswith("ircc") else ","
            n = self.db.rows(f"SELECT count(*) AS n FROM read_csv('{p.resolve().as_posix()}', delim = '{delim}', "
                             "header = true, all_varchar = true)")[0]["n"]
            out.append({"fichier": p.name, "ko": round(p.stat().st_size / 1024), "lignes": n})
        return out
