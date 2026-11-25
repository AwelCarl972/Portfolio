"""Adaptateurs DuckDB : exécution SQL uniquement, zéro logique métier."""
import re
import threading
from pathlib import Path

import duckdb

from app.domain.models import Entity, Kind, RiskRow, SupplyAlert

_DIR = Path(__file__).parent


def _load_queries(*files: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for f in files:
        parts = re.split(r"^-- name: (\w+)\s*$", (_DIR / f).read_text(encoding="utf-8"), flags=re.M)
        out |= {parts[i]: parts[i + 1].strip() for i in range(1, len(parts), 2)}
    return out


class Database:
    def __init__(self, path: str):
        self._con = duckdb.connect(path)
        self._lock = threading.RLock()
        self.q = _load_queries("queries.sql", "territory_queries.sql", "projets_queries.sql", "francophonie_queries.sql",
                               "energie_queries.sql", "btp_queries.sql")
        self.execute((_DIR / "schema.sql").read_text(encoding="utf-8"))

    def execute(self, sql: str, params: tuple = ()):
        with self._lock:
            self._con.execute(sql, params)

    def many(self, sql: str, rows: list):
        with self._lock:
            self._con.executemany(sql, rows)

    def rows(self, sql: str, params: tuple | dict = ()) -> list[dict]:
        with self._lock:
            cur = self._con.execute(sql, params)
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, r)) for r in cur.fetchall()]


class DuckFleetRepository:
    def __init__(self, db: Database):
        self.db = db

    def risk_ranking(self) -> list[RiskRow]:
        return [RiskRow(**r) for r in self.db.rows(self.db.q["fleet_risk"])]

    def supply_alerts(self) -> list[SupplyAlert]:
        return [SupplyAlert(**r) for r in self.db.rows(self.db.q["supply_alerts"])]

    def sql(self) -> dict[str, str]:
        """Le SQL tel qu'exécuté, pour l'afficher sous les graphiques."""
        return {k: self.db.q[k] for k in ("fleet_risk", "supply_alerts")}

    def latest_report(self, asset_id: int) -> str | None:
        rows = self.db.rows(self.db.q["latest_report"], (asset_id,))
        return rows[0]["report"] if rows else None


class DuckMappingStore:
    def __init__(self, db: Database):
        self.db = db

    def original(self, alias: str) -> str | None:
        r = self.db.rows("SELECT original FROM privacy_map WHERE alias = ?", (alias,))
        return r[0]["original"] if r else None

    def put(self, alias: str, kind: str, original: str) -> None:
        self.db.execute("INSERT INTO privacy_map (alias, kind, original) VALUES (?, ?, ?)"
                        " ON CONFLICT DO NOTHING", (alias, kind, original))

    def all(self) -> list[dict]:
        return self.db.rows("SELECT alias, kind, original FROM privacy_map ORDER BY kind, alias")


class DuckEntityCatalog:
    def __init__(self, db: Database):
        self.db = db

    def entities(self) -> list[Entity]:
        return [Entity(Kind(r["kind"]), r["value"]) for r in self.db.rows(self.db.q["catalog"])]
