"""Moteur de pseudonymisation natif (binaire Rust `datakit`), branché derrière le même port `Anonymizer`.

Répartition des rôles :
- Rust : détection des entités (dictionnaire + motifs) et empreinte HMAC-SHA256, en un seul passage ;
- Python : choix de la longueur d'alias (collisions) et persistance de la table de correspondance locale.

Le texte et la clé transitent par un tube (stdin/stdout) d'un processus local : rien ne quitte la machine.
"""
import json
import subprocess
from pathlib import Path

from app.domain.models import Anonymized, Kind

from .pseudonymizer import Pseudonymizer

ROOT = Path(__file__).resolve().parents[3]
BINARY = next((p for p in (ROOT / "rust/datakit/target/release/datakit.exe",
                           ROOT / "rust/datakit/target/release/datakit") if p.exists()), None)


def available() -> bool:
    return BINARY is not None


def sources() -> list[dict]:
    """Code source Rust, affiché tel quel dans l'onglet « Données & SQL »."""
    src = ROOT / "rust/datakit/src"
    return [{"file": f"rust/datakit/src/{n}", "code": (src / n).read_text(encoding="utf-8")}
            for n in ("profile.rs", "anonymize.rs", "main.rs") if (src / n).exists()]


def run_datakit(args: list[str], stdin: str | None = None, timeout: float = 120) -> str:
    if BINARY is None:
        raise RuntimeError("binaire datakit absent : cd rust/datakit && cargo build --release")
    r = subprocess.run([str(BINARY), *args], input=stdin, capture_output=True, text=True,
                       encoding="utf-8", timeout=timeout, check=False)
    if r.returncode:
        raise RuntimeError(r.stderr.strip() or f"datakit a échoué ({r.returncode})")
    return r.stdout


class RustPseudonymizer(Pseudonymizer):
    engine = "Rust"

    def anonymize(self, text: str) -> Anonymized:
        req = {"text": text, "key_hex": self._key.hex(),
               "catalog": [{"kind": e.kind.value, "value": e.value} for e in self.catalog.entities()]}
        out, used = [], {}
        for seg in json.loads(run_datakit(["anonymize"], json.dumps(req))):
            if "digest" not in seg:
                out.append(seg["text"])
                continue
            alias = self._alias(Kind(seg["kind"]), seg["original"], seg["digest"])
            used[alias] = seg["original"]
            out.append(alias)
        return Anonymized("".join(out), used)
