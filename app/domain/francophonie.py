"""Référentiel de la page Francophonie canadienne : géographies des recensements, en français."""

# Libellé Statistique Canada → (code, nom français, type). Les tableaux historiques mélangent provinces, territoires
# et agrégats ; « Territoires du Nord-Ouest y compris Nunavut » couvre les recensements d'avant la création du Nunavut (1999).
GEOS: dict[str, tuple[str, str, str]] = {
    "Canada": ("CA", "Canada", "agrégat"),
    "Canada outside Quebec": ("HQ", "Canada hors Québec", "agrégat"),
    "Newfoundland and Labrador": ("NL", "Terre-Neuve-et-Labrador", "province"),
    "Prince Edward Island": ("PE", "Île-du-Prince-Édouard", "province"),
    "Nova Scotia": ("NS", "Nouvelle-Écosse", "province"),
    "New Brunswick": ("NB", "Nouveau-Brunswick", "province"),
    "Quebec": ("QC", "Québec", "province"),
    "Ontario": ("ON", "Ontario", "province"),
    "Manitoba": ("MB", "Manitoba", "province"),
    "Saskatchewan": ("SK", "Saskatchewan", "province"),
    "Alberta": ("AB", "Alberta", "province"),
    "British Columbia": ("BC", "Colombie-Britannique", "province"),
    "Yukon": ("YT", "Yukon", "territoire"),
    "Northwest Territories": ("NT", "Territoires du Nord-Ouest", "territoire"),
    "Nunavut": ("NU", "Nunavut", "territoire"),
    "Northwest Territories including Nunavut": ("NTNU", "T.N.-O. avec Nunavut (avant 1999)", "territoire"),
}

# Provinces où vivre en français hors Québec : l'ordre d'affichage par défaut du sélecteur
PROVINCES_HQ = ["NB", "ON", "MB", "NS", "AB", "BC", "PE", "SK", "NL"]


def continuity_label(ratio: float | None) -> str:
    """Indice de continuité linguistique : part des personnes de langue maternelle française
    qui parlent encore surtout le français à la maison."""
    if ratio is None:
        return "inconnu"
    if ratio >= 0.85:
        return "le français se transmet"
    if ratio >= 0.6:
        return "transmission fragile"
    return "l'anglais l'emporte à la maison"


# Villes comparées pour s'installer : chaque source publie ses propres libellés géographiques, et certaines ne
# descendent pas à la ville (revenu de Moncton, Halifax et Sudbury : valeur provinciale ; seuil MPC de Sudbury :
# « Ontario, 100 000 à 499 999 habitants »). Le niveau réellement utilisé est affiché à côté de chaque valeur.
# Colonnes : code, nom, province, MPC, loyer, revenu, criminalité, chômage, ville IRCC, ville du recensement 2021
VILLES: list[tuple[str, ...]] = [
    ("MON", "Moncton", "NB", "Moncton, New Brunswick", "Moncton, New Brunswick", "New Brunswick",
     "Moncton, New Brunswick [13305]", "Moncton, New Brunswick", "Moncton", "Moncton (CMA), N.B."),
    ("HAL", "Halifax", "NS", "Halifax, Nova Scotia", "Halifax, Nova Scotia", "Nova Scotia",
     "Halifax, Nova Scotia [12205]", "Halifax, Nova Scotia", "Halifax", "Halifax (CMA), N.S."),
    ("OTT", "Ottawa", "ON", "Ottawa-Gatineau, Ontario part, Ontario/Quebec", "Ottawa-Gatineau, Ontario part, Ontario/Quebec",
     "Ottawa-Gatineau, Ontario/Quebec", "Ottawa-Gatineau, Ontario part [35505]",
     "Ottawa-Gatineau, Ontario part, Ontario/Quebec", "Ottawa - Gatineau (Ontario part)", "Ottawa - Gatineau (Ontario part) (CMA), Ont."),
    ("SUD", "Grand Sudbury", "ON", "Ontario, population 100,000 to 499,999", "Greater Sudbury, Ontario", "Ontario",
     "Greater Sudbury, Ontario [35580]", "Greater Sudbury, Ontario", "Greater Sudbury", "Greater Sudbury (CMA), Ont."),
    ("TOR", "Toronto", "ON", "Toronto, Ontario", "Toronto, Ontario", "Toronto, Ontario",
     "Toronto, Ontario [35535]", "Toronto, Ontario", "Toronto", "Toronto (CMA), Ont."),
    ("WIN", "Winnipeg", "MB", "Winnipeg, Manitoba", "Winnipeg, Manitoba", "Winnipeg, Manitoba",
     "Winnipeg, Manitoba [46602]", "Winnipeg, Manitoba", "Winnipeg", "Winnipeg (CMA), Man."),
    ("EDM", "Edmonton", "AB", "Edmonton, Alberta", "Edmonton, Alberta", "Edmonton, Alberta",
     "Edmonton, Alberta [48835]", "Edmonton, Alberta", "Edmonton", "Edmonton (CMA), Alta."),
    ("CAL", "Calgary", "AB", "Calgary, Alberta", "Calgary, Alberta", "Calgary, Alberta",
     "Calgary, Alberta [48825]", "Calgary, Alberta", "Calgary", "Calgary (CMA), Alta."),
    ("VAN", "Vancouver", "BC", "Vancouver, British Columbia", "Vancouver, British Columbia", "Vancouver, British Columbia",
     "Vancouver, British Columbia [59933]", "Vancouver, British Columbia", "Vancouver", "Vancouver (CMA), B.C."),
]

# Les quatre piliers du comparatif et leurs indicateurs : (colonne, libellé, sens) — sens +1 = plus c'est haut, mieux c'est
PILIERS: dict[str, list[tuple[str, str, int]]] = {
    "Francophonie": [("plop_fr_pct", "Francophones dans la ville (%)", 1),
                     ("maison_fr_pct", "Francophones qui parlent surtout français à la maison (%)", 1),
                     ("enfants_fr_pct", "Enfants de 0 à 14 ans francophones (%)", 1),
                     ("part_fr_arrivees", "Francophones parmi les nouveaux résidents permanents (%)", 1)],
    "Coût de la vie": [("loyer", "Loyer moyen, 2 chambres ($/mois)", -1),
                       ("mpc", "Coût du panier de base, famille de 4 ($/an)", -1),
                       ("pouvoir_achat", "Revenu des couples avec enfants ÷ panier de base", 1)],
    "Emploi": [("chomage", "Taux de chômage (%)", -1),
               ("revenu", "Revenu médian après impôt, couples avec enfants ($)", 1)],
    "Cadre de vie": [("criminalite", "Indice de gravité de la criminalité", -1),
                     ("satisfaction", "Très satisfaits de leur vie, province (%)", 1)],
}

# Cibles d'admissions francophones hors Québec (% des résidents permanents admis hors Québec), plans des niveaux
# d'immigration 2024-2026 et 2026-2028 (IRCC). Ce sont des objectifs politiques, pas des données : saisis ici, à la main.
CIBLES_IRCC: dict[int, float] = {2024: 6.0, 2025: 8.5, 2026: 9.0, 2027: 9.5, 2028: 10.5}
