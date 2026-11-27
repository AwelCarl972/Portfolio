"""Ventes de logements à La Réunion (DVF géolocalisée, 2021-2025) pour la carte des prix au m².

Une ligne par vente d'un seul logement (maison ou appartement), avec ce qui l'accompagne : dépendance
(garage, parking, cave), surface de terrain, neuf ou ancien. Les ventes sont rattachées à leur commune et
à un hexagone d'environ 2 km de large ; les coordonnées et les adresses ne sont pas publiées.
Le résultat est un JSON en colonnes, lu par static/immo.js.

    python -m app.infrastructure.opendata.dvf_carte
"""
import json
import math
import urllib.request
from datetime import date
from pathlib import Path

import duckdb

RACINE = Path(__file__).resolve().parents[3]
BRUT = RACINE / "data" / "raw" / "dvf_geo"
SORTIE = RACINE / "app" / "presentation" / "web" / "static" / "immo" / "ventes.json"
ANNEES = range(2021, 2026)
URL = "https://files.data.gouv.fr/geo-dvf/latest/csv/{a}/departements/974.csv.gz"
COMMUNES = "https://geo.api.gouv.fr/communes?codeDepartement=974&format=geojson&geometry=contour&fields=nom"
_AGENT = {"User-Agent": "opendata-fetch/1.0"}

# Même projection que la carte du réseau électrique : équirectangulaire corrigée de la latitude
LON0, LON1, LAT0, LAT1 = 55.20, 55.85, -20.855, -21.405
W = 900
KX = W / (LON1 - LON0)
KY = KX / math.cos(math.radians(21.13))
H = round((LAT0 - LAT1) * KY)
HEX = 1.15 * KX / (111.32 * math.cos(math.radians(21.13)))  # rayon d'un hexagone : 1,15 km, en pixels

VENTES = """
WITH r AS (
    SELECT * FROM read_csv('{brut}/*.csv.gz', all_varchar = true)
    WHERE nature_mutation IN ('Vente', 'Vente en l''état futur d''achèvement')
),
mut AS (
    SELECT id_mutation,
        any_value(nature_mutation) <> 'Vente'                                       AS neuf,
        year(min(date_mutation::DATE))                                              AS annee,
        max(valeur_fonciere::DOUBLE)                                                AS prix,
        count(DISTINCT code_commune)                                                AS n_communes,
        any_value(code_commune)                                                     AS code_insee,
        count(DISTINCT CASE WHEN type_local IN ('Maison', 'Appartement')
              THEN concat_ws('|', id_parcelle, lot1_numero, type_local, surface_reelle_bati) END) AS n_logements,
        bool_or(type_local LIKE 'Local%')                                           AS local_pro,
        bool_or(type_local = 'Dépendance')                                          AS dependance,
        max(CASE WHEN type_local IN ('Maison', 'Appartement') THEN type_local END) AS type_local,
        max(CASE WHEN type_local IN ('Maison', 'Appartement') THEN surface_reelle_bati::DOUBLE END) AS surface,
        max(CASE WHEN type_local IN ('Maison', 'Appartement') THEN nombre_pieces_principales::INT END) AS pieces,
        avg(CASE WHEN type_local IN ('Maison', 'Appartement') THEN longitude::DOUBLE END) AS lon,
        avg(CASE WHEN type_local IN ('Maison', 'Appartement') THEN latitude::DOUBLE END)  AS lat
    FROM r GROUP BY id_mutation
),
-- Terrain : une ligne DVF par parcelle × nature de culture × local ; on dédoublonne avant de sommer
terrain AS (
    SELECT id_mutation, sum(surface) AS terrain
    FROM (SELECT DISTINCT id_mutation, id_parcelle, code_nature_culture, surface_terrain::DOUBLE AS surface
          FROM r WHERE surface_terrain IS NOT NULL)
    GROUP BY id_mutation
)
SELECT m.code_insee, m.lon, m.lat, m.annee, m.neuf, m.dependance,
       m.type_local = 'Appartement' AS appartement,
       least(greatest(m.pieces, 1), 5) AS pieces,
       round(m.surface)::INT AS surface,
       round(m.prix / m.surface)::INT AS prix_m2,
       CASE WHEN m.type_local = 'Appartement' THEN NULL
            WHEN coalesce(t.terrain, 0) < 300 THEN 0
            WHEN t.terrain < 600 THEN 1 ELSE 2 END AS terrain
FROM mut m LEFT JOIN terrain t USING (id_mutation)
WHERE m.n_logements = 1 AND m.n_communes = 1 AND NOT m.local_pro
  AND m.surface BETWEEN 15 AND 400 AND m.pieces >= 1
  AND m.prix / m.surface BETWEEN 500 AND 12000          -- mêmes bornes que l'Observatoire (valeurs aberrantes)
"""


def _get(url: str) -> bytes:
    with urllib.request.urlopen(urllib.request.Request(url, headers=_AGENT), timeout=180) as r:
        return r.read()


def telecharger() -> None:
    BRUT.mkdir(parents=True, exist_ok=True)
    for a in ANNEES:
        (BRUT / f"{a}.csv.gz").write_bytes(_get(URL.format(a=a)))


def _xy(lat: float, lon: float) -> tuple[float, float]:
    return (lon - LON0) * KX, (LAT0 - lat) * KY


def _hexagone(x: float, y: float) -> tuple[int, int]:
    """Coordonnées axiales (q, r) de l'hexagone « pointe en haut » qui contient le point."""
    q = (math.sqrt(3) / 3 * x - y / 3) / HEX
    r = (2 / 3 * y) / HEX
    cx, cz = q, r
    cy = -cx - cz
    rx, ry, rz = round(cx), round(cy), round(cz)
    dx, dy, dz = abs(rx - cx), abs(ry - cy), abs(rz - cz)
    if dx > dy and dx > dz:
        rx = -ry - rz
    elif dy <= dz:
        rz = -rx - ry
    return rx, rz


def _centre_hex(q: int, r: int) -> tuple[float, float]:
    return HEX * math.sqrt(3) * (q + r / 2), HEX * 1.5 * r


def construire() -> dict:
    lignes = duckdb.sql(VENTES.format(brut=BRUT.as_posix())).fetchall()
    geo = json.loads(_get(COMMUNES))
    communes = sorted(((f["properties"]["code"], f["properties"]["nom"], f["geometry"]) for f in geo["features"]),
                      key=lambda c: c[1])
    idx_commune = {code: i for i, (code, _, _) in enumerate(communes)}

    def chemin(g) -> str:
        polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
        morceaux = []
        for poly in polys:
            pts, prec = [], None
            for lon, lat in poly[0]:
                p = tuple(round(v) for v in _xy(lat, lon))
                if p != prec:
                    pts.append(f"{p[0]},{p[1]}")
                    prec = p
            morceaux.append("M" + "L".join(pts) + "Z")
        return "".join(morceaux)

    hexagones: dict[tuple[int, int], int] = {}
    col = {k: [] for k in "chtpsmdjna"}
    for code, lon, lat, annee, neuf, dep, appart, pieces, surface, prix_m2, terrain in lignes:
        if code not in idx_commune:
            continue
        h = -1
        if lon is not None and lat is not None:
            h = hexagones.setdefault(_hexagone(*_xy(lat, lon)), len(hexagones))
        for k, v in zip("chtpsmdjna", (idx_commune[code], h, int(appart), pieces, surface, prix_m2, int(dep),
                                        -1 if terrain is None else terrain, int(neuf), annee)):
            col[k].append(v)

    return {
        "maj": f"{date.today():%d/%m/%Y}",
        "vue": [W, H],
        "rayon_hex": round(HEX, 2),
        "communes": [{"nom": nom, "d": chemin(g)} for _, nom, g in communes],
        "hex": [[round(v, 1) for v in _centre_hex(q, r)] for (q, r) in sorted(hexagones, key=hexagones.get)],
        "ventes": col,
    }


def main() -> None:
    if not any(BRUT.glob("*.csv.gz")):
        telecharger()
    data = construire()
    SORTIE.parent.mkdir(parents=True, exist_ok=True)
    SORTIE.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"{len(data['ventes']['m'])} ventes, {len(data['hex'])} hexagones, {SORTIE.stat().st_size // 1024} Ko")


if __name__ == "__main__":
    main()
