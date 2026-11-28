import logging
import os
import re
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

import duckdb
from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import HTMLResponse, PlainTextResponse, Response
from markupsafe import Markup, escape
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.application.use_cases.analyze_report import AnalyzeReport
from app.application.use_cases.btp import BtpShowcase
from app.application.use_cases.fleet_overview import FleetOverview
from app.application.use_cases.energie import EnergieShowcase
from app.application.use_cases.francophonie import FrancophonieShowcase
from app.application.use_cases.projets import ProjetsShowcase
from app.application.use_cases.territory_dashboard import TerritoryDashboard
from app.domain.rules import risk_level, status_label
from app.domain.territory import REGIONS

from .deps import get_analyze, get_btp, get_energie, get_francophonie, get_overview, get_projets, get_store, get_territory
from .quota import depuis_env

@asynccontextmanager
async def demarrage(_app):
    # Chargement des données et calcul des pages AVANT d'accepter des visiteurs : sans cela, le premier venu
    # après un déploiement attendait ~20 s. Le serveur ne répond qu'une fois prêt (le script de déploiement attend /sante).
    t0 = time.perf_counter()
    _prechauffer()
    logging.getLogger("uvicorn.error").info("Pages prêtes en %.1f s", time.perf_counter() - t0)
    yield


app = FastAPI(title="ParcInsulaire", lifespan=demarrage)
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")
_EXTRAITS = Path(__file__).parent / "extraits"  # code d'anciens projets, relu et sans secret


@app.exception_handler(duckdb.IOException)
def db_locked(request: Request, exc: duckdb.IOException):
    # DuckDB n'autorise qu'un processus écrivain par fichier : cas typique = deux serveurs lancés.
    return HTMLResponse("<h1>Base de données indisponible</h1><p>Le fichier DuckDB est verrouillé par un "
                        "autre processus (un second serveur uvicorn est-il lancé ?). Arrêtez-le puis rechargez."
                        f"</p><pre>{exc}</pre>", status_code=503)


# Version des fichiers statiques dans leur URL : sans elle, un navigateur garde l'ancien JS après une mise en ligne
_STATIC = Path(__file__).parent / "static"
templates.env.globals.update(risk_level=risk_level, status_label=status_label,
                             v=str(int(max(f.stat().st_mtime for f in _STATIC.iterdir()))))


@app.get("/cv", response_class=HTMLResponse)
def cv(request: Request):
    """Version publique du CV : sans téléphone, avec l'adresse du domaine (le site est lu par des robots)."""
    return templates.TemplateResponse(request, "cv.html", {})


# --- Robots : ce que les moteurs voient --------------------------------------------------------------------------
SITE = os.environ.get("SITE_URL", "https://axelclaude.fr").rstrip("/")
# Pages présentées aux recruteurs de La Réunion, dans l'ordre du menu
PAGES_PUBLIQUES = ["/", "/observatoire", "/energie", "/btp", "/parc", "/projets", "/cv"]
# Accessibles par lien direct, mais hors des moteurs : la version « Canada » du portfolio
HORS_MOTEURS = {"/francophonie", "/static/cv/CV-Axel-Claude-Data-Analyst-EN.pdf"}


@app.middleware("http")
async def consigne_robots(request: Request, call_next):
    reponse = await call_next(request)
    if request.url.path in HORS_MOTEURS:
        reponse.headers["X-Robots-Tag"] = "noindex"
    return reponse


@app.get("/robots.txt", response_class=PlainTextResponse)
def robots():
    # Les fragments HTMX, les données brutes et l'appel à l'IA ne sont pas des pages à référencer
    return ("User-agent: *\n"
            "Disallow: /analyze\n"
            "Disallow: /observatoire/panel\n"
            "Disallow: /observatoire/pair\n"
            "Disallow: /projets/donnees/\n"
            f"\nSitemap: {SITE}/sitemap.xml\n")


@app.get("/sitemap.xml")
def sitemap():
    urls = "".join(f"<url><loc>{SITE}{p}</loc></url>" for p in PAGES_PUBLIQUES)
    return Response('<?xml version="1.0" encoding="UTF-8"?>'
                    f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>',
                    media_type="application/xml")


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    # Les navigateurs demandent /favicon.ico d'office ; on sert la même icône que le <link rel="icon"> des pages
    return Response((_STATIC / "favicon.svg").read_bytes(), media_type="image/svg+xml",
                    headers={"Cache-Control": "public, max-age=604800"})


@app.get("/sante")
def sante():
    """Sonde du conteneur : ne charge rien, répond dès que le serveur écoute."""
    return {"ok": True}


@app.get("/", response_class=HTMLResponse)
def accueil(request: Request):
    """Page recruteur : qui, où, quoi, en 30 secondes, et un chiffre par analyse."""
    return templates.TemplateResponse(request, "accueil.html", {})


_ALIAS = re.compile(r"\b(?:ACTIF|LIEU|CLIENT|TEL|MAIL|REF)_[0-9A-Za-z]{2,16}\b")


def _surligner(texte: str) -> Markup:
    """Échappe le texte puis encadre les alias (ACTIF_3F2A…) : on voit d'un coup d'œil ce qui a été masqué."""
    return Markup(_ALIAS.sub(lambda m: f'<mark class="alias">{m.group(0)}</mark>', str(escape(texte))))


templates.env.filters["alias"] = _surligner


# Les données open data sont chargées une fois au démarrage et ne bougent plus : inutile de refaire les requêtes
# DuckDB à chaque visite (0,3 à 0,7 s par page). La clé inclut l'objet métier, pour qu'un test qui en injecte
# un autre ne reçoive pas les résultats d'un précédent.
_MEMO: dict = {}


def _une_fois(uc, *cle, calcul):
    k = (id(uc), *cle)
    if k not in _MEMO:
        _MEMO[k] = calcul()
    return _MEMO[k]


def _page(uc):
    return _une_fois(uc, "page", calcul=lambda: jsonable_encoder(uc.page()))


def _panneau(uc, region: str):
    region = region if region in REGIONS else "ALL"
    return _une_fois(uc, "panel", region, calcul=lambda: jsonable_encoder(uc.panel(region)))


def _prechauffer():
    territoire = get_territory()
    if territoire.available():
        for r in ["ALL", *REGIONS]:
            _panneau(territoire, r)
        _une_fois(territoire, "cross", calcul=lambda: jsonable_encoder(territoire.cross()))
        _une_fois(territoire, "lineage", calcul=territoire.lineage)
    for uc in (get_energie(), get_btp(), get_projets(), get_francophonie()):
        if uc.available():
            _page(uc)


@app.get("/parc", response_class=HTMLResponse)
def parc(request: Request, overview: Annotated[FleetOverview, Depends(get_overview)]):
    risks, alerts = overview()
    data = {"risques": [{"plaque": r.plate, "libelle": r.label, "commune": r.commune, "score": r.risk_score,
                         "niveau": risk_level(r.risk_score), "pannes": r.failures_12m,
                         "cout": r.cost_12m, "derive": r.drift_ratio} for r in risks]}
    return templates.TemplateResponse(request, "index.html", {"risks": risks, "alerts": alerts, "data": data,
                                                              "sql": overview.sql()})


_QUOTA = depuis_env()
_TEXTE_MAX = 3000  # un compte rendu d'intervention tient en quelques lignes ; au-delà, c'est la facture qui grossit


@app.post("/analyze", response_class=HTMLResponse)
def analyze(request: Request, uc: Annotated[AnalyzeReport, Depends(get_analyze)],
            asset_id: Annotated[int | None, Form()] = None, text: Annotated[str, Form()] = ""):
    if len(text) > _TEXTE_MAX:
        return HTMLResponse(f'<p class="erreur">Texte trop long : {_TEXTE_MAX} caractères au plus.</p>')
    # Le quota ne vaut que pour le vrai LLM : le simulateur ne coûte rien
    if os.getenv("ANTHROPIC_API_KEY"):
        refus = _QUOTA.refus(request.client.host if request.client else "inconnu")
        if refus:
            return HTMLResponse(f'<p class="erreur">{refus}</p>', status_code=429)
    try:
        result = uc(asset_id, text)
    except ValueError as e:
        return HTMLResponse(f'<p class="erreur">{escape(str(e))}</p>')
    return templates.TemplateResponse(request, "partials/analysis.html", {"a": result})


@app.get("/privacy-map", response_class=HTMLResponse)
def privacy_map(request: Request, store=Depends(get_store)):
    return templates.TemplateResponse(request, "partials/map.html", {"rows": store.all()})


# --- Observatoire territorial (open data La Réunion) -------------------------------------------

@app.get("/observatoire", response_class=HTMLResponse)
def observatoire(request: Request, uc: Annotated[TerritoryDashboard, Depends(get_territory)]):
    if not uc.available():
        return templates.TemplateResponse(request, "dashboard.html", {"missing": True})
    return templates.TemplateResponse(request, "dashboard.html", {
        "missing": False, "regions": REGIONS,
        "panel": _panneau(uc, "ALL"),
        "cross": _une_fois(uc, "cross", calcul=lambda: jsonable_encoder(uc.cross())),
        "lineage": _une_fois(uc, "lineage", calcul=uc.lineage)})


@app.get("/observatoire/panel", response_class=HTMLResponse)
def observatoire_panel(request: Request, uc: Annotated[TerritoryDashboard, Depends(get_territory)],
                       region: str = "ALL"):
    return templates.TemplateResponse(request, "partials/territory_panel.html",
                                      {"panel": _panneau(uc, region)})


@app.get("/observatoire/pair")
def observatoire_pair(uc: Annotated[TerritoryDashboard, Depends(get_territory)], x: str, y: str):
    try:
        return jsonable_encoder(uc.pair(x, y))
    except ValueError as e:
        raise HTTPException(400, str(e))


# --- Projets antérieurs : carte des bornes (projet final Le Wagon) et trading algorithmique ------------

@app.get("/projets", response_class=HTMLResponse)
def projets(request: Request, uc: Annotated[ProjetsShowcase, Depends(get_projets)]):
    if not uc.available():
        return templates.TemplateResponse(request, "projets.html", {"missing": True})
    extraits = {f.name: f.read_text(encoding="utf-8") for f in _EXTRAITS.iterdir() if f.is_file()}
    return templates.TemplateResponse(request, "projets.html", {"missing": False, "page": _page(uc),
                                                                "extraits": extraits})


@app.get("/projets/donnees/{name}.json")
def projets_donnees(uc: Annotated[ProjetsShowcase, Depends(get_projets)], name: str):
    try:
        return jsonable_encoder(uc.donnees(name))
    except ValueError as e:
        raise HTTPException(404, str(e))


# --- Francophonie canadienne : recensements 1951-2021 (Statistique Canada) ---------------------------------

@app.get("/energie", response_class=HTMLResponse)
def energie(request: Request, uc: Annotated[EnergieShowcase, Depends(get_energie)]):
    if not uc.available():
        return templates.TemplateResponse(request, "energie.html", {"missing": True})
    return templates.TemplateResponse(request, "energie.html", {"missing": False,
                                                            "page": _page(uc)})


@app.get("/btp", response_class=HTMLResponse)
def btp(request: Request, uc: Annotated[BtpShowcase, Depends(get_btp)]):
    if not uc.available():
        return templates.TemplateResponse(request, "btp.html", {"missing": True})
    return templates.TemplateResponse(request, "btp.html", {"missing": False,
                                                            "page": _page(uc)})


@app.get("/francophonie", response_class=HTMLResponse)
def francophonie(request: Request, uc: Annotated[FrancophonieShowcase, Depends(get_francophonie)]):
    if not uc.available():
        return templates.TemplateResponse(request, "francophonie.html", {"missing": True})
    return templates.TemplateResponse(request, "francophonie.html", {"missing": False,
                                                            "page": _page(uc)})
