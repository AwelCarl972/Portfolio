-- Projets antérieurs : chargement + nettoyage (CSV aplatis par app.infrastructure.projets.importer).
-- {raw} est remplacé par le dossier data/raw/projets. Chaque règle de nettoyage est comptée dans pj_qualite.

-- Points de charge tels que livrés par le projet Le Wagon, une ligne par point
CREATE OR REPLACE TABLE pj_borne_brut AS
SELECT * FROM read_csv('{raw}/bornes.csv', header = true,
                       types = {'mois': 'VARCHAR', 'code_insee': 'VARCHAR'});

-- Points nettoyés : date de mise en service plausible, puissance absente plutôt que 0, territoire déduit des coordonnées
CREATE OR REPLACE TABLE pj_borne AS
WITH b AS (
    SELECT *, strptime(mois || '-01', '%Y-%m-%d')::DATE AS mise_en_service,
           CASE WHEN puissance_nominale > 0 THEN puissance_nominale END AS puissance,
           CASE WHEN latitude BETWEEN 41 AND 51.2 AND longitude BETWEEN -5.5 AND 9.7 THEN 'Métropole'
                WHEN latitude BETWEEN -21.5 AND -20.8 AND longitude BETWEEN 55.1 AND 56 THEN 'La Réunion'
                WHEN latitude BETWEEN 14 AND 18.5 AND longitude BETWEEN -63.5 AND -60.5 THEN 'Antilles'
                WHEN longitude < -130 OR longitude > 160 THEN 'Pacifique'
                ELSE 'Autre' END AS territoire
    FROM pj_borne_brut
)
SELECT mise_en_service, year(mise_en_service) AS annee,
       year(mise_en_service) || '-T' || quarter(mise_en_service) AS trimestre,
       code_insee, latitude, longitude, territoire, nbre_pdc, puissance,
       CASE WHEN puissance IS NULL THEN 'Non renseignée'
            WHEN puissance < 8 THEN 'Normale (< 8 kW)'
            WHEN puissance <= 22.5 THEN 'Accélérée (8-22 kW)'
            WHEN puissance < 100 THEN 'Rapide (23-99 kW)'
            ELSE 'Haute puissance (≥ 100 kW)' END AS classe
FROM b
WHERE mise_en_service >= DATE '2010-01-01';

-- Sites de recharge : un point GPS = un site ; sa date est celle de son premier point mis en service
CREATE OR REPLACE TABLE pj_site AS
SELECT round(latitude, 5) AS lat, round(longitude, 5) AS lon, any_value(territoire) AS territoire,
       min(mise_en_service) AS ouverture, COUNT(*) AS points, max(puissance) AS puissance_max
FROM pj_borne
GROUP BY 1, 2;

-- Comptage des règles de nettoyage, du brut au retenu
CREATE OR REPLACE TABLE pj_qualite AS
SELECT 1 AS ordre, 'Points livrés par le projet Le Wagon' AS regle, COUNT(*) AS lignes FROM pj_borne_brut
UNION ALL
SELECT 2, 'Écartés : mise en service avant 2010 (1930, 2002 : saisies aberrantes)',
       COUNT(*) FILTER (WHERE mois < '2010-01') FROM pj_borne_brut
UNION ALL
SELECT 3, 'Gardés, puissance « non renseignée » au lieu de 0 kW', COUNT(*) FILTER (WHERE puissance IS NULL) FROM pj_borne
UNION ALL
SELECT 4, 'Retenus pour l''analyse', COUNT(*) FROM pj_borne;

-- Les trois optimisations MetaTrader 5 (en-têtes des rapports)
CREATE OR REPLACE TABLE pj_optimisation AS
SELECT id, robot, symbole, unite, debut::DATE AS debut, fin::DATE AS fin, cree::DATE AS cree, passes,
       symbole || ' ' || unite || ' · ' || strftime(debut::DATE, '%m/%Y') || ' → ' || strftime(fin::DATE, '%m/%Y') AS libelle,
       date_diff('day', debut::DATE, fin::DATE) AS jours
FROM read_json('{raw}/trading_optimisations.json');

-- Une ligne par jeu de paramètres testé
CREATE OR REPLACE TABLE pj_passe AS
SELECT optimisation, "Pass" AS passe, "Profit" AS profit, "Profit Factor" AS profit_factor,
       "Sharpe Ratio" AS sharpe, "Recovery Factor" AS recovery, "Equity DD %" AS drawdown_pct,
       "Trades" AS trades, params
FROM read_csv('{raw}/trading_passes.csv', header = true);
