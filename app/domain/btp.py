"""BTP à La Réunion : familles de travaux, tranches de montant et types d'acheteurs publics (pur, sans I/O)."""

# Familles de travaux, lues sur les 4 premiers chiffres du code CPV (division 45 = travaux de construction).
# Ordre = ordre d'affichage. Le code générique 45000000 (« travaux de construction ») est gardé à part : il ne dit rien.
FAMILLES: list[tuple[str, str, tuple[str, ...]]] = [
    ("batiment", "Bâtiment, couverture, charpente", ("4520", "4521", "4525", "4526")),
    ("reseaux", "Routes, réseaux et génie civil", ("4522", "4523", "4524")),
    ("terrassement", "Terrassement et démolition", ("4510", "4511", "4512")),
    ("technique", "Électricité, plomberie, clim.", ("4530", "4531", "4532", "4533", "4534", "4535")),
    ("finitions", "Second œuvre et finitions", ("4540", "4541", "4542", "4543", "4544", "4545")),
    ("engins", "Engins avec conducteur", ("4550",)),
    ("generique", "Non précisé", ("4500",)),
]

# Tranches de montant notifié : (borne haute exclue en euros, libellé). La dernière n'a pas de borne.
TRANCHES: list[tuple[float | None, str]] = [
    (100_000, "Moins de 100 k€"),
    (1_000_000, "100 k€ à 1 M€"),
    (5_000_000, "1 à 5 M€"),
    (None, "Plus de 5 M€"),
]

# Au-delà, un « marché » est un contrat global de conception, réalisation et exploitation sur des années : un seul
# pèserait autant que des centaines de chantiers. Ils sont montrés à part et retirés des totaux et des classements.
HORS_NORME = 100_000_000

# Type d'acheteur, déduit de la catégorie juridique INSEE (répertoire SIRENE). Premier préfixe qui correspond.
TYPES_ACHETEUR: list[tuple[tuple[str, ...], str]] = [
    (("7210",), "Communes"),
    (("7220", "7225", "7229", "7230"), "Région et Département"),
    (("734", "735"), "Intercommunalités et syndicats"),
    (("736",), "Hôpitaux et action sociale"),
    (("71", "72", "73", "74", "4"), "État et autres établissements publics"),
    (("5", "6"), "SEM, SPL et bailleurs sociaux"),
]
AUTRE = "Autres ou inconnus"


def famille(cpv: str | None) -> str:
    code = (cpv or "")[:4]
    return next((f for f, _, prefixes in FAMILLES if code in prefixes), "generique")


def tranche(montant: float) -> str:
    return next(lib for borne, lib in TRANCHES if borne is None or montant < borne)


def type_acheteur(nature_juridique: str | None) -> str:
    nj = nature_juridique or ""
    return next((lib for prefixes, lib in TYPES_ACHETEUR if nj and nj.startswith(prefixes)), AUTRE)


def implantation(code_postal: str | None) -> str:
    """Où est l'établissement qui a signé le marché : sur l'île, ou ailleurs (siège ou agence hors de La Réunion)."""
    if not code_postal:
        return "Inconnue"
    return "À La Réunion" if code_postal.startswith("974") else "Hors de La Réunion"
