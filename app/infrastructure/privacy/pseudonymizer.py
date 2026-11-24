"""Moteur de pseudonymisation LOCAL et déterministe.

alias = PRÉFIXE_ + HMAC-SHA256(clé locale, type|valeur normalisée)[:4..16]
- déterministe : même valeur -> même alias (l'IA peut raisonner sur les récurrences) ;
- non réversible sans la clé ni la table `privacy_map` (qui restent en local) ;
- détection = dictionnaire des entités connues (BDD) + regex (plaques, tél., adresses, ...).

Ce module respecte le port `Anonymizer` : on peut le remplacer par un binaire Rust
sans toucher au reste.
"""
import hashlib
import hmac
import re

from app.domain.models import Anonymized, Entity, Kind
from app.domain.ports import EntityCatalog, MappingStore

COMMUNES = ["Saint-Denis", "Sainte-Marie", "Sainte-Suzanne", "Saint-André", "Bras-Panon",
            "Saint-Benoît", "Sainte-Rose", "Plaine-des-Palmistes", "Saint-Pierre", "Saint-Louis",
            "Saint-Paul", "Le Port", "La Possession", "Saint-Leu", "Les Avirons", "L'Étang-Salé",
            "Saint-Joseph", "Petite-Île", "Le Tampon", "Entre-Deux", "Cilaos", "Salazie",
            "Trois-Bassins", "Saint-Philippe"]

_PATTERNS: list[tuple[Kind, re.Pattern]] = [(k, re.compile(p, re.I)) for k, p in [
    (Kind.MAIL, r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+"),
    (Kind.TEL, r"(?<!\w)(?:\+262\s?|0)[26]\d{2}(?:[ .]?\d{2}){3}(?!\d)"),
    (Kind.ACTIF, r"\b[A-Z]{2}-\d{3}-[A-Z]{2}\b"),            # plaque AB-123-CD
    (Kind.ACTIF, r"\bSN-[A-Z]{2}-\d{4,}\b"),                  # numéro de série
    (Kind.REF, r"\b(?:OT|BC|DOS)-\d{3,}\b"),                  # références internes
    (Kind.LIEU, r"\b\d{1,3}(?:\s?bis)?\s+(?:rue|chemin|route|avenue|impasse|allée|boulevard)\s+[^,.;\n]{3,45}"),
    (Kind.LIEU, r"(?<!\w)(?:" + "|".join(map(re.escape, COMMUNES)) + r")(?!\w)"),
]]
_ALIAS_RE = re.compile(r"\b(?:" + "|".join(k.value for k in Kind) + r")_[0-9A-F]{4,16}\b")


def _norm(s: str) -> str:
    return " ".join(s.split()).casefold()


class Pseudonymizer:
    engine = "Python"

    def __init__(self, store: MappingStore, catalog: EntityCatalog, secret: bytes):
        self.store, self.catalog, self._key = store, catalog, secret
        self._cache: dict[tuple[Kind, str], str] = {}

    def _alias(self, kind: Kind, original: str, digest: str | None = None) -> str:
        """Choisit l'alias à partir de l'empreinte HMAC (calculée ici, ou fournie par le moteur Rust)."""
        key = (kind, _norm(original))
        if key in self._cache:
            return self._cache[key]
        digest = digest or hmac.new(self._key, f"{kind.value}|{key[1]}".encode(), hashlib.sha256).hexdigest().upper()
        for n in range(4, 17):  # allonge l'alias en cas (rare) de collision
            alias = f"{kind.value}_{digest[:n]}"
            known = self.store.original(alias)
            if known is None:
                self.store.put(alias, kind.value, original)
            elif _norm(known) != key[1]:
                continue
            self._cache[key] = alias
            return alias
        raise RuntimeError("collision d'alias irrécupérable")

    def _spans(self, text: str) -> list[tuple[int, int, Kind, str]]:
        spans: list[tuple[int, int, Kind, str]] = []
        ents: list[Entity] = sorted(self.catalog.entities(), key=lambda e: -len(e.value))
        if ents:
            canon = {_norm(e.value): e for e in ents}
            rx = re.compile(r"(?<!\w)(?:" + "|".join(re.escape(e.value) for e in ents) + r")(?!\w)", re.I)
            for m in rx.finditer(text):
                e = canon[_norm(m.group())]
                spans.append((m.start(), m.end(), e.kind, e.value))
        for kind, rx in _PATTERNS:
            spans += [(m.start(), m.end(), kind, " ".join(m.group().split())) for m in rx.finditer(text)]
        spans.sort(key=lambda s: (s[0], -(s[1] - s[0])))
        kept, last_end = [], 0
        for s in spans:  # résolution des chevauchements : le plus long à gauche gagne
            if s[0] >= last_end:
                kept.append(s)
                last_end = s[1]
        return kept

    def anonymize(self, text: str) -> Anonymized:
        out, pos, used = [], 0, {}
        for start, end, kind, original in self._spans(text):
            alias = self._alias(kind, original)
            used[alias] = original
            out += [text[pos:start], alias]
            pos = end
        out.append(text[pos:])
        return Anonymized("".join(out), used)

    def restore(self, text: str) -> str:
        return _ALIAS_RE.sub(lambda m: self.store.original(m.group()) or m.group(), text)
