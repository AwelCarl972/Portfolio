"""Adaptateur DuckDB de la page BTP à La Réunion (commande publique DECP, SIRENE, permis Sitadel)."""
from pathlib import Path

from app.domain.btp import FAMILLES, HORS_NORME, TRANCHES, TYPES_ACHETEUR
from app.domain.energie import COMMUNES
from app.domain.territory import MICRO_REGIONS

from .repository import Database, _load_queries
from .territory_repository import _lead_comments

_DIR = Path(__file__).parent
_SCHEMA = "btp_schema.sql"
_QUERIES = "btp_queries.sql"
FICHIERS = ["decp_arrete2019", "decp_arrete2022", "sirene_decp", "permis", "population"]


class DuckBtpRepository:
    def __init__(self, db: Database, raw_dir: Path):
        self.db, self.raw_dir = db, raw_dir
        self._ok = False

    def load(self) -> bool:
        """(Re)construit les tables bt_* depuis les CSV. False s'ils n'ont pas été téléchargés."""
        if not all(p.exists() for p in self._fichiers()):
            return False
        self.db.execute("CREATE OR REPLACE TABLE bt_famille (famille VARCHAR, libelle VARCHAR, ordre INT)")
        self.db.many("INSERT INTO bt_famille VALUES (?, ?, ?)", [(f, l, i) for i, (f, l, _) in enumerate(FAMILLES)])
        self.db.execute("CREATE OR REPLACE TABLE bt_famille_cpv (prefixe VARCHAR, famille VARCHAR)")
        self.db.many("INSERT INTO bt_famille_cpv VALUES (?, ?)", [(p, f) for f, _, ps in FAMILLES for p in ps])
        self.db.execute("CREATE OR REPLACE TABLE bt_tranche (borne_basse DOUBLE, borne_haute DOUBLE, libelle VARCHAR, ordre INT)")
        bornes = [0.0] + [b for b, _ in TRANCHES[:-1]]
        self.db.many("INSERT INTO bt_tranche VALUES (?, ?, ?, ?)",
                     [(bornes[i], b, l, i) for i, (b, l) in enumerate(TRANCHES)])
        self.db.execute("CREATE OR REPLACE TABLE bt_type_acheteur (prefixe VARCHAR, libelle VARCHAR, ordre INT)")
        self.db.many("INSERT INTO bt_type_acheteur VALUES (?, ?, ?)",
                     [(p, l, i) for i, (ps, l) in enumerate(TYPES_ACHETEUR) for p in ps])
        self.db.execute("CREATE OR REPLACE TABLE bt_commune (code_insee VARCHAR, nom VARCHAR, region VARCHAR)")
        self.db.many("INSERT INTO bt_commune VALUES (?, ?, ?)", [(c, n, MICRO_REGIONS[c]) for c, n in COMMUNES.items()])
        sql = (_DIR / _SCHEMA).read_text(encoding="utf-8")
        self.db.execute(sql.replace("{raw}", self.raw_dir.resolve().as_posix()).replace("{hors_norme}", str(HORS_NORME)))
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
