"""Adaptateur DuckDB de la page Électricité de La Réunion (open data EDF)."""
from pathlib import Path

from app.domain.energie import COMMUNES, FILIERES, FILIERES_HORAIRES, HAUTS
from app.domain.territory import MICRO_REGIONS

from .repository import Database, _load_queries
from .territory_repository import _lead_comments

_DIR = Path(__file__).parent
_SCHEMA = "energie_schema.sql"
_QUERIES = "energie_queries.sql"
FICHIERS = ["edf_horaire", "edf_annuel", "edf_co2", "edf_conso"]


class DuckEnergieRepository:
    def __init__(self, db: Database, raw_dir: Path):
        self.db, self.raw_dir = db, raw_dir
        self._ok = False

    def load(self) -> bool:
        """(Re)construit les tables en_* depuis les CSV d'EDF. False s'ils n'ont pas été téléchargés."""
        if not all(p.exists() for p in self._fichiers()):
            return False
        self.db.execute("CREATE OR REPLACE TABLE en_filiere (filiere VARCHAR, libelle VARCHAR, renouvelable BOOLEAN, ordre INT)")
        self.db.many("INSERT INTO en_filiere VALUES (?, ?, ?, ?)", [(c, l, r, i) for i, (c, l, r) in enumerate(FILIERES)])
        self.db.execute("CREATE OR REPLACE TABLE en_filiere_h (colonne VARCHAR, libelle VARCHAR, ordre INT)")
        self.db.many("INSERT INTO en_filiere_h VALUES (?, ?, ?)", [(c, l, i) for i, (c, l) in enumerate(FILIERES_HORAIRES)])
        self.db.execute("CREATE OR REPLACE TABLE en_commune (code_insee VARCHAR, nom VARCHAR, hauts BOOLEAN, region VARCHAR)")
        self.db.many("INSERT INTO en_commune VALUES (?, ?, ?, ?)",
                     [(c, n, c in HAUTS, MICRO_REGIONS[c]) for c, n in COMMUNES.items()])
        sql = (_DIR / _SCHEMA).read_text(encoding="utf-8")
        self.db.execute(sql.replace("{raw}", self.raw_dir.resolve().as_posix()))
        self._ok = True
        return True

    def _fichiers(self) -> list[Path]:
        return [self.raw_dir / f"{f}.csv" for f in FICHIERS]

    def available(self) -> bool:
        return self._ok

    def query(self, name: str) -> list[dict]:
        return self.db.rows(self.db.q[name])

    def sql(self) -> dict[str, dict]:
        """Chaque requête et chaque étape de chargement, avec sa description (boutons « SQL » et section Données)."""
        out = {}
        for chunk in (_DIR / _SCHEMA).read_text(encoding="utf-8").split(";\n\n"):
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
        out = []
        for p in self._fichiers():
            n = self.db.rows(f"SELECT count(*) AS n FROM read_csv('{p.resolve().as_posix()}', all_varchar = true)")[0]["n"]
            out.append({"fichier": p.name, "ko": round(p.stat().st_size / 1024), "lignes": n})
        return out
