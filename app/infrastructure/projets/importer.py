"""Import des projets antérieurs au portfolio : la carte des bornes (projet final Le Wagon) et les
rapports MetaTrader 5 (trading algorithmique). Les sources sont aplaties en CSV, sans aucun nettoyage :
le nettoyage vit dans `projets_schema.sql`, là où il se relit et se compte.

    python -m app.infrastructure.projets.importer --lewagon <dossier ProjetFinal> --trading <dossier Trading>

Ce qui n'est PAS importé, volontairement : les scripts Python de connexion à MetaTrader, qui contiennent
des identifiants de compte. Le portfolio ne montre que du code relu et sans secret.
"""
import argparse
import csv
import html
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

RAW = Path("data/raw/projets")
_SS = {"ss": "urn:schemas-microsoft-com:office:spreadsheet", "o": "urn:schemas-microsoft-com:office:office"}

# Colonnes communes aux trois optimisations ; les paramètres propres à chaque robot partent en JSON
_COMMUNES = ["Pass", "Profit", "Expected Payoff", "Profit Factor", "Recovery Factor", "Sharpe Ratio",
             "Equity DD %", "Trades"]


def bornes(projet_final: Path, dest: Path) -> int:
    """Aplatit le JSON mensuel {"AAAA-MM": [points]} en une ligne par point de charge.

    On repart du fichier MENSUEL seulement : le trimestriel en est un regroupement, et ses clés
    « 2025-Q%q » (un format de date que pandas ne connaît pas) le rendent inutilisable tel quel.
    Le trimestre se recalcule en SQL à partir du mois.
    """
    src = json.loads((projet_final / "bornes_recharge_mensuel.json").read_text(encoding="utf-8"))
    n = 0
    with (dest / "bornes.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["mois", "code_insee", "latitude", "longitude", "nbre_pdc", "puissance_nominale"])
        for mois in sorted(src):
            for p in src[mois]:
                w.writerow([mois, p.get("code_insee"), p.get("latitude"), p.get("longitude"),
                            p.get("nbre_pdc"), p.get("puissance_nominale")])
                n += 1
    return n


def optimisation(xml_file: Path) -> tuple[dict, list[dict]]:
    """Lit un rapport d'optimisation MT5 (classeur XML Excel 2003) : en-tête + une ligne par passe."""
    root = ET.parse(xml_file).getroot()
    prop = lambda k: (root.find(f".//o:{k}", _SS).text if root.find(f".//o:{k}", _SS) is not None else None)
    # Titre : « <robot> <symbole>,<unité de temps> <début>-<fin> »
    m = re.match(r"(.+?) (\w+),(\w+) ([\d.]+)-([\d.]+)", prop("Title") or "")
    meta = {"fichier": xml_file.name, "robot": m.group(1), "symbole": m.group(2), "unite": m.group(3),
            "debut": m.group(4).replace(".", "-"), "fin": m.group(5).replace(".", "-"),
            "cree": (prop("Created") or "")[:10], "depot": prop("Deposit"), "levier": prop("Leverage")}
    rows = [[(c.find("ss:Data", _SS).text if c.find("ss:Data", _SS) is not None else None)
             for c in r.findall("ss:Cell", _SS)] for r in root.findall(".//ss:Row", _SS)]
    head, passes = rows[0], []
    for r in rows[1:]:
        d = dict(zip(head, r))
        passes.append({**{k: d[k] for k in _COMMUNES},
                       "params": json.dumps({k: d[k] for k in head if k not in _COMMUNES + ["Result", "Custom"]})})
    return meta, passes


def backtest(report: Path) -> dict:
    """Extrait le résumé d'un rapport de test MT5 (HTML en UTF-16) : réglages et résultats, libellé → valeur."""
    text = report.read_text(encoding="utf-16")
    cells = [html.unescape(re.sub(r"<[^>]+>", "", c)).strip() for c in re.findall(r"<td[^>]*>(.*?)</td>", text, re.S)]
    out, i = {}, 0
    stop = cells.index("Ordres") if "Ordres" in cells else len(cells)
    while i < stop - 1:
        if cells[i].endswith(":") and cells[i + 1] and not cells[i + 1].endswith(":"):
            out[cells[i].rstrip(":").strip()] = cells[i + 1]
            i += 2
        else:
            i += 1
    return {"fichier": report.name, "resume": out}


def trading(dossier: Path, dest: Path) -> int:
    metas, n = [], 0
    with (dest / "trading_passes.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["optimisation", *_COMMUNES, "params"])
        for i, xml_file in enumerate(sorted((dossier / "Optimisation").glob("*.xml")), start=1):
            meta, passes = optimisation(xml_file)
            metas.append({"id": i, **meta, "passes": len(passes)})
            for p in passes:
                w.writerow([i, *[p[k] for k in _COMMUNES], p["params"]])
                n += 1
    (dest / "trading_optimisations.json").write_text(json.dumps(metas, ensure_ascii=False, indent=1), encoding="utf-8")
    reports = [backtest(r) for r in sorted((dossier / "BackTest").glob("*.html"))]
    (dest / "trading_backtests.json").write_text(json.dumps(reports, ensure_ascii=False, indent=1), encoding="utf-8")
    return n


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--lewagon", type=Path, help="dossier ProjetFinal du projet Le Wagon")
    ap.add_argument("--trading", type=Path, help="dossier Trading (sous-dossiers Optimisation et BackTest)")
    ap.add_argument("--dest", type=Path, default=RAW)
    a = ap.parse_args(argv)
    a.dest.mkdir(parents=True, exist_ok=True)
    if a.lewagon:
        print(f"bornes : {bornes(a.lewagon, a.dest):,} points de charge".replace(",", " "))
    if a.trading:
        print(f"trading : {trading(a.trading, a.dest):,} passes d'optimisation".replace(",", " "))


if __name__ == "__main__":
    main()
