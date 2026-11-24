"""Modèles métier purs : aucune dépendance technique."""
from dataclasses import dataclass, field
from datetime import date
from enum import Enum


class Kind(str, Enum):
    """Type d'entité sensible ; la valeur sert de préfixe d'alias (ex. ACTIF_8F2A)."""
    ACTIF = "ACTIF"
    LIEU = "LIEU"
    CLIENT = "CLIENT"
    TEL = "TEL"
    MAIL = "MAIL"
    REF = "REF"


@dataclass(frozen=True)
class Entity:
    kind: Kind
    value: str


@dataclass(frozen=True)
class Anonymized:
    text: str
    used: dict[str, str]  # alias -> valeur réelle (LOCAL uniquement, jamais envoyé)


@dataclass(frozen=True)
class RiskRow:
    id: int
    label: str
    plate: str
    client: str
    commune: str
    km_current: int
    failures_12m: int
    cost_12m: float
    downtime_12m: float
    drift_ratio: float | None
    risk_score: int


@dataclass(frozen=True)
class SupplyAlert:
    asset_id: int
    label: str
    plate: str
    part_ref: str
    part_label: str
    due_km: int
    due_date: date
    stock_qty: int
    demand_rank: int
    days_left_to_order: int
    status: str


@dataclass(frozen=True)
class Analysis:
    raw_input: str
    payload: str          # ce que l'IA reçoit réellement
    system_prompt: str
    ai_response: str      # réponse brute (alias)
    final: str            # réponse réidentifiée (affichage local)
    used: dict[str, str] = field(default_factory=dict)
    engine: str = "Python"  # moteur de pseudonymisation utilisé (Rust natif ou Python)
