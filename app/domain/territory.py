"""Référentiel territorial de La Réunion et règles d'interprétation (pur, sans I/O)."""

MICRO_REGIONS: dict[str, str] = {
    "97411": "Nord", "97418": "Nord", "97420": "Nord",
    "97402": "Est", "97406": "Est", "97409": "Est", "97410": "Est", "97419": "Est", "97421": "Est",
    "97407": "Ouest", "97408": "Ouest", "97413": "Ouest", "97415": "Ouest", "97423": "Ouest",
    "97401": "Sud", "97403": "Sud", "97404": "Sud", "97405": "Sud", "97412": "Sud", "97414": "Sud",
    "97416": "Sud", "97417": "Sud", "97422": "Sud", "97424": "Sud",
}
REGIONS = ["Nord", "Est", "Ouest", "Sud"]

# Indicateurs communaux exposés à l'analyse : colonne SQL -> (court, libellé, unité). Liste blanche.
INDICATORS: dict[str, tuple[str, str, str]] = {
    "prix_m2": ("Prix m²", "Prix médian au m² (2023-25)", "€/m²"),
    "evol_prix_pct": ("Évol. prix", "Évolution du prix au m² depuis 2016-18", "%"),
    "revenu_median": ("Revenu méd.", "Revenu disponible médian (2014)", "€/an"),
    "taux_pauvrete": ("Pauvreté", "Taux de pauvreté (2014)", "%"),
    "gini": ("Gini", "Indice de Gini (2014)", ""),
    "densite": ("Densité", "Densité de population (2016)", "hab/km²"),
    "croissance_pop_pct": ("Croiss. pop.", "Croissance démographique 2006-16", "%"),
    "chomeurs_pour_100hab": ("Chômage", "Demandeurs d'emploi pour 100 hab (2022)", ""),
    "logements_pour_1000hab": ("Construction", "Logements autorisés / an pour 1 000 hab", ""),
    "accidents_pour_1000hab": ("Accidents", "Accidents corporels / an pour 1 000 hab", ""),
}


# Cyclones marquants ayant touché La Réunion : (année, mois) -> nom. Sert à annoter les extrêmes.
CYCLONES: dict[tuple[int, int], str] = {
    (1966, 1): "Denise", (1980, 1): "Hyacinthe", (1987, 2): "Clotilda", (1989, 1): "Firinga",
    (2002, 1): "Dina", (2006, 3): "Diwa", (2007, 2): "Gamède", (2024, 1): "Belal", (2025, 2): "Garance",
}


def normalize_region(region: str | None) -> str:
    return region if region in REGIONS else "ALL"


def correlation_strength(r: float | None) -> str:
    if r is None:
        return "non calculable"
    a = abs(r)
    level = "forte" if a >= 0.7 else "modérée" if a >= 0.4 else "faible" if a >= 0.2 else "négligeable"
    sign = "positive" if r > 0 else "négative"
    return level if level == "négligeable" else f"{level} {sign}"
