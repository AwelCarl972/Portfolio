import os
from pathlib import Path
from typing import Annotated

import duckdb
from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.application.use_cases.analyze_report import AnalyzeReport
from app.application.use_cases.fleet_overview import FleetOverview
from app.application.use_cases.projets import ProjetsShowcase
from app.application.use_cases.territory_dashboard import TerritoryDashboard
from app.domain.rules import risk_level, status_label
from app.domain.territory import REGIONS

from .deps import get_analyze, get_overview, get_projets, get_store, get_territory
from .quota import depuis_env

app = FastAPI(title="ParcInsulaire")
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")
_EXTRAITS = Path(__file__).parent / "extraits"  # code d'anciens projets, relu et sans secret


@app.exception_handler(duckdb.IOException)
def db_locked(request: Request, exc: duckdb.IOException):
    # DuckDB n'autorise qu'un processus écrivain par fichier : cas typique = deux serveurs lancés.
    return HTMLResponse("<h1>Base de données indisponible</h1><p>Le fichier DuckDB est verrouillé par un "
                        "autre processus (un second serveur uvicorn est-il lancé ?). Arrêtez-le puis rechargez."
                        f"</p><pre>{exc}</pre>", status_code=503)


templates.env.globals.update(risk_level=risk_level, status_label=status_label)


@app.get("/sante")
def sante():
    """Sonde du conteneur : ne charge rien, répond dès que le serveur écoute."""
    return {"ok": True}


@app.get("/", response_class=HTMLResponse)
def index(request: Request, overview: Annotated[FleetOverview, Depends(get_overview)]):
    risks, alerts = overview()
    return templates.TemplateResponse(request, "index.html", {"risks": risks, "alerts": alerts})


_QUOTA = depuis_env()
_TEXTE_MAX = 3000  # un compte rendu d'intervention tient en quelques lignes ; au-delà, c'est la facture qui grossit


@app.post("/analyze", response_class=HTMLResponse)
def analyze(request: Request, uc: Annotated[AnalyzeReport, Depends(get_analyze)],
            asset_id: Annotated[int | None, Form()] = None, text: Annotated[str, Form()] = ""):
    if len(text) > _TEXTE_MAX:
        return HTMLResponse(f'<p class="text-red-600">Texte trop long : {_TEXTE_MAX} caractères au plus.</p>')
    # Le quota ne vaut que pour le vrai LLM : le simulateur ne coûte rien
    if os.getenv("ANTHROPIC_API_KEY"):
        refus = _QUOTA.refus(request.client.host if request.client else "inconnu")
        if refus:
            return HTMLResponse(f'<p class="text-amber-600">{refus}</p>', status_code=429)
    try:
        result = uc(asset_id, text)
    except ValueError as e:
        return HTMLResponse(f'<p class="text-red-600">{e}</p>')
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
        "panel": jsonable_encoder(uc.panel("ALL")), "cross": jsonable_encoder(uc.cross()),
        "lineage": uc.lineage()})


@app.get("/observatoire/panel", response_class=HTMLResponse)
def observatoire_panel(request: Request, uc: Annotated[TerritoryDashboard, Depends(get_territory)],
                       region: str = "ALL"):
    return templates.TemplateResponse(request, "partials/territory_panel.html",
                                      {"panel": jsonable_encoder(uc.panel(region))})


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
    return templates.TemplateResponse(request, "projets.html", {"missing": False, "page": jsonable_encoder(uc.page()),
                                                                "extraits": extraits})


@app.get("/projets/donnees/{name}.json")
def projets_donnees(uc: Annotated[ProjetsShowcase, Depends(get_projets)], name: str):
    try:
        return jsonable_encoder(uc.donnees(name))
    except ValueError as e:
        raise HTTPException(404, str(e))
