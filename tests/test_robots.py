"""Ce que les robots des moteurs voient : robots.txt, sitemap, pages tenues hors des résultats."""
import pytest

pytest.importorskip("httpx")  # le client de test de Starlette en dépend
from fastapi.testclient import TestClient  # noqa: E402

from app.presentation.web.main import HORS_MOTEURS, PAGES_PUBLIQUES, app  # noqa: E402

client = TestClient(app)


def test_robots_txt_annonce_le_sitemap_et_ferme_les_fragments():
    r = client.get("/robots.txt")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/plain")
    assert "User-agent: *" in r.text and "Sitemap: https://axelclaude.fr/sitemap.xml" in r.text
    assert "Disallow: /analyze" in r.text and "Disallow: /francophonie" not in r.text  # noindex, pas un blocage


def test_sitemap_ne_liste_que_les_pages_reunion():
    r = client.get("/sitemap.xml")
    assert r.status_code == 200 and "xml" in r.headers["content-type"]
    for p in PAGES_PUBLIQUES:
        assert f"<loc>https://axelclaude.fr{p}</loc>" in r.text
    assert "francophonie" not in r.text


def test_la_version_canada_porte_noindex():
    for chemin in HORS_MOTEURS:
        assert client.get(chemin).headers.get("X-Robots-Tag") == "noindex", chemin
    assert "X-Robots-Tag" not in client.get("/sante").headers
