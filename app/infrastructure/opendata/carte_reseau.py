"""Carte du réseau 63 kV et des centrales de La Réunion, en SVG statique.

Sources : OpenStreetMap (lignes et postes 63 kV, centrales, via l'API Overpass) et geo.api.gouv.fr
(contours des communes). Le résultat est un fragment HTML inclus par la page Énergie : la carte
s'affiche sans script, et les cases de la légende filtrent les couches en CSS.

    python -m app.infrastructure.opendata.carte_reseau
"""
import json
import math
import re
import urllib.parse
import urllib.request
from datetime import date
from html import escape
from pathlib import Path

SORTIE = Path(__file__).resolve().parents[2] / "presentation" / "web" / "templates" / "partials" / "carte_reseau.html"
_AGENT = {"User-Agent": "opendata-fetch/1.0"}
OVERPASS = ["https://overpass-api.de/api/interpreter", "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
            "https://overpass.kumi.systems/api/interpreter"]
REQUETE = """[out:json][timeout:120];area["ISO3166-1"="RE"]->.a;
(way["power"="line"](area.a);way["power"="cable"]["voltage"](area.a);nwr["power"="plant"](area.a);
 nwr["power"="substation"](area.a););out tags geom;"""
COMMUNES = "https://geo.api.gouv.fr/communes?codeDepartement=974&format=geojson&geometry=contour&fields=nom"

# Filières, dans l'ordre de la légende. Couleurs : celles des graphiques de la page (theme.css).
FILIERES = [("hydro", "Hydraulique", "--s1"), ("bioliquide", "Thermique (bioliquide, fioul)", "--s2"),
            ("biomasse", "Biomasse (bagasse, bois)", "--s3"), ("eolien", "Éolien", "--o1"),
            ("solaire", "Solaire au sol", "--s4")]

# Emprise et projection (équirectangulaire corrigée de la latitude : à l'échelle de l'île, l'écart est négligeable)
LON0, LON1, LAT0, LAT1 = 55.20, 55.85, -20.855, -21.405
W = 900
KX = W / (LON1 - LON0)
KY = KX / math.cos(math.radians(21.13))
H = round((LAT0 - LAT1) * KY)


def _get(url: str, data: bytes | None = None) -> dict:
    with urllib.request.urlopen(urllib.request.Request(url, data=data, headers=_AGENT), timeout=180) as r:
        return json.loads(r.read())


def _osm() -> list[dict]:
    corps = urllib.parse.urlencode({"data": REQUETE}).encode()
    for url in OVERPASS * 2:  # le serveur principal est souvent saturé : on essaie les miroirs, deux tours
        try:
            return _get(url, corps)["elements"]
        except Exception:
            continue
    raise RuntimeError("aucun serveur Overpass n'a répondu")


def _xy(lat: float, lon: float) -> tuple[float, float]:
    return round((lon - LON0) * KX, 1), round((LAT0 - lat) * KY, 1)


def _pts(coords, pas: float = 0.1) -> str:
    """Points SVG arrondis au pas donné (en pixels), sans doublons consécutifs."""
    out, prec = [], None
    for lat, lon in coords:
        x, y = _xy(lat, lon)
        p = (round(round(x / pas) * pas, 1), round(round(y / pas) * pas, 1))
        if p != prec:
            out.append(f"{p[0]:g},{p[1]:g}")
            prec = p
    return " ".join(out)


def _centre(e: dict) -> tuple[float, float]:
    if e["type"] == "node":
        return e["lat"], e["lon"]
    if "bounds" in e:
        b = e["bounds"]
        return (b["minlat"] + b["maxlat"]) / 2, (b["minlon"] + b["maxlon"]) / 2
    pts = e["geometry"]
    return sum(p["lat"] for p in pts) / len(pts), sum(p["lon"] for p in pts) / len(pts)


def _mw(v: str | None) -> float | None:
    m = re.match(r"([\d.]+)\s*MW", v or "")
    return float(m.group(1)) if m else None


def _filiere(t: dict) -> str:
    src, nom = t.get("plant:source"), t.get("name") or ""
    if src in ("solar", "wind", "hydro"):
        return {"solar": "solaire", "wind": "eolien", "hydro": "hydro"}[src]
    if "Gol" in nom or "Bois-Rouge" in nom:  # OSM les dit encore « charbon » : sorties du charbon en 2023-2024
        return "biomasse"
    return "bioliquide"  # Port-Est (moteurs), turbines de La Possession et de Saint-Pierre


def _nom(t: dict) -> str:
    nom = t.get("name") or "Parc photovoltaïque (sans nom dans OpenStreetMap)"
    return {"Centrale hydroélectrique de Sainte-Rose": "Centrale de la Rivière de l'Est (Sainte-Rose)",
            "Centrale thermique de la baie de la Possession": "Turbines à combustion de la baie de La Possession"}.get(nom, nom)


def construire(osm: list[dict], communes: dict) -> str:
    svg = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="Carte des lignes 63 kV, des postes sources et des centrales de La Réunion">',
           '<g class="cr-terre">']
    for f in communes["features"]:
        g = f["geometry"]
        for poly in (g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]):
            svg.append(f'<polygon points="{_pts(((y, x) for x, y in poly[0]), pas=1)}"><title>{escape(f["properties"]["nom"])}</title></polygon>')
    svg.append('</g><g class="cr-reseau">')

    postes, centrales = [], []
    for e in osm:
        t = e["tags"]
        p, tension = t.get("power"), t.get("voltage") or ""
        if p in ("line", "cable") and "63000" in tension:
            svg.append(f'<polyline class="cr-ligne{" cr-sout" if p == "cable" else ""}" points="{_pts((q["lat"], q["lon"]) for q in e["geometry"])}"/>')
        elif p == "substation" and "63000" in tension:
            postes.append((t.get("name") or "Poste 63 kV", _xy(*_centre(e))))
        elif p == "plant":
            lat, lon = _centre(e)
            if _nom(t).startswith("Turbines à combustion"):
                lat -= 0.004  # même site que Port-Est : léger décalage pour que les deux points restent visibles
            centrales.append((_filiere(t), _nom(t), _mw(t.get("plant:output:electricity")), t.get("operator") or "", _xy(lat, lon)))
    svg.append("</g>")

    total = {}
    for code, libelle, _ in FILIERES:
        svg.append(f'<g class="cr-c-{code}">')
        total[code] = 0
        for _, nom, mw, op, (x, y) in sorted((c for c in centrales if c[0] == code), key=lambda c: -(c[2] or 0)):
            total[code] += mw or 0
            r = max(5, 2.4 * math.sqrt(mw)) if mw else 4.5
            puissance = f"{mw:g} MW".replace(".", ",") if mw else "puissance non renseignée"
            info = escape(f"{nom}\n{libelle} · {puissance}" + (f" · {op}" if op else ""))
            svg.append(f'<circle class="cr-ctr" style="fill:var({dict((c, v) for c, _, v in FILIERES)[code]})" cx="{x}" cy="{y}" r="{r:.1f}"><title>{info}</title></circle>')
        svg.append("</g>")
    svg.append('<g class="cr-reseau">')
    for nom, (x, y) in postes:
        svg.append(f'<rect class="cr-poste" x="{x - 4:.1f}" y="{y - 4:.1f}" width="8" height="8"><title>{escape(nom)} · poste source 63 kV</title></rect>')
    svg.append("</g></svg>")

    filtres = "\n".join(
        f'<label class="cr-filtre"><input type="checkbox" class="cr-f-{c}" checked><span class="cr-pastille" style="background:var({v})"></span>'
        f'<span>{l}</span><span class="cr-mw">{round(total[c])} MW</span></label>' for c, l, v in FILIERES)
    masquer = ",\n".join(f".cr-carte:has(.cr-f-{c}:not(:checked)) .cr-c-{c}" for c, _, _ in FILIERES)

    return f"""{{# Généré par app/infrastructure/opendata/carte_reseau.py le {date.today():%d/%m/%Y} : ne pas modifier à la main. #}}
<style>
.cr-carte {{ display: grid; grid-template-columns: minmax(0, 1fr) 260px; gap: 16px; align-items: start }}
@media (max-width: 860px) {{ .cr-carte {{ grid-template-columns: minmax(0, 1fr) }} }}
.cr-fond {{ background: var(--code-bg); border-radius: 8px; padding: 8px }}
.cr-fond svg {{ width: 100%; height: auto; display: block }}
.cr-terre polygon {{ fill: var(--surface-1); stroke: var(--axis); stroke-width: .6 }}
.cr-ligne {{ stroke: var(--text-primary); stroke-width: 2; fill: none; stroke-linejoin: round }}
.cr-sout {{ stroke-dasharray: 4 4; stroke-width: 1.6 }}
.cr-poste {{ fill: var(--surface-1); stroke: var(--text-primary); stroke-width: 1.5 }}
.cr-ctr {{ stroke: var(--surface-1); stroke-width: 1.2; fill-opacity: .9; cursor: help }}
.cr-ctr:hover {{ stroke: var(--text-primary); stroke-width: 2 }}
.cr-legende {{ display: grid; gap: 14px; font-size: 13px }}
.cr-legende h4 {{ font-size: 12px; font-weight: 600; letter-spacing: .06em; text-transform: uppercase; color: var(--muted); margin-bottom: 4px }}
.cr-filtre {{ display: grid; grid-template-columns: 16px 12px 1fr auto; align-items: center; gap: 8px; padding: 2px 0; cursor: pointer }}
.cr-pastille {{ width: 12px; height: 12px; border-radius: 50% }}
.cr-mw {{ color: var(--muted); font-variant-numeric: tabular-nums }}
.cr-sym {{ display: grid; grid-template-columns: 30px 1fr; gap: 8px; align-items: center; padding: 1px 0 }}
.cr-sym svg {{ overflow: visible }}
{masquer},
.cr-carte:has(.cr-f-reseau:not(:checked)) .cr-reseau {{ display: none }}
</style>
<div class="cr-carte">
  <div class="cr-fond">
{chr(10).join(svg)}
  </div>
  <div class="cr-legende">
    <div><h4>Centrales</h4>
{filtres}
    </div>
    <div><h4>Réseau</h4>
      <div class="cr-sym"><svg width="30" height="8" aria-hidden="true"><line x1="0" y1="4" x2="30" y2="4" class="cr-ligne"/></svg><span>Ligne 63 kV aérienne</span></div>
      <div class="cr-sym"><svg width="30" height="8" aria-hidden="true"><line x1="0" y1="4" x2="30" y2="4" class="cr-ligne cr-sout"/></svg><span>Ligne 63 kV souterraine</span></div>
      <div class="cr-sym"><svg width="30" height="12" aria-hidden="true"><rect x="10" y="1" width="10" height="10" class="cr-poste"/></svg><span>Poste source 63 kV</span></div>
      <label class="cr-filtre" style="grid-template-columns:16px 1fr"><input type="checkbox" class="cr-f-reseau" checked><span>Afficher le réseau</span></label>
    </div>
    <p class="muted">Survolez un point pour voir le nom de la centrale et sa puissance. Sources : contributeurs OpenStreetMap (ODbL),
      extraits le {date.today():%d/%m/%Y} ; contours des communes : geo.api.gouv.fr.</p>
  </div>
</div>
"""


def main() -> None:
    html = construire(_osm(), _get(COMMUNES))
    SORTIE.write_text(html, encoding="utf-8")
    print(f"{SORTIE} : {len(html) // 1024} Ko")


if __name__ == "__main__":
    main()
