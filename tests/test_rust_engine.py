"""Test croisé : le moteur Rust doit produire exactement le même résultat que le moteur Python."""
import json

import pytest

from app.domain.models import Entity, Kind
from app.infrastructure.privacy import rust_engine
from app.infrastructure.privacy.pseudonymizer import Pseudonymizer

pytestmark = pytest.mark.skipif(not rust_engine.available(), reason="binaire Rust non compilé")

TEXTS = [
    "OT-4999 — Transports Payet Express. Camion FG-482-RT (série SN-RU-48213) au 12 chemin des Lataniers, "
    "Le Port. Contact 0262 42 18 07 ou jean@payet.re. Fuite injecteur à 85 000 km.",
    "Réunion à Saint-Pierre puis L'Étang-Salé, rappeler le +262 692 11 47 23. Réf. BC-20931, DOS-118.",
    "transports payet express a livré ab-123-cd au 3 bis rue Marius et Ary Leblond ; RAS à Saint-Denis.",
    "Aucun identifiant ici : 85 000 km, fuite d'huile, pression 2,4 bars.",
]


class MemStore:
    def __init__(self): self.d = {}
    def original(self, a): return self.d.get(a, (None, None))[1]
    def put(self, a, k, o): self.d[a] = (k, o)
    def all(self): return []


class Cat:
    def entities(self):
        return [Entity(Kind.CLIENT, "Transports Payet Express"), Entity(Kind.LIEU, "Dépôt Le Port")]


@pytest.mark.parametrize("text", TEXTS)
def test_rust_matches_python(text):
    py = Pseudonymizer(MemStore(), Cat(), b"k" * 32).anonymize(text)
    rs = rust_engine.RustPseudonymizer(MemStore(), Cat(), b"k" * 32).anonymize(text)
    assert rs.text == py.text and rs.used == py.used


def test_rust_roundtrip():
    eng = rust_engine.RustPseudonymizer(MemStore(), Cat(), b"k" * 32)
    a = eng.anonymize(TEXTS[0])
    assert "Payet" not in a.text and eng.restore(a.text) == TEXTS[0]


def test_profiler_reads_csv_and_gzip(tmp_path):
    import gzip
    (tmp_path / "a.csv").write_text("x;y;d\n1;a;2024-01-01\n2;;2024-01-02\n3.5;b;\n", encoding="utf-8")
    with gzip.open(tmp_path / "b.csv.gz", "wt", encoding="utf-8") as f:
        f.write("n\n1\n2\n")
    a, b = json.loads(rust_engine.run_datakit(["profile", str(tmp_path / "a.csv"), str(tmp_path / "b.csv.gz")]))
    cols = {c["name"]: c for c in a["column_profiles"]}
    assert a["rows"] == 3 and cols["x"]["inferred_type"] == "décimal" and cols["x"]["max"] == 3.5
    assert cols["y"]["null_pct"] == 33.3 and cols["d"]["inferred_type"] == "date"
    assert b["rows"] == 2 and b["column_profiles"][0]["inferred_type"] == "entier"
