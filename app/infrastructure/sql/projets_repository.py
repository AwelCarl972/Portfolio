"""Adaptateur DuckDB de la page Projets (carte des bornes Le Wagon, trading algorithmique)."""
import json
from pathlib import Path

from .repository import Database, _load_queries
from .territory_repository import _lead_comments

_DIR = Path(__file__).parent
_SCHEMA = "projets_schema.sql"


class DuckProjetsRepository:
    def __init__(self, db: Database, raw_dir: Path):
        self.db, self.raw_dir = db, raw_dir
        self._ok = False
        self._backtests: list[dict] = []

    def load(self) -> bool:
        """(Re)construit les tables pj_* depuis les CSV aplatis. False si l'import n'a pas été lancé."""
        if not (self.raw_dir / "bornes.csv").exists() or not (self.raw_dir / "trading_passes.csv").exists():
            return False
        sql = (_DIR / _SCHEMA).read_text(encoding="utf-8")
        self.db.execute(sql.replace("{raw}", self.raw_dir.resolve().as_posix()))
        f = self.raw_dir / "trading_backtests.json"
        self._backtests = json.loads(f.read_text(encoding="utf-8")) if f.exists() else []
        self._ok = True
        return True

    def available(self) -> bool:
        return self._ok

    def query(self, name: str) -> list[dict]:
        return self.db.rows(self.db.q[name])

    def backtests(self) -> list[dict]:
        return self._backtests

    def sql(self) -> dict[str, dict]:
        """Chaque requête et chaque étape de nettoyage, avec sa description : ce que montrent les boutons « SQL »."""
        out = {}
        for name, sql in _load_queries("projets_queries.sql").items():
            desc, code = _lead_comments(sql)
            out[name] = {"description": desc, "sql": code}
        schema = (_DIR / _SCHEMA).read_text(encoding="utf-8")
        for chunk in schema.split(";\n\n"):
            body = chunk.split("\n\n")[-1] if "CREATE" in chunk.split("\n\n")[-1] else chunk
            if "CREATE OR REPLACE TABLE" not in body:
                continue
            desc, code = _lead_comments(body)
            name = code.split("CREATE OR REPLACE TABLE ", 1)[1].split()[0]
            out[name] = {"description": desc, "sql": code.rstrip(";") + ";"}
        return out
