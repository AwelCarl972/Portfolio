"""Électricité de La Réunion : les filières telles qu'EDF les publie, et ce qui compte comme renouvelable."""

# (colonne du bilan annuel EDF, libellé, renouvelable ?) — ordre d'empilement des graphiques : le fossile en bas
FILIERES: list[tuple[str, str, bool]] = [
    ("charbon", "Charbon", False),
    ("moteurs_diesel", "Moteurs diesel (fioul)", False),
    ("turbines_a_combustion_fioul", "Turbines à combustion", False),
    ("bioenergie", "Bioénergies (bagasse, bois, biomasse liquide, biogaz)", True),
    ("hydraulique", "Hydraulique", True),
    ("solaire_photovoltaique", "Solaire photovoltaïque", True),
    ("eolien", "Éolien", True),
]

# Pas horaire : EDF regroupe autrement, et la frontière fossile / renouvelable y bouge en 2024 (voir les limites de la page)
FILIERES_HORAIRES: list[tuple[str, str]] = [
    ("thermique_mw", "Thermique (fioul puis biomasse liquide)"),
    ("bagasse_charbon_mw", "Bagasse / charbon"),
    ("hydraulique_mw", "Hydraulique"),
    ("photovoltaique_mw", "Solaire"),
    ("eolien_mw", "Éolien"),
    ("bioenergies_mw", "Biogaz"),
]

# EDF écrit les communes en capitales sans accents (« L ETANG SALE ») : on joint par code INSEE
COMMUNES: dict[str, str] = {
    "97401": "Les Avirons", "97402": "Bras-Panon", "97403": "Entre-Deux", "97404": "L'Étang-Salé",
    "97405": "Petite-Île", "97406": "La Plaine-des-Palmistes", "97407": "Le Port", "97408": "La Possession",
    "97409": "Saint-André", "97410": "Saint-Benoît", "97411": "Saint-Denis", "97412": "Saint-Joseph",
    "97413": "Saint-Leu", "97414": "Saint-Louis", "97415": "Saint-Paul", "97416": "Saint-Pierre",
    "97417": "Saint-Philippe", "97418": "Sainte-Marie", "97419": "Sainte-Rose", "97420": "Sainte-Suzanne",
    "97421": "Salazie", "97422": "Le Tampon", "97423": "Les Trois-Bassins", "97424": "Cilaos",
}
HAUTS = {"97424", "97421", "97406"}  # Cilaos, Salazie, La Plaine-des-Palmistes : bourgs en altitude, climat frais

# Saisons australes : l'été (chaud et humide, climatisation) n'est pas l'hiver de la métropole
SAISONS = {"Été austral (déc.-mars)": (12, 1, 2, 3), "Hiver austral (juin-sept.)": (6, 7, 8, 9)}


def renouvelable(colonne: str) -> bool:
    return next(r for c, _, r in FILIERES if c == colonne)
