# From raw public data to decisions

*[Version française](README.md)*

**Data Analyst portfolio** · advanced SQL · Rust · Python · web dashboards without a BI licence

> Public datasets from Canada (Statistics Canada, 70 years of census data) and from Reunion Island
> (real estate, employment, road safety, climate): downloaded, profiled, cleaned, modelled and presented,
> **with every line of SQL visible in the interface.**
> Plus an AI module that processes business data **without ever exposing it**.
>
> Native French speaker, English intermediate (B1) and improving · open to relocating to Canada outside Quebec
> (or Reunion Island) · permanent or fixed-term · Data Analyst, data tooling, AI automation.

The interface is in French; this document describes what each page shows.

---

## What the data says (highlights)

| Topic | Finding | How |
|---|---|---|
| French in Canada | Outside Quebec, **1 million** people had French as their mother tongue in 2021, up 39 % since 1951, yet their share **halved** (7.3 % → 3.5 %) | 4 Statistics Canada tables, `PIVOT`, recomputed shares checked against published ones |
| Language transmission | In New Brunswick, **89 %** of French mother-tongue speakers still mostly speak French at home, vs. 56 % in Ontario and 42 % in Manitoba | Language continuity index (home language ÷ mother tongue) |
| Bilingualism | English-French bilingualism rose from 26 % to **46 %** in Quebec (1951-2021) but has stalled at about 10 % in the rest of Canada since 2001 | Time series by province |
| Francophone immigration | **28,975** French-speaking permanent residents admitted outside Quebec in 2025 (×3.7 since 2019, 8.7 % of admissions vs. an 8.5 % target); **42 %** settled in Ottawa | 28,000 monthly IRCC rows, suppressed cells kept as NULL |
| Choosing a city | Across 9 cities and 11 indicators (French, cost of living, jobs, quality of life), **Ottawa** ranks first with equal weights; **Moncton** takes the lead as soon as French counts double | Min-max scores (`UNPIVOT` + window functions), weights adjustable in the page |
| Real estate (Reunion) | Median price **€2,849/m²** in 2025; growth since 2016-18 ranges from **+6 %** to **+61 %** by municipality | 52,560 cleaned property sales, medians and quartiles in SQL |
| Income × prices | **Moderate** correlation between median income and price per m² (r = 0.58, R² = 0.33, 17 municipalities) | Pearson + Spearman matrix (`UNPIVOT`, `RANK`), `regr_*` regression |
| Road safety | Accidents peak **on Mondays at 7 a.m.**; rain on the day **does not significantly** raise the risk (relative risk ×1.14, overlapping 95 % CIs) | 9,208 accidents joined with daily weather, confidence intervals |
| Climate | **−0.64 °C per 100 m** of altitude (R² = 0.96); warming of **+0.27 °C per decade** since 1961; 22× more rain on the windward heights than on the west coast | 249 Météo-France stations, 1991-2020 normals |

Limits are shown next to the results: small samples, correlation is not causation, census data are
self-reported and end in 2021. A number is only worth something if you know where it comes from.

## What this project shows about how I work

- **SQL carries the analysis.** All analytical logic lives in `.sql` files: CTEs, window functions
  (`LAG`, `FIRST_VALUE`, `NTILE`, `RANK`, rolling averages), `PIVOT` / `UNPIVOT`, `quantile_cont`,
  `regr_slope` and `regr_r2`, `FILTER`, `DISTINCT ON`, `arg_min` / `arg_max`. Python wires the results, the browser draws them.
- **Data quality is checked, not assumed.** Raw-file profiling, explicit cleaning rules, raw → kept row counts for
  every source, and recomputed figures confronted with the official ones (max gap: 0.07 points on the Canadian census).
- **Full traceability.** Each page has a *Data & SQL* tab with the pipeline, sources, cleaning rules and all SQL.
  What is shown is read from the files that run, so documentation cannot drift from code.
- **Rust where speed and safety matter.** The `datakit` binary profiles raw files (224,000 rows in under half a
  second, gzip included) and runs the pseudonymization engine.
- **No licence needed to read it.** A light web page (FastAPI + HTMX + ECharts): filters, a table view for every chart,
  dark mode, colour-blind-checked palette.
- **AI without data leaks.** Names, plates, addresses and phone numbers are replaced locally by aliases before any call
  to an AI model, then restored for display.

---

## 1. Canadian Francophonie (`/francophonie`)

French outside Quebec in five tabs: **Evolution 1951-2021 · Where to live in French · Immigration since 2015 ·
Choosing a city · Data & SQL**.

- **Immigration**: French-speaking permanent residents by month and city (IRCC, 2015-2026), against the federal
  targets (6 % in 2024, 8.5 % in 2025, 9 % in 2026).
- **Choosing a city**: Moncton, Halifax, Ottawa, Greater Sudbury, Toronto, Winnipeg, Edmonton, Calgary and Vancouver
  compared on 11 official indicators (2021 census by city, CMHC rents, Market Basket Measure, after-tax income,
  unemployment, Crime Severity Index, life satisfaction), scored out of 100 in four pillars, with weight sliders, a
  parallel-coordinates chart and a French-vs-cost trade-off map. Every source names cities differently: the mapping
  is written once, in the domain, with the level actually published (city or province).

| Statistics Canada table | Content |
|---|---|
| 15-10-0031-01 | Mother tongue, 1951-2021 |
| 15-10-0032-01 | First official language spoken, 1971-2021 |
| 15-10-0004-01 | Knowledge of official languages (bilingualism), 1951-2021 |
| 15-10-0033-01 | Language spoken most often at home, 1971-2021 |
| 98-10-0192-01 | 2021 census by city (45 cells read through the web API instead of a 29 MB download) |
| 11-10-0066-01, 34-10-0133-01, 11-10-0190-01 | Market Basket Measure 2025, CMHC rents 2025, median after-tax income 2024 |
| 14-10-0385-01, 35-10-0026-01, 13-10-0843-01 | Unemployment by city 2024, Crime Severity Index 2025, life satisfaction 2025 |
| IRCC open data | Permanent residents, French-speaking and all, by city and month, 2015-2026 |

- **Cleaning**: the 4 tables stacked into one long format; geography labels trimmed (one table writes
  "Saskatchewan " with a trailing space, which would silently drop the province from every join); counts only;
  "distributed" multiple responses so that 1951 and 2021 stay comparable; pre-1999 Nunavut kept apart.
- **Checks**: shares are recomputed from counts and compared with the published percentages.
- **Indicators**: language continuity index, base-100 index, change between censuses (`LAG`), each province's
  share of the total (`SUM() OVER ()`).

## 2. Reunion Island observatory (`/observatoire`)

A 6-tab dashboard: **Real estate · Road safety · Employment & housing · Climate · Correlations · Data & SQL**.
Every chart has a **Table** button and a **SQL** button that opens its query.

| Source | Volume | Use |
|---|---|---|
| DVF property transactions 2014-2025 | 54,000 sales | price per m², spread, trends |
| INSEE Filosofi income 2014 (IRIS → municipality) | 17 municipalities | median income, poverty, Gini |
| Official population 2006-2016 | 24 municipalities | density, growth, ratios |
| Job seekers 2016-2022 | monthly × municipality | base-100 index by micro-region |
| Building permits 2017-2022 | 20,000 permits | individual / collective / social housing |
| Road accidents (BAAC) 2012-2024 | 9,200 accidents | risk hours, severity |
| SYNOP weather, Gillot 2010-2026 | 47,000 three-hourly records | rain ↔ accidents |
| Météo-France climate database 1950-2026 | 249 stations, 91,000 monthly records | Climate tab |

**Pipeline:** open-data API → raw CSV → **quality profile (Rust)** → SQL loading and cleaning (12 steps)
→ DuckDB analytical model (14 tables and views) → 18 named queries → Python use cases → JSON → ECharts.

## 3. Rust: `datakit`

A native binary (`rust/datakit`) called from Python through a local pipe. It touches no database: it receives its
input and answers in JSON.

| Command | Role |
|---|---|
| `datakit profile <files>` | Streaming quality profile (CSV and `.csv.gz`): inferred types, % empty, cardinality, min/max, malformed rows, timing |
| `datakit anonymize` | Sensitive-entity detection (dictionary + patterns) and deterministic HMAC-SHA256 fingerprint |

A cross-test (pytest) proves the Rust and Python engines produce exactly the same anonymized text. The Python
engine remains as a fallback (`PRIVACY_ENGINE=python`).

## 4. Fleet & AI: predictive maintenance and privacy (`/parc`)

Management of a fleet of vehicles and machinery (simulated data): risk score per asset, drift in failure intervals,
and **the latest date to order parts by sea (30-45 days) or air freight (4-7 days)**. The AI writes the analysis of a
service report, but only ever sees aliases:

```
Raw text ──► Local masking (Rust) ──► Anonymized payload ──► LLM ──► Answer (aliases) ──► Local re-identification
```

- Aliases are **deterministic** (`PREFIX_` + HMAC-SHA256 with a local key): the same entity keeps the same alias
  across calls, so the AI sees recurrences without knowing identities.
- The mapping table and the key **stay on the machine**. A *"What the AI receives"* tab shows the exact payload.
- **Known limit**: this is detection-based pseudonymization; an unknown proper noun matching no pattern would not be
  masked. Next step: a local named-entity recognition stage behind the same `Anonymizer` port.

## 5. Earlier projects, revisited (`/projets`)

- **EV charging stations (Le Wagon final project, 2025).** 126,787 charging points opened in France from 2010 to
  2025 on 30,113 sites: an animated month-by-month map. Revisiting it, I counted the outliers instead of hiding them,
  recomputed broken quarter keys in SQL, treated 0 kW as unknown, and drew 30,113 sites once instead of 126,790
  markers per frame.
- **Algorithmic trading (MQL5, until 2022).** 9,943 MetaTrader 5 optimization passes on three robots. Finding: on one
  month of data the "best" settings rest on about twenty trades, and passes with more than 100 trades almost all
  lose. The page states what I would do today: out-of-sample validation, minimum volume, distributions over maximums.

## Architecture (Clean Architecture, without over-abstraction)

```
app/
├─ domain/                 # pure business code: models, ports (Protocols), rules, reference data
├─ application/use_cases/  # orchestration: francophonie, territory_dashboard, analyze_report, fleet_overview, projets
├─ infrastructure/
│  ├─ sql/                 # *.sql (loading, views, named queries) + DuckDB adapters
│  ├─ opendata/fetch.py    # open-data downloads (Statistics Canada, Reunion Region, Météo-France)
│  ├─ privacy/             # Python pseudonymization + bridge to the Rust engine
│  ├─ ai/                  # Anthropic LLM or offline simulator
│  └─ seed.py              # simulated fleet data
└─ presentation/web/       # FastAPI + Jinja + HTMX + ECharts; deps.py = composition root
rust/datakit/              # Rust binary: quality profiling + pseudonymization
tests/                     # pytest: privacy, end-to-end SQL, Rust/Python equivalence, census checks
```

Dependencies point towards the domain. Changing database, LLM or masking engine means writing one adapter.

## Run it

```powershell
python -m venv .venv; .venv\Scripts\activate
pip install -r requirements.txt
cd rust\datakit; cargo build --release; cd ..\..   # optional: without the binary, falls back to Python
python -m app.infrastructure.opendata.fetch       # ~22 MB of open data, once
python -m uvicorn app.presentation.web.main:app --reload
```

Open http://127.0.0.1:8000/francophonie, http://127.0.0.1:8000/observatoire and http://127.0.0.1:8000/parc.
Without an API key an offline AI simulator answers; with `ANTHROPIC_API_KEY` (and `pip install anthropic`) it is a
real LLM. Tests: `pytest` and `cargo test`.

---

## About me

- **Data & development**: certified AI & Big Data developer (Le Wagon, French state certification, bachelor's level);
  2 years of web development (PHP/Symfony, WordPress from scratch); modular architecture, SOLID, Clean Architecture.
  Today: advanced SQL, Rust, Python, and daily use of AI to move faster.
- **Method**: a "smart lazy" person. No repetitive task that could be automated, no over-engineering, the shortest
  path to a reliable and maintainable result.
- **Field experience**: construction site manager and mason (estimating, margins, supply), real-estate diagnostician
  (audits, compliance, reports), fleet management and motorhome assessment (maintenance, parts, claims). I understand
  the data because I have done the jobs that produce it.
- **Islands and remote markets**: 7 years in Martinique; I know freight, supply lead times and small-market economics.
- **Rigour**: volunteer shooting-school director and instructor for 5 years: strict safety, teaching, young shooters
  coached up to the French national championships.
- **Languages**: French (native), English (intermediate, B1), learning fast in practice.
- **Availability**: ready to relocate with my family. I would rather show you this project live than take an online test.
