"""Racine de composition : le seul endroit qui connaît les implémentations concrètes."""
import os
import secrets
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from app.application.use_cases.analyze_report import AnalyzeReport
from app.application.use_cases.fleet_overview import FleetOverview
from app.application.use_cases.francophonie import FrancophonieShowcase
from app.application.use_cases.projets import ProjetsShowcase
from app.application.use_cases.territory_dashboard import TerritoryDashboard
from app.infrastructure.ai.llm import build_llm
from app.infrastructure.privacy import rust_engine
from app.infrastructure.privacy.pseudonymizer import Pseudonymizer
from app.infrastructure.privacy.rust_engine import RustPseudonymizer
from app.infrastructure.seed import seed_if_empty
from app.infrastructure.sql.repository import (Database, DuckEntityCatalog, DuckFleetRepository,
                                               DuckMappingStore)
from app.infrastructure.sql.francophonie_repository import DuckFrancophonieRepository
from app.infrastructure.sql.projets_repository import DuckProjetsRepository
from app.infrastructure.sql.territory_repository import DuckTerritoryRepository


@dataclass
class Container:
    overview: FleetOverview
    analyze: AnalyzeReport
    store: DuckMappingStore
    territory: TerritoryDashboard
    projets: ProjetsShowcase
    francophonie: FrancophonieShowcase


def _secret(data_dir: Path) -> bytes:
    f = data_dir / ".privacy_key"
    if not f.exists():
        f.write_bytes(secrets.token_bytes(32))
    return f.read_bytes()


@lru_cache
def container() -> Container:
    db_path = Path(os.getenv("FLEET_DB", "data/fleet.duckdb"))
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db = Database(str(db_path))
    seed_if_empty(db)
    repo, store = DuckFleetRepository(db), DuckMappingStore(db)
    # Moteur natif Rust si le binaire est compilé (PRIVACY_ENGINE=python pour forcer le moteur Python)
    engine = RustPseudonymizer if rust_engine.available() and os.getenv("PRIVACY_ENGINE") != "python" else Pseudonymizer
    anonymizer = engine(store, DuckEntityCatalog(db), _secret(db_path.parent))
    territory = DuckTerritoryRepository(db, db_path.parent / "raw")
    territory.load()  # ~1 s : reconstruit les tables od_* depuis les CSV open data
    projets = DuckProjetsRepository(db, db_path.parent / "raw" / "projets")
    projets.load()  # tables pj_* : carte des bornes (Le Wagon) et optimisations MetaTrader
    francophonie = DuckFrancophonieRepository(db, db_path.parent / "raw")
    francophonie.load()  # tables fr_* : recensements canadiens 1951-2021 (Statistique Canada)
    return Container(FleetOverview(repo), AnalyzeReport(repo, anonymizer, build_llm()), store,
                     TerritoryDashboard(territory), ProjetsShowcase(projets), FrancophonieShowcase(francophonie))


def get_territory() -> TerritoryDashboard:
    return container().territory


def get_projets() -> ProjetsShowcase:
    return container().projets


def get_francophonie() -> FrancophonieShowcase:
    return container().francophonie


def get_overview() -> FleetOverview:
    return container().overview


def get_analyze() -> AnalyzeReport:
    return container().analyze


def get_store() -> DuckMappingStore:
    return container().store
