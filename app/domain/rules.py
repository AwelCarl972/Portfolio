"""Règles métier pures (testables sans base ni réseau)."""


def risk_level(score: int) -> str:
    if score >= 70:
        return "CRITIQUE"
    if score >= 45:
        return "ÉLEVÉ"
    if score >= 25:
        return "À SURVEILLER"
    return "OK"


_STATUS = {
    "COUVERT_STOCK": ("Couvert par le stock", "ok"),
    "COMMANDER_MER": ("Commander (fret maritime OK)", "warn"),
    "COMMANDER_AIR": ("Commander en AÉRIEN (mer trop lent)", "bad"),
    "RUPTURE_PROBABLE": ("Rupture probable (même en aérien)", "crit"),
}


def status_label(status: str) -> tuple[str, str]:
    return _STATUS.get(status, (status, "ok"))
