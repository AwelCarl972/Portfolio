"""Adaptateur DuckDB du tableau de bord territorial (open data Réunion)."""
import json
import re
from pathlib import Path

from app.domain.territory import CYCLONES, INDICATORS, MICRO_REGIONS
from app.infrastructure.opendata.fetch import BASE, DATASETS, FILES
from app.infrastructure.privacy import rust_engine

from .repository import Database, _load_queries

_DIR = Path(__file__).parent
_SCHEMA = "territory_schema.sql"
# Fichier brut -> table analytique qui en est issue
_TARGET = {"dvf": "od_dvf", "revenus_iris": "od_revenus", "population": "od_population", "chomage": "od_chomage",
           "permis": "od_permis", "accidents": "od_accident", "meteo_gillot": "od_meteo_jour",
           "meteo_mens_1950_2024": "od_meteo_mens", "meteo_mens_2025_2026": "od_meteo_mens"}

# Requête dynamique : seuls des noms de colonnes de la liste blanche INDICATORS y sont injectés
PAIR_SQL = """SELECT nom, region, {x} AS x, {y} AS y, pop_2016,
       regr_slope({y}, {x}) OVER () AS slope,
       regr_intercept({y}, {x}) OVER () AS intercept,
       regr_r2({y}, {x}) OVER () AS r2,
       corr({y}, {x}) OVER () AS r,
       COUNT(*) OVER () AS n
FROM v_commune_features
WHERE {x} IS NOT NULL AND {y} IS NOT NULL
ORDER BY nom"""


def _lead_comments(sql: str) -> tuple[str, str]:
    """Sépare les commentaires de tête (description) du code SQL."""
    lines = sql.strip().splitlines()
    i = 0
    while i < len(lines) and lines[i].lstrip().startswith("--"):
        i += 1
    desc = " ".join(l.lstrip("- ").strip() for l in lines[:i])
    return desc, "\n".join(lines[i:]).strip()


class DuckTerritoryRepository:
    def __init__(self, db: Database, raw_dir: Path):
        self.db, self.raw_dir = db, raw_dir
        self._ok = False

    def load(self) -> bool:
        """(Re)construit les tables od_* depuis les CSV bruts. Retourne False si les CSV manquent."""
        if not (self.raw_dir / "dvf.csv").exists():
            return False
        self.db.execute("CREATE OR REPLACE TABLE od_micro_region (code_insee VARCHAR, region VARCHAR)")
        self.db.many("INSERT INTO od_micro_region VALUES (?, ?)", list(MICRO_REGIONS.items()))
        self.db.execute("CREATE OR REPLACE TABLE od_cyclone (annee INTEGER, mois INTEGER, nom VARCHAR)")
        self.db.many("INSERT INTO od_cyclone VALUES (?, ?, ?)", [(y, m, n) for (y, m), n in CYCLONES.items()])
        sql = (_DIR / _SCHEMA).read_text(encoding="utf-8")
        self.db.execute(sql.replace("{raw}", self.raw_dir.resolve().as_posix()))
        self._ok, self._lineage = True, None
        return True

    def available(self) -> bool:
        return self._ok

    def query(self, name: str, region: str = "ALL") -> list[dict]:
        sql = self.db.q[name]
        return self.db.rows(sql, {"region": region} if "$region" in sql else ())

    def pair(self, x: str, y: str) -> list[dict]:
        if x not in INDICATORS or y not in INDICATORS:  # identifiants SQL : liste blanche stricte
            raise ValueError("indicateur inconnu")
        return self.db.rows(PAIR_SQL.format(x=x, y=y))

    # --- Lignage : tout ce qui a servi à produire les chiffres, lu depuis les vraies sources ---

    def lineage(self) -> dict:
        """Calculé une fois par chargement : les données ne changent qu'au redémarrage."""
        if getattr(self, "_lineage", None) is None:
            self._lineage = self._build_lineage()
        return self._lineage

    def _build_lineage(self) -> dict:
        sources = []
        for name, (dataset, params) in DATASETS.items():
            f = self.raw_dir / f"{name}.csv"
            rows = self.db.rows(f"SELECT COUNT(*) AS n FROM read_csv('{f.resolve().as_posix()}', delim=';', header=true)")[0]["n"] if f.exists() else None
            sources.append({"name": name, "dataset": dataset, "url": f"https://data.regionreunion.com/explore/dataset/{dataset}/",
                            "api": f"{BASE}/{dataset}/exports/csv", "params": params, "file": f"data/raw/{name}.csv",
                            "size_kb": round(f.stat().st_size / 1024) if f.exists() else None, "rows": rows})
        for name, url in FILES.items():
            f = self.raw_dir / f"{name}.csv.gz"
            rows = self.db.rows(f"SELECT COUNT(*) AS n FROM read_csv('{f.resolve().as_posix()}', delim=';', header=true)")[0]["n"] if f.exists() else None
            sources.append({"name": name, "dataset": url.rsplit("/", 1)[-1],
                            "url": "https://meteo.data.gouv.fr/datasets/donnees-climatologiques-de-base-mensuelles",
                            "api": url, "params": {"fichier": "téléchargé tel quel (gzip), lu directement par DuckDB"},
                            "file": f"data/raw/{name}.csv.gz",
                            "size_kb": round(f.stat().st_size / 1024) if f.exists() else None, "rows": rows})

        schema = (_DIR / _SCHEMA).read_text(encoding="utf-8")
        steps = []
        for chunk in re.split(r";\s*\n\s*\n", schema):
            m = re.search(r"CREATE OR REPLACE (TABLE|VIEW) (\w+)", chunk)
            if not m:
                continue
            body = chunk[chunk.rfind("\n\n") + 2:] if "\n\n" in chunk[:m.start()] else chunk  # retire l'en-tête du fichier
            desc, code = _lead_comments(body)
            steps.append({"name": m.group(2), "kind": m.group(1).lower(), "description": desc, "sql": code.rstrip(";") + ";"})

        queries = []
        for name, sql in _load_queries("territory_queries.sql").items():
            desc, code = _lead_comments(sql)
            queries.append({"name": name, "description": desc, "sql": code})
        queries.append({"name": "pair", "description": "Nuage de points + régression (dynamique : colonnes {x}, {y} "
                        "validées contre une liste blanche avant formatage)", "sql": PAIR_SQL})

        tables = [{"name": r["table_name"], "kind": r["table_type"], "rows": self.db.rows(f'SELECT COUNT(*) AS n FROM "{r["table_name"]}"')[0]["n"]}
                  for r in self.db.rows("SELECT table_name, table_type FROM information_schema.tables "
                                        "WHERE table_name LIKE 'od\\_%' ESCAPE '\\' OR table_name IN ('v_commune_features', 'v_station_normales') ORDER BY table_name")]
        quality = self._quality_profile(sources)
        counts = {t["name"]: t["rows"] for t in tables}
        for s in sources:
            s["table"] = _TARGET.get(s["name"])
            s["table_rows"] = counts.get(s["table"])
        return {"sources": sources, "steps": steps, "queries": queries, "tables": tables, "quality": quality,
                "rust": rust_engine.sources()}

    def _quality_profile(self, sources: list[dict]) -> list[dict] | None:
        """Profil qualité des fichiers bruts par le binaire Rust, mis en cache tant que les fichiers ne changent pas."""
        if not rust_engine.available():
            return None
        files = [self.raw_dir / Path(s["file"]).name for s in sources if (self.raw_dir / Path(s["file"]).name).exists()]
        cache = self.raw_dir / "_profil_qualite_rust.json"
        if cache.exists() and cache.stat().st_mtime > max(f.stat().st_mtime for f in files):
            return json.loads(cache.read_text(encoding="utf-8"))
        result = json.loads(rust_engine.run_datakit(["profile", *map(str, files)]))
        cache.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
        return result
