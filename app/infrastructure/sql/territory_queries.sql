-- Requêtes du tableau de bord territorial. $region = 'ALL' ou une micro-région (Nord/Est/Ouest/Sud).

-- name: kpis
-- Indicateurs clés et leur variation (LAG annuel, LAG 12 mois pour le chômage), filtrés par micro-région
WITH c AS (SELECT * FROM od_commune WHERE $region = 'ALL' OR region = $region),
prix AS (
    SELECT annee, median(prix_m2) AS v FROM od_dvf JOIN c USING (code_insee) GROUP BY 1
), prix_y AS (
    SELECT annee, v, 100 * (v / LAG(v) OVER (ORDER BY annee) - 1) AS evol FROM prix
), acc AS (
    SELECT annee, COUNT(*) AS v, COUNT(*) FILTER (WHERE gravite = 'Mortel') AS mortels
    FROM od_accident JOIN c USING (code_insee) GROUP BY 1
), acc_y AS (
    SELECT *, 100 * (v / LAG(v) OVER (ORDER BY annee) - 1) AS evol FROM acc
), cho AS (
    SELECT mois, SUM(inscrits) AS v FROM od_chomage JOIN c USING (code_insee) GROUP BY 1
), cho_y AS (
    SELECT mois, v, 100 * (v / LAG(v, 12) OVER (ORDER BY mois) - 1) AS evol FROM cho
), lgt AS (
    SELECT annee, SUM(lgt_tot) AS v FROM od_permis JOIN c USING (code_insee) GROUP BY 1
), lgt_y AS (
    SELECT annee, v, 100 * (v / LAG(v) OVER (ORDER BY annee) - 1) AS evol FROM lgt
)
SELECT
    (SELECT SUM(pop_2016) FROM c) AS pop,
    (SELECT ROUND(100 * (SUM(pop_2016) / SUM(pop_2006) - 1), 1) FROM c) AS pop_evol,
    (SELECT COUNT(*) FROM c) AS nb_communes,
    (SELECT ROUND(v) FROM prix_y ORDER BY annee DESC LIMIT 1) AS prix_m2,
    (SELECT ROUND(evol, 1) FROM prix_y ORDER BY annee DESC LIMIT 1) AS prix_evol,
    (SELECT MAX(annee) FROM prix_y) AS prix_annee,
    (SELECT v FROM acc_y ORDER BY annee DESC LIMIT 1) AS accidents,
    (SELECT ROUND(evol, 1) FROM acc_y ORDER BY annee DESC LIMIT 1) AS accidents_evol,
    (SELECT mortels FROM acc_y ORDER BY annee DESC LIMIT 1) AS accidents_mortels,
    (SELECT MAX(annee) FROM acc_y) AS accidents_annee,
    (SELECT v FROM cho_y ORDER BY mois DESC LIMIT 1) AS chomeurs,
    (SELECT ROUND(evol, 1) FROM cho_y ORDER BY mois DESC LIMIT 1) AS chomeurs_evol,
    (SELECT strftime(MAX(mois), '%m/%Y') FROM cho_y) AS chomeurs_mois,
    (SELECT v FROM lgt_y ORDER BY annee DESC LIMIT 1) AS logements,
    (SELECT ROUND(evol, 1) FROM lgt_y ORDER BY annee DESC LIMIT 1) AS logements_evol,
    (SELECT MAX(annee) FROM lgt_y) AS logements_annee;

-- name: prix_trend
-- Prix médian au m² et écart interquartile, par année et type de bien
SELECT annee, type_bien, ROUND(median(prix_m2)) AS med,
       ROUND(quantile_cont(prix_m2, 0.25)) AS q1, ROUND(quantile_cont(prix_m2, 0.75)) AS q3,
       COUNT(*) AS n
FROM od_dvf JOIN od_commune USING (code_insee)
WHERE $region = 'ALL' OR region = $region
GROUP BY 1, 2 ORDER BY 1, 2;

-- name: prix_box
-- Distribution du prix au m² 2023-2025 par commune (P10, Q1, médiane, Q3, P90)
WITH f AS (
    SELECT c.nom, d.prix_m2 FROM od_dvf d JOIN od_commune c USING (code_insee)
    WHERE d.annee BETWEEN 2023 AND 2025 AND ($region = 'ALL' OR c.region = $region)
)
SELECT nom, COUNT(*) AS n,
       list_transform(quantile_cont(prix_m2, [0.1, 0.25, 0.5, 0.75, 0.9]), lambda x: ROUND(x)) AS q
FROM f GROUP BY nom HAVING COUNT(*) >= 30
ORDER BY q[3] DESC LIMIT 12;

-- name: prix_evol
-- Évolution du prix médian au m² : 2016-2018 -> 2023-2025
SELECT nom, region, evol_prix_pct, prix_m2, n_ventes
FROM v_commune_features
WHERE n_ventes >= 30 AND evol_prix_pct IS NOT NULL AND ($region = 'ALL' OR region = $region)
ORDER BY evol_prix_pct DESC;

-- name: acc_heatmap
-- Accidents par jour de semaine x heure
SELECT dow, heure, COUNT(*) AS n
FROM od_accident JOIN od_commune USING (code_insee)
WHERE heure IS NOT NULL AND ($region = 'ALL' OR region = $region)
GROUP BY 1, 2 ORDER BY 1, 2;

-- name: acc_gravite
-- Accidents par année et gravité maximale (calculée au chargement)
SELECT annee, gravite, COUNT(*) AS n
FROM od_accident JOIN od_commune USING (code_insee)
WHERE $region = 'ALL' OR region = $region
GROUP BY 1, 2 ORDER BY 1, 2;

-- name: permis_trend
-- Logements autorisés par an : individuel, collectif, dont prêt locatif social
SELECT annee, SUM(lgt_ind) AS individuel, SUM(lgt_col) AS collectif, SUM(lgt_social) AS dont_social
FROM od_permis JOIN od_commune USING (code_insee)
WHERE $region = 'ALL' OR region = $region
GROUP BY 1 ORDER BY 1;

-- name: corr_matrix
-- Corrélations de Pearson et de Spearman (sur les rangs) entre indicateurs communaux, paires complètes
WITH long AS (
    UNPIVOT (
        SELECT code_insee,
               CAST(prix_m2 AS DOUBLE) AS prix_m2, CAST(evol_prix_pct AS DOUBLE) AS evol_prix_pct,
               CAST(revenu_median AS DOUBLE) AS revenu_median, CAST(taux_pauvrete AS DOUBLE) AS taux_pauvrete,
               CAST(gini AS DOUBLE) AS gini, CAST(densite AS DOUBLE) AS densite,
               CAST(croissance_pop_pct AS DOUBLE) AS croissance_pop_pct,
               CAST(chomeurs_pour_100hab AS DOUBLE) AS chomeurs_pour_100hab,
               CAST(logements_pour_1000hab AS DOUBLE) AS logements_pour_1000hab,
               CAST(accidents_pour_1000hab AS DOUBLE) AS accidents_pour_1000hab
        FROM v_commune_features
    ) ON COLUMNS(* EXCLUDE code_insee) INTO NAME var VALUE val
), ranked AS (
    SELECT *, RANK() OVER (PARTITION BY var ORDER BY val) AS rk FROM long
)
SELECT a.var AS x, b.var AS y,
       ROUND(corr(a.val, b.val), 2) AS pearson,
       ROUND(corr(a.rk, b.rk), 2) AS spearman,
       COUNT(*) AS n
FROM ranked a JOIN ranked b USING (code_insee)
GROUP BY 1, 2;

-- name: features
-- Table des indicateurs par commune (source de la matrice)
SELECT * FROM v_commune_features ORDER BY pop_2016 DESC;

-- name: pluie_accidents
-- Accidents/jour dans le Nord (communes proches de la station de Gillot) selon la pluie du jour
WITH days AS (
    SELECT jour, pluie_mm FROM od_meteo_jour
    WHERE nb_obs >= 6 AND jour BETWEEN (SELECT MIN(jour) FROM od_accident) AND (SELECT MAX(jour) FROM od_accident)
), acc AS (
    SELECT jour, COUNT(*) AS n FROM od_accident
    WHERE code_insee IN ('97411', '97418', '97420') GROUP BY 1
), j AS (
    SELECT d.jour, d.pluie_mm, COALESCE(a.n, 0) AS n,
           CASE WHEN d.pluie_mm < 0.2 THEN 'Sec (< 0,2 mm)'
                WHEN d.pluie_mm < 5 THEN 'Faible (0,2-5 mm)'
                WHEN d.pluie_mm < 20 THEN 'Modérée (5-20 mm)'
                ELSE 'Forte (≥ 20 mm)' END AS classe,
           CASE WHEN d.pluie_mm < 0.2 THEN 1 WHEN d.pluie_mm < 5 THEN 2 WHEN d.pluie_mm < 20 THEN 3 ELSE 4 END AS ordre
    FROM days d LEFT JOIN acc a USING (jour)
)
SELECT classe, ordre, COUNT(*) AS jours, SUM(n) AS accidents,
       ROUND(AVG(n), 3) AS acc_par_jour,
       ROUND(1.96 * STDDEV_SAMP(n) / SQRT(COUNT(*)), 3) AS ic95,
       ROUND(AVG(n) / (SELECT AVG(n) FROM j WHERE ordre = 1), 2) AS risque_relatif,
       (SELECT ROUND(corr(pluie_mm, n), 3) FROM j) AS corr_jour
FROM j GROUP BY classe, ordre ORDER BY ordre;

-- name: chomage_index
-- Demandeurs d'emploi par micro-région, moyenne mobile 3 mois, indice base 100 au premier mois
WITH s AS (
    SELECT c.region, ch.mois, SUM(ch.inscrits) AS v
    FROM od_chomage ch JOIN od_commune c USING (code_insee) GROUP BY 1, 2
), sm AS (
    SELECT region, mois, v,
           AVG(v) OVER (PARTITION BY region ORDER BY mois ROWS BETWEEN 2 PRECEDING AND CURRENT ROW) AS v3
    FROM s
)
SELECT region, mois, v AS inscrits,
       ROUND(100 * v3 / FIRST_VALUE(v3) OVER (PARTITION BY region ORDER BY mois), 1) AS indice
FROM sm ORDER BY region, mois;

-- name: climat_kpis
-- Chiffres clés du réseau Météo-France : stations, ancienneté, record de pluie en 24 h
WITH rec AS (
    SELECT m.station, m.alti, m.annee, m.mois, m.jour_max, m.pluie_max_jour, c.nom AS cyclone
    FROM od_meteo_mens m LEFT JOIN od_cyclone c USING (annee, mois)
    WHERE m.pluie_max_jour IS NOT NULL ORDER BY m.pluie_max_jour DESC LIMIT 1
)
SELECT (SELECT COUNT(*) FROM od_station) AS stations,
       (SELECT COUNT(*) FROM v_station_normales) AS stations_normales,
       (SELECT MIN(annee) FROM od_meteo_mens) AS debut,
       (SELECT COUNT(*) FROM od_meteo_mens) AS releves,
       rec.station AS record_station, rec.alti AS record_alti, rec.pluie_max_jour AS record_mm,
       rec.jour_max AS record_jour, rec.mois AS record_mois, rec.annee AS record_annee, rec.cyclone AS record_cyclone
FROM rec;

-- name: stations
-- Normales 1991-2020 par station + régressions sur l'altitude (gradient thermique, pluie par exposition)
SELECT station, lat, lon, alti, exposition, azimut, pluie_normale, annees_pluie, t_normale, annees_t,
       ROUND(100 * regr_slope(t_normale, alti) OVER (), 2) AS gradient_100m,
       ROUND(regr_intercept(t_normale, alti) OVER (), 2) AS t_niveau_mer,
       ROUND(regr_r2(t_normale, alti) OVER (), 3) AS r2_temp,
       regr_count(t_normale, alti) OVER () AS n_temp,
       ROUND(corr(pluie_normale, alti) OVER (PARTITION BY exposition), 2) AS r_pluie_alti,
       ROUND(median(pluie_normale) OVER (PARTITION BY exposition)) AS pluie_mediane_expo
FROM v_station_normales
ORDER BY pluie_normale DESC;

-- name: rechauffement
-- Anomalie de température annuelle vs 1981-2010 : moyenne des écarts de chaque station à sa propre
-- référence (stations à années complètes), moyenne glissante 10 ans et tendance linéaire par décennie
WITH a AS (
    SELECT poste, annee, AVG(t_moy) AS t FROM od_meteo_mens
    WHERE t_moy IS NOT NULL GROUP BY poste, annee HAVING COUNT(*) = 12
), ref AS (
    SELECT poste, AVG(t) AS tref FROM a WHERE annee BETWEEN 1981 AND 2010
    GROUP BY poste HAVING COUNT(*) >= 20
), an AS (
    SELECT annee, AVG(t - tref) AS anomalie, COUNT(*) AS stations
    FROM a JOIN ref USING (poste) GROUP BY annee HAVING COUNT(*) >= 5
)
SELECT annee, ROUND(anomalie, 2) AS anomalie, stations,
       CASE WHEN COUNT(*) OVER w10 = 10 THEN ROUND(AVG(anomalie) OVER w10, 2) END AS moy_10ans,  -- fenêtre complète seulement
       ROUND(10 * regr_slope(anomalie, annee) OVER (), 3) AS tendance_decennie,
       ROUND(regr_r2(anomalie, annee) OVER (), 2) AS r2
FROM an
WINDOW w10 AS (ORDER BY annee ROWS BETWEEN 9 PRECEDING AND CURRENT ROW)
ORDER BY annee;

-- name: pluie_annuelle
-- Pluie annuelle de l'île en % de la normale 1991-2020 (moyenne des écarts par station), cyclones de l'année
WITH a AS (
    SELECT poste, annee, SUM(pluie_mm) AS p FROM od_meteo_mens
    WHERE pluie_mm IS NOT NULL GROUP BY poste, annee HAVING COUNT(*) = 12
), ref AS (
    SELECT poste, AVG(p) AS pref FROM a WHERE annee BETWEEN 1991 AND 2020
    GROUP BY poste HAVING COUNT(*) >= 20
), an AS (
    SELECT annee, AVG(100 * (p / pref - 1)) AS ecart_pct, COUNT(*) AS stations
    FROM a JOIN ref USING (poste) WHERE annee >= 1960 GROUP BY annee HAVING COUNT(*) >= 10
)
SELECT an.annee, ROUND(ecart_pct, 1) AS ecart_pct, stations,
       (SELECT string_agg(nom, ', ' ORDER BY mois) FROM od_cyclone c WHERE c.annee = an.annee) AS cyclones,
       RANK() OVER (ORDER BY ecart_pct DESC) AS rang_humide
FROM an ORDER BY annee;

-- name: regimes
-- Régime saisonnier : part de chaque mois dans le cumul annuel (normales 1991-2020) pour 18 stations
-- réparties sur tout l'éventail des pluviométries (NTILE), de la plus arrosée à la plus sèche
WITH ranked AS (
    SELECT poste, station, exposition, alti, pluie_normale,
           NTILE(18) OVER (ORDER BY pluie_normale DESC) AS tranche
    FROM v_station_normales WHERE annees_pluie >= 25
), top AS (
    SELECT DISTINCT ON (tranche) poste, station, exposition, alti, pluie_normale
    FROM ranked ORDER BY tranche, pluie_normale DESC
), mens AS (
    SELECT poste, mois, AVG(pluie_mm) AS pluie FROM od_meteo_mens
    WHERE annee BETWEEN 1991 AND 2020 AND pluie_mm IS NOT NULL GROUP BY poste, mois
)
SELECT t.station, t.exposition, t.alti, t.pluie_normale, m.mois, ROUND(m.pluie) AS pluie,
       ROUND(100 * m.pluie / t.pluie_normale, 1) AS part_annuelle_pct
FROM top t JOIN mens m USING (poste)
ORDER BY t.pluie_normale DESC, m.mois;

-- name: records_pluie
-- Les 15 plus fortes pluies en 24 h du réseau depuis 1950, rapprochées des cyclones du même mois
SELECT m.station, m.alti, m.annee, m.mois, m.jour_max AS jour, m.pluie_max_jour AS pluie_24h,
       m.pluie_mm AS pluie_du_mois, c.nom AS cyclone
FROM od_meteo_mens m LEFT JOIN od_cyclone c USING (annee, mois)
WHERE m.pluie_max_jour IS NOT NULL
ORDER BY m.pluie_max_jour DESC LIMIT 15;
