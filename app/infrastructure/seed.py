"""Générateur de données simulées réalistes (La Réunion). Démo prête en 2 minutes.

    python -m app.infrastructure.seed
"""
import os
import random
from datetime import date, timedelta

from .sql.repository import Database

CLIENTS = ["Réunion Location Évasion", "Bâtiments Hoarau & Fils", "Transports Payet Express",
           "Camping-Cars Océan Indien"]
SITES = [("Dépôt Le Port", "12 chemin des Lataniers", "Le Port", "0262 42 18 07"),
         ("Agence Saint-Pierre", "48 rue Marius et Ary Leblond", "Saint-Pierre", "0262 35 64 90"),
         ("Chantier Saint-Paul", "7 impasse des Letchis", "Saint-Paul", "0692 11 47 23"),
         ("Base Saint-Denis", "3 route de la Montagne", "Saint-Denis", "0262 20 55 31")]
KINDS = ["Renault Master L2H2", "Fiat Ducato camping-car", "Mini-pelle Kubota U27", "Toyota Hilux",
         "Iveco Daily benne"]
# ref, libellé, origine, délai mer, délai air, stock, intervalle km
PARTS = [("INJ-2201", "Injecteur common-rail", "Europe", 35, 5, 2, 90000),
         ("FRN-1180", "Plaquettes de frein avant", "Europe", 30, 4, 6, 30000),
         ("EMB-770", "Kit embrayage", "Europe", 42, 6, 1, 120000),
         ("HYD-305", "Flexible hydraulique HP", "Asie", 45, 7, 0, 40000),
         ("FAP-910", "Filtre à particules", "Europe", 38, 5, 0, 100000),
         ("BAT-AGM", "Batterie AGM", "Europe", 28, 4, 3, 60000)]
N_ASSETS, N_RISKY = 14, 4


def _km(n: int) -> str:
    return f"{n:,}".replace(",", " ")


def seed(db: Database, rng_seed: int = 974) -> None:
    rnd = random.Random(rng_seed)
    today = date.today()
    letters = "ABCDEFGHJKLMNPQRSTVWXYZ"
    db.many("INSERT INTO clients VALUES (?, ?)", [(i, n) for i, n in enumerate(CLIENTS, 1)])
    db.many("INSERT INTO sites VALUES (?, ?, ?, ?)", [(i, s[0], s[1], s[2]) for i, s in enumerate(SITES, 1)])
    db.many("INSERT INTO parts VALUES (?, ?, ?, ?, ?, ?)", [p[:6] for p in PARTS])

    assets, plan, logs, inters = [], [], [], []
    iid, oid = 0, 4000
    for aid in range(1, N_ASSETS + 1):
        kind = rnd.choice(KINDS)
        site_i = rnd.randrange(len(SITES))
        site = SITES[site_i]
        plate = f"{rnd.choice(letters)}{rnd.choice(letters)}-{rnd.randint(100, 999)}-{rnd.choice(letters)}{rnd.choice(letters)}"
        serial = f"SN-RU-{rnd.randint(10000, 99999)}"
        risky = aid <= N_RISKY
        rate = rnd.randint(110, 140) if risky else (rnd.randint(30, 60) if "pelle" in kind else rnd.randint(60, 120))
        km_end = rnd.randint(90000, 160000) if risky else rnd.randint(30000, 150000)
        km_start = km_end - rate * 730
        assets.append((aid, kind, plate, serial, kind.split()[0], rnd.randint(1, len(CLIENTS)), site_i + 1, km_end))
        client = CLIENTS[assets[-1][5] - 1]

        logs += [(aid, today - timedelta(days=d), km_start + rate * (730 - d)) for d in range(730, -1, -7)]
        if logs[-1][1] != today:
            logs.append((aid, today, km_end))

        def when(km):
            return today - timedelta(days=int((km_end - km) / rate))

        def add(km, cat, part, symptom):
            nonlocal iid, oid
            iid, oid = iid + 1, oid + 1
            corr = cat == "corrective"
            rpt = (f"OT-{oid} — {client}. Véhicule {plate} (série {serial}) immobilisé au "
                   f"{site[1]}, {site[2]}. {symptom} constaté à {_km(km)} km. "
                   f"Contact sur place : {site[3]}. "
                   + ("Remplacement effectué, essai concluant." if corr else "Entretien préventif réalisé."))
            inters.append((iid, aid, when(km), km, cat, part,
                           rnd.randint(400, 3500) if corr else rnd.randint(150, 900),
                           rnd.randint(1, 12) if corr else rnd.randint(0, 1), rpt))

        # Pannes : intervalles qui raccourcissent pour les actifs « à risque » (dérive détectable)
        if risky:
            pos, gaps = km_end - 1200, [7000, 12000, 20000, 30000]
            for g in gaps:
                if pos > km_start:
                    add(pos, "corrective", "INJ-2201", "Fuite injecteur")
                pos -= g
            if pos > km_start:
                add(pos, "corrective", "INJ-2201", "Fuite injecteur")
        else:
            for pos in (km_end - rnd.randint(55000, 70000), km_end - rnd.randint(15000, 30000)):
                if pos > km_start:
                    add(pos, "corrective", rnd.choice(["FRN-1180", "BAT-AGM"]), "Usure anormale")

        # Plan de maintenance : certaines pièces arrivent à échéance dans < 120 j
        for ref, _, _, _, _, _, interval in rnd.sample(PARTS, 3):
            plan.append((aid, ref, interval))
            last = km_end - interval + rate * rnd.randint(20, 110) if rnd.random() < 0.6 else km_end - interval // 3
            if last > km_start:
                add(last, "preventive", ref, "Révision programmée")

    db.many("INSERT INTO assets VALUES (?, ?, ?, ?, ?, ?, ?, ?)", assets)
    db.many("INSERT INTO maintenance_plan VALUES (?, ?, ?)", plan)
    db.many("INSERT INTO km_log VALUES (?, ?, ?)", logs)
    db.many("INSERT INTO interventions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", inters)


def seed_if_empty(db: Database) -> None:
    if db.rows("SELECT COUNT(*) AS n FROM assets")[0]["n"] == 0:
        seed(db)


if __name__ == "__main__":
    database = Database(os.getenv("FLEET_DB", "data/fleet.duckdb"))
    seed_if_empty(database)
    print("Base prête.")
