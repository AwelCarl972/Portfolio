-- Requêtes de la page Projets (carte des bornes, trading algorithmique).

-- name: bornes_kpis
-- Chiffres clés du déploiement : volume, période, part de la haute puissance, poids de La Réunion
SELECT COUNT(*) AS points,
       (SELECT COUNT(*) FROM pj_site) AS sites,
       strftime(min(mise_en_service), '%m/%Y') AS debut, strftime(max(mise_en_service), '%m/%Y') AS fin,
       ROUND(100 * COUNT(*) FILTER (WHERE classe LIKE 'Haute%') / COUNT(*) FILTER (WHERE puissance IS NOT NULL), 1) AS part_hp,
       COUNT(*) FILTER (WHERE territoire = 'La Réunion') AS points_reunion,
       (SELECT COUNT(*) FROM pj_site WHERE territoire = 'La Réunion') AS sites_reunion,
       COUNT(*) FILTER (WHERE annee = 2023) AS points_2023,
       ROUND(100 * COUNT(*) FILTER (WHERE annee = 2023) / COUNT(*), 0) AS part_2023
FROM pj_borne;

-- name: bornes_annuel
-- Points mis en service par année et classe de puissance
SELECT annee, classe, COUNT(*) AS n FROM pj_borne GROUP BY ALL ORDER BY annee, classe;

-- name: bornes_cumul
-- Parc cumulé mois par mois (window function), base de la frise de la carte
WITH m AS (SELECT mise_en_service AS mois, COUNT(*) AS n FROM pj_borne GROUP BY 1)
SELECT strftime(mois, '%Y-%m') AS mois, n, SUM(n) OVER (ORDER BY mois) AS cumul
FROM m ORDER BY mois;

-- name: bornes_sites
-- Sites pour la carte : position, mois d'ouverture (rang depuis 2010), taille, puissance maximale
SELECT lat, lon, territoire, strftime(ouverture, '%Y-%m') AS ouverture,
       12 * (year(ouverture) - 2010) + month(ouverture) - 1 AS rang, points, puissance_max
FROM pj_site ORDER BY ouverture;

-- name: bornes_territoires
-- Répartition par territoire : points, sites, points pour 100 sites, part de haute puissance
SELECT territoire, COUNT(*) AS points, COUNT(DISTINCT (round(latitude, 5), round(longitude, 5))) AS sites,
       ROUND(100 * COUNT(*) FILTER (WHERE classe LIKE 'Haute%') / NULLIF(COUNT(*) FILTER (WHERE puissance IS NOT NULL), 0), 1) AS part_hp
FROM pj_borne GROUP BY 1 ORDER BY points DESC;

-- name: bornes_qualite
-- Du brut au retenu : chaque règle de nettoyage et le nombre de lignes qu'elle touche
SELECT regle, lignes FROM pj_qualite ORDER BY ordre;

-- name: trading_resume
-- Par optimisation : passes testées, part rentable, meilleur résultat et nombre de trades qui le porte
WITH r AS (
    SELECT *, ROW_NUMBER() OVER (PARTITION BY optimisation ORDER BY profit DESC) AS rang,
           NTILE(20) OVER (PARTITION BY optimisation ORDER BY profit DESC) AS vingtile
    FROM pj_passe
)
SELECT o.id, o.libelle, o.robot, o.jours, o.passes,
       ROUND(100 * COUNT(*) FILTER (WHERE profit > 0) / COUNT(*), 0) AS pct_rentables,
       ROUND(median(profit)) AS profit_median,
       ROUND(max(profit)) AS profit_max,
       any_value(trades) FILTER (WHERE rang = 1) AS trades_meilleure,
       ROUND(any_value(drawdown_pct) FILTER (WHERE rang = 1), 1) AS dd_meilleure,
       median(trades) AS trades_median,
       median(trades) FILTER (WHERE vingtile = 1) AS trades_top5
FROM r JOIN pj_optimisation o ON o.id = r.optimisation
GROUP BY ALL ORDER BY o.id;

-- name: trading_nuage
-- Toutes les passes : risque (drawdown) contre gain, et nombre de trades qui les produit
SELECT optimisation, passe, ROUND(profit) AS profit, ROUND(drawdown_pct, 2) AS dd, trades,
       ROUND(profit_factor, 2) AS pf
FROM pj_passe ORDER BY optimisation, profit DESC;

-- name: trading_fiabilite
-- Le piège du sur-apprentissage : selon le nombre de trades, l'écart entre la meilleure passe et la passe médiane
SELECT optimisation,
       CASE WHEN trades < 30 THEN '< 30 trades' WHEN trades < 100 THEN '30-99 trades' ELSE '≥ 100 trades' END AS volume,
       COUNT(*) AS passes, ROUND(median(profit)) AS mediane,
       ROUND(quantile_cont(profit, 0.05)) AS p5, ROUND(quantile_cont(profit, 0.95)) AS p95, ROUND(max(profit)) AS meilleur
FROM pj_passe GROUP BY ALL ORDER BY optimisation, min(trades);
