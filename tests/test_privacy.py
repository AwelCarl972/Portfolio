import pytest

from app.application.use_cases.analyze_report import AnalyzeReport
from app.domain.models import Entity, Kind
from app.infrastructure.ai.llm import OfflineLLM
from app.infrastructure.privacy.pseudonymizer import Pseudonymizer
from app.infrastructure.seed import seed
from app.infrastructure.sql.repository import (Database, DuckEntityCatalog, DuckFleetRepository,
                                               DuckMappingStore)

TEXT = ("OT-4999 — Transports Payet Express. Camion FG-482-RT (série SN-RU-48213) au 12 chemin des "
        "Lataniers, Le Port. Contact 0262 42 18 07 ou jean@payet.re. Fuite injecteur à 85 000 km.")
SECRETS = ["Payet", "FG-482-RT", "SN-RU-48213", "Lataniers", "Le Port", "0262 42 18 07", "payet.re", "OT-4999"]


class MemStore:
    def __init__(self): self.d = {}
    def original(self, a): return self.d.get(a, (None, None))[1]
    def put(self, a, k, o): self.d[a] = (k, o)
    def all(self): return []


class Cat:
    def entities(self): return [Entity(Kind.CLIENT, "Transports Payet Express")]


@pytest.fixture
def anon():
    return Pseudonymizer(MemStore(), Cat(), b"k" * 32)


def test_no_sensitive_data_in_payload(anon):
    out = anon.anonymize(TEXT).text
    for s in SECRETS:
        assert s not in out
    assert "85 000 km" in out  # le contexte technique est conservé


def test_deterministic_and_roundtrip(anon):
    a, b = anon.anonymize(TEXT), anon.anonymize(TEXT)
    assert a.text == b.text
    assert anon.restore(a.text) == TEXT


def test_different_key_gives_different_aliases():
    a = Pseudonymizer(MemStore(), Cat(), b"a" * 32).anonymize(TEXT).text
    b = Pseudonymizer(MemStore(), Cat(), b"b" * 32).anonymize(TEXT).text
    assert a != b


def test_end_to_end_with_sql(tmp_path):
    db = Database(str(tmp_path / "t.duckdb"))
    seed(db)
    repo, store = DuckFleetRepository(db), DuckMappingStore(db)
    risks, alerts = repo.risk_ranking(), repo.supply_alerts()
    assert risks and risks[0].risk_score >= risks[-1].risk_score
    assert alerts
    uc = AnalyzeReport(repo, Pseudonymizer(store, DuckEntityCatalog(db), b"k" * 32), OfflineLLM())
    top = risks[0]
    res = uc(top.id, "")
    for secret in (top.plate, top.client):
        assert secret not in res.payload and secret not in res.ai_response
        assert secret in res.raw_input
    assert "ACTIF_" in res.final or top.plate in res.final
