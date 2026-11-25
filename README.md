# Données réunionnaises : de la donnée brute à la décision

*[English version](README.en.md)*

**Portfolio Data Analyst · La Réunion** — SQL avancé · Rust · Python · tableaux de bord web sans licence BI

> 8 jeux de données publiques réunionnaises (immobilier, emploi, sécurité routière, climat) :
> téléchargés, profilés, nettoyés, modélisés et restitués, **avec chaque ligne de SQL visible dans l'interface.**
> Plus un module IA qui traite des données d'entreprise **sans jamais les exposer**.
>
> Installation à La Réunion sous 30 jours · CDI / CDD · Data Analyst, outils data, automatisation IA.

---

## Ce que disent les données (extraits)

| Thème | Constat | Comment |
|---|---|---|
| Immobilier | Prix médian **2 849 €/m²** en 2025 (+3,4 % sur un an). Depuis 2016-18, de **+6 %** (Bras-Panon) à **+61 %** (Entre-Deux) selon la commune | 52 560 ventes DVF nettoyées, médianes et quartiles en SQL |
| Revenus × immobilier | Corrélation **modérée** entre revenu médian et prix au m² (r = 0,58, R² = 0,33, 17 communes) | Matrice Pearson + Spearman (`UNPIVOT`, `RANK`), régression `regr_*` |
| Sécurité routière | Pic d'accidents **le lundi à 7 h**. La pluie du jour **n'augmente pas significativement** le risque dans le Nord (risque relatif ×1,14, IC 95 % chevauchants) | 9 208 accidents × météo journalière, intervalles de confiance |
| Climat | Il pleut **22 fois plus** sur les hauts de Sainte-Rose (10 601 mm/an) que sur la côte Ouest. **−0,64 °C par 100 m** d'altitude (R² = 0,96). Réchauffement de **+0,27 °C par décennie** depuis 1961 | 249 stations Météo-France, normales 1991-2020, anomalies par station |
| Extrêmes | **1 825 mm en 24 h** à Foc-Foc (cyclone Denise, 1966) | Records rapprochés des cyclones du même mois |
| Emploi | 174 080 demandeurs d'emploi fin 2022 (−1,9 % sur un an), évolution comparée des 4 micro-régions | Indice base 100, moyenne mobile (window functions) |
| Francophonie canadienne | Hors Québec, **1 million** de francophones en 2021 (+39 % depuis 1951) mais une part **divisée par deux** (7,3 % → 3,5 %). Le français se transmet à la maison à **89 %** au Nouveau-Brunswick, 42 % au Manitoba | 4 tableaux de Statistique Canada, `PIVOT`, `LAG`, `arg_min`/`arg_max`, parts recalculées puis contrôlées |
| Immigration francophone | **28 975** francophones admis hors Québec en 2025 (×3,7 depuis 2019, 8,7 % des admissions pour une cible de 8,5 %) ; **42 %** ont choisi Ottawa | 28 000 lignes mensuelles IRCC, cellules masquées gardées à NULL |
| Choisir une ville | Sur 9 villes et 11 indicateurs (francophonie, coût de la vie, emploi, cadre de vie), **Ottawa** arrive en tête à poids égaux ; **Moncton** passe devant dès que la francophonie compte double | Notes min-max (`UNPIVOT` + fenêtres), poids réglables dans la page |

Les limites sont affichées à côté des résultats : 24 communes forment un petit échantillon, une corrélation
n'est pas une causalité, et les revenus ne couvrent que 17 communes. Un chiffre ne vaut que si on sait d'où il vient.

## Ce que ce projet montre de ma façon de travailler

- **Le SQL porte l'analyse.** Toute la logique analytique tient dans des fichiers `.sql` : CTE, window
  functions (`LAG`, `FIRST_VALUE`, `NTILE`, moyennes glissantes), `UNPIVOT`, `quantile_cont`, `regr_slope` et `regr_r2`,
  `FILTER`, `DISTINCT ON`, conversion de fuseau horaire. Python assemble les résultats, le navigateur dessine.
- **Rust pour ce qui doit être rapide et sûr.** Le binaire `datakit` profile la qualité des fichiers bruts
  (224 000 lignes en moins d'une demi-seconde, gzip compris) et fait tourner le moteur de pseudonymisation.
- **Qualité de données contrôlée.** Profil automatique des fichiers bruts à chaque téléchargement, règles
  de nettoyage explicites, et lignes brutes → retenues affichées pour chaque source.
- **Traçabilité totale.** L'onglet *Données & SQL* affiche le pipeline, les paramètres exacts envoyés aux API,
  le profil qualité, les règles de nettoyage, tout le SQL et le code Rust. Ce qui est affiché est lu dans les
  fichiers exécutés, donc la documentation ne peut pas diverger du code.
- **Restitution sans licence.** Une page web légère (FastAPI + HTMX + ECharts), consultable partout, avec
  filtres, vue tableau pour chaque graphique, mode sombre et palette vérifiée pour les daltoniens.
- **IA sans fuite de données.** Les noms, plaques, adresses et téléphones sont remplacés localement par des alias
  avant tout appel à un modèle d'IA, puis rétablis à l'affichage.

---

## 1. Observatoire Réunion (`/observatoire`)

Tableau de bord en 6 onglets : **Immobilier · Sécurité routière · Emploi & logement · Climat · Corrélations ·
Données & SQL**. L'adresse garde l'onglet ouvert (`/observatoire#climat`). Chaque graphique a un bouton
**Tableau** et un bouton **SQL** qui ouvre sa requête.

| Source | Volume | Utilisation |
|---|---|---|
| DVF, transactions immobilières 2014-2025 | 54 000 ventes | prix au m², dispersion, évolution |
| Filosofi INSEE 2014 (IRIS → commune) | 17 communes | revenu médian, pauvreté, Gini |
| Populations légales 2006-2016 | 24 communes | densité, croissance, ratios |
| Demandeurs d'emploi 2016-2022 | mensuel × commune | indice base 100 par micro-région |
| Permis de construire 2017-2022 | 20 000 permis | individuel / collectif / social |
| Accidents corporels (BAAC) 2012-2024 | 9 200 accidents | heures à risque, gravité |
| Météo SYNOP Gillot 2010-2026 | 47 000 relevés tri-horaires | pluie ↔ accidents |
| Base climatologique Météo-France 1950-2026 | 249 stations, 91 000 relevés mensuels | onglet Climat |

Sources : data.regionreunion.com (API Opendatasoft, filtrage côté serveur) et meteo.data.gouv.fr.

**Pipeline :** API open data → CSV bruts → **profil qualité (Rust)** → chargement et nettoyage SQL
(12 étapes) → modèle analytique DuckDB (14 tables et vues) → 18 requêtes nommées → cas d'usage Python → JSON → ECharts.

## 2. Francophonie canadienne (`/francophonie`)

Le français hors Québec en 5 onglets : **Évolution 1951-2021 · Où vivre en français · Immigration depuis 2015 ·
Choisir sa ville · Données & SQL**. Même chaîne que l'Observatoire, et même règle : chaque graphique a ses boutons
*Tableau* et *SQL*.

- **Immigration** : résidents permanents d'expression française par mois et par ville (IRCC, 2015-2026), confrontés
  aux cibles fédérales (6 % en 2024, 8,5 % en 2025, 9 % en 2026).
- **Choisir sa ville** : Moncton, Halifax, Ottawa, Grand Sudbury, Toronto, Winnipeg, Edmonton, Calgary et Vancouver
  comparées sur 11 indicateurs officiels, ramenés sur 100 et regroupés en 4 piliers. Curseurs de poids, graphique
  en coordonnées parallèles, arbitrage francophonie / coût de la vie. Chaque source nomme les villes à sa façon : la
  correspondance est écrite une fois, dans le domaine, avec le niveau réellement publié (ville ou province).

| Tableau Statistique Canada | Contenu |
|---|---|
| 15-10-0031-01 | Langue maternelle, 1951-2021 |
| 15-10-0032-01 | Première langue officielle parlée, 1971-2021 |
| 15-10-0004-01 | Connaissance des langues officielles (bilinguisme), 1951-2021 |
| 15-10-0033-01 | Langue parlée le plus souvent à la maison, 1971-2021 |
| 98-10-0192-01 | Recensement 2021 par ville (45 cellules lues par l'API web, au lieu de 29 Mo) |
| 11-10-0066-01 | Mesure du panier de consommation, 2025 |
| 34-10-0133-01 | Loyers moyens SCHL, octobre 2025 |
| 11-10-0190-01 | Revenu médian après impôt, 2024 |
| 14-10-0385-01 | Chômage par ville, 2024 |
| 35-10-0026-01 | Indice de gravité de la criminalité, 2025 |
| 13-10-0843-01 | Satisfaction à l'égard de la vie, 2025 |
| IRCC (portail des données ouvertes) | Résidents permanents, francophones et tous, par ville et par mois, 2015-2026 |

- **Nettoyage** : les 4 tableaux empilés en un format long, libellés géographiques nettoyés (« Saskatchewan » suivi
  d'une espace dans un tableau aurait fait disparaître la province de la jointure), effectifs seuls, réponses multiples
  « réparties » pour comparer 1951 et 2021, Nunavut d'avant 1999 gardé à part.
- **Contrôle** : les parts sont recalculées depuis les effectifs puis confrontées à celles que publie Statistique Canada
  (écart maximal : 0,07 point, dû aux arrondis).
- **Indicateurs** : indice de continuité linguistique (langue de la maison ÷ langue maternelle), indice base 100,
  variations entre recensements (`LAG`), part de chaque province dans le total (`SUM() OVER ()`).

```powershell
python -m app.infrastructure.opendata.fetch statcan_langue_maternelle statcan_plos statcan_connaissance statcan_langue_maison statcan_recensement_villes statcan_mbm statcan_loyers statcan_revenus statcan_chomage_rmr statcan_criminalite statcan_satisfaction ircc_francophones_rmr ircc_rp_rmr
```

## 3. Rust : `datakit`

Binaire natif (`rust/datakit`) appelé par Python via un tube local. Il ne touche à aucune base : il reçoit
ses entrées et répond en JSON.

| Commande | Rôle |
|---|---|
| `datakit profile <fichiers>` | Profil qualité en flux (CSV et `.csv.gz`) : types déduits, % de vides, cardinalités, min/max, lignes mal formées, temps |
| `datakit anonymize` | Détection des entités sensibles (dictionnaire + motifs) et empreinte HMAC-SHA256 déterministe |

- **Équivalence prouvée** : un test croisé (pytest) vérifie que les moteurs Rust et Python produisent
  exactement le même texte anonymisé, accents et numéros réunionnais compris. Le moteur Python reste
  disponible en repli (`PRIVACY_ENGINE=python`).
- Tests unitaires Rust : `cargo test` ; dépendances limitées à l'essentiel (`csv`, `flate2`, `hmac`, `sha2`, `fancy-regex`, `serde`).

## 4. Parc & IA : maintenance prédictive et confidentialité (`/`)

Gestion d'un parc de véhicules et d'engins (données simulées, réalistes pour La Réunion) : score de risque
par actif, dérive des intervalles de panne, et **date limite de commande des pièces selon le fret maritime
(30-45 j) ou aérien (4-7 j)**. L'IA rédige l'analyse d'un compte rendu d'intervention, mais ne voit que des alias :

```
Texte brut ──► Masquage local (Rust) ──► Payload anonymisé ──► LLM ──► Réponse (alias) ──► Réidentification locale
 "FG-482-RT chez Payet,                  "ACTIF_8F2A chez                                   "FG-482-RT chez Payet…"
  12 chemin des Lataniers"                CLIENT_1C07, LIEU_3B9E"
```

- Les alias sont **déterministes** : `PRÉFIXE_` + HMAC-SHA256 (clé locale), donc une même entité garde le même alias
  d'un appel à l'autre. L'IA voit les récurrences sans connaître les identités.
- La table de correspondance et la clé **restent sur la machine**. Un onglet *« Ce que l'IA reçoit »* montre le
  payload exact à côté de l'affichage local.
- **Limite assumée** : c'est de la pseudonymisation par détection. Un nom propre inconnu du dictionnaire et
  ne ressemblant à aucun motif ne serait pas masqué. Suite prévue : une étape de reconnaissance d'entités locale
  derrière le même port `Anonymizer`.

## 5. Projets : avant ce portfolio, repris et corrigés (`/projets`)

Deux travaux antérieurs, rechargés dans la même chaîne (CSV → SQL DuckDB → ECharts) et relus avec un œil d'analyste.

- **Bornes de recharge (projet final Le Wagon, 2025).** 126 787 points de charge mis en service en France de 2010
  à 2025, sur 30 113 sites. Carte animée mois par mois, graphique annuel par classe de puissance. En reprenant le
  projet : 3 dates aberrantes (1930, 2002) écartées et comptées au lieu d'être masquées, trimestres recalculés en
  SQL (les clés d'origine « 2025-Q%q » étaient cassées), 6 925 puissances à 0 kW traitées comme inconnues, et une
  carte qui dessine 30 113 sites une fois au lieu de 126 790 marqueurs à chaque image.
- **Trading algorithmique (MQL5, jusqu'en 2022).** 9 943 passes d'optimisation MetaTrader 5 sur trois robots.
  Constat : sur un mois de données, les meilleurs réglages reposent sur une vingtaine de trades, et les passes
  à plus de 100 trades perdent presque toutes. Un backtest au facteur de profit de 9 tient sur un seul trade
  gagnant. La page dit ce que je ferais aujourd'hui : validation hors échantillon, volume minimal, distribution
  plutôt que maximum.
- **Code** : un robot MQL5 multi-unités de temps (extrait commenté et original complet), le script Python de
  connexion à MetaTrader (identifiants floutés), la carte d'origine et la carte refaite, le SQL de nettoyage.

Import des sources (une fois) :

```powershell
python -m app.infrastructure.projets.importer --lewagon <dossier ProjetFinal> --trading <dossier Trading>
```

## Architecture (Clean Architecture, sans sur-abstraction)

```
app/
├─ domain/                 # métier pur : modèles, ports (Protocols), règles, référentiel territorial
├─ application/use_cases/  # orchestration : territory_dashboard, francophonie, analyze_report, fleet_overview, projets
├─ infrastructure/
│  ├─ sql/                 # *.sql (chargement, vues, requêtes nommées) + adaptateurs DuckDB
│  ├─ opendata/fetch.py    # téléchargement open data (Région Réunion, Météo-France, Statistique Canada)
│  ├─ privacy/             # pseudonymisation Python + pont vers le moteur Rust
│  ├─ ai/                  # LLM Anthropic ou simulateur hors-ligne
│  └─ seed.py              # données simulées du parc
└─ presentation/web/       # FastAPI + Jinja + HTMX + ECharts ; deps.py = racine de composition
rust/datakit/              # binaire Rust : profilage qualité + pseudonymisation
tests/                     # pytest : confidentialité, SQL de bout en bout, équivalence Rust/Python
```

Les dépendances pointent vers le domaine. Changer de base, de LLM ou de moteur de masquage revient à écrire un adaptateur.

## Lancer le projet

```powershell
python -m venv .venv; .venv\Scripts\activate
pip install -r requirements.txt
cd rust\datakit; cargo build --release; cd ..\..   # facultatif : sans binaire, repli automatique sur Python
python -m app.infrastructure.opendata.fetch       # ~22 Mo d'open data (Réunion + Canada), une seule fois
python -m uvicorn app.presentation.web.main:app --reload
```

Ouvrir http://127.0.0.1:8000/observatoire (dashboard), http://127.0.0.1:8000/francophonie et http://127.0.0.1:8000 (Parc & IA). Sans clé API,
un simulateur d'IA hors-ligne répond ; avec `ANTHROPIC_API_KEY` (et `pip install anthropic`), c'est un vrai LLM.
Tests : `pytest` et `cargo test`.

---

## À propos de moi

- **Data & développement** : 2 ans de développement web (PHP/Symfony, WordPress en code pur sans plugin),
  architecture modulaire, SOLID, Clean Architecture, débogage de problèmes complexes. Aujourd'hui : SQL
  avancé, Rust, Python et une utilisation quotidienne de l'IA pour aller plus vite.
- **Méthode** : un « fainéant intelligent ». Aucune tâche répétitive qui pourrait être automatisée, pas d'usine
  à gaz, le chemin le plus court vers un résultat fiable et maintenable.
- **Terrain** : conducteur de travaux et maçon (chiffrage, marges, approvisionnements), diagnostiqueur
  immobilier (audits, conformité, rapports), gestion de parc et expertise de camping-cars (maintenance,
  pièces, sinistralité). Je comprends les données parce que j'ai fait les métiers qui les produisent.
- **Outre-mer** : 7 ans en Martinique. Je connais le fret, les délais d'approvisionnement et les réalités
  économiques des DROM.
- **Rigueur** : directeur d'école de tir et instructeur bénévole depuis 5 ans. Sécurité stricte, pédagogie,
  jeunes tireurs accompagnés jusqu'aux Championnats de France 10 m.
- **Langues** : français langue maternelle, anglais intermédiaire (B1), en progression.
- **Disponibilité** : installation à La Réunion sous 30 jours, ou au Canada hors Québec, CDI ou CDD. Je préfère vous montrer ce projet
  en direct plutôt que passer un test en ligne.
