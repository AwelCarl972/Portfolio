-- Chargement + nettoyage des jeux open data (CSV bruts -> tables analytiques).
-- {raw} est remplacé par le dossier des CSV ; od_micro_region est alimentée par le domaine.

-- Populations légales INSEE, tous millésimes (2006-2016)
CREATE OR REPLACE TABLE od_population AS
SELECT CAST(code_insee AS VARCHAR) AS code_insee, nom_de_la_commune AS nom,
       annee_recensement AS annee, population_municipale AS pop, superficie
FROM read_csv('{raw}/population.csv', delim = ';', header = true);

-- Référentiel communal : population 2016 et 2006, micro-région (issue du domaine), libellés harmonisés
CREATE OR REPLACE TABLE od_commune AS
SELECT p.code_insee, replace(p.nom, 'L'' É', 'L''É') AS nom, m.region, p.superficie,
       p.pop AS pop_2016,
       (SELECT pop FROM od_population o WHERE o.code_insee = p.code_insee AND o.annee = 2006) AS pop_2006
FROM od_population p JOIN od_micro_region m USING (code_insee)
WHERE p.annee = 2016;

-- DVF : une seule commune par mutation, surfaces et prix au m² hors valeurs aberrantes
CREATE OR REPLACE TABLE od_dvf AS
SELECT datemut AS date_mut, year(datemut) AS annee, CAST(l_codinsee AS VARCHAR) AS code_insee,
       CASE libtypbien WHEN 'UNE MAISON' THEN 'Maison' ELSE 'Appartement' END AS type_bien,
       valeurfonc AS prix, sbati AS surface, valeurfonc / sbati AS prix_m2
FROM read_csv('{raw}/dvf.csv', delim = ';', header = true, types = {'l_codinsee': 'VARCHAR'})
WHERE length(l_codinsee) = 5 AND sbati BETWEEN 15 AND 400
  AND valeurfonc / sbati BETWEEN 500 AND 12000;

-- Revenus INSEE 2014 agrégés de l'IRIS à la commune (moyenne pondérée par la population des ménages)
CREATE OR REPLACE TABLE od_revenus AS
SELECT CAST(com AS VARCHAR) AS code_insee,
       SUM(dec_med14 * pop_menages_en_2014_princ) / SUM(pop_menages_en_2014_princ) AS revenu_median,
       SUM(dec_tp6014 * pop_menages_en_2014_princ) / SUM(pop_menages_en_2014_princ) AS taux_pauvrete,
       SUM(dec_gi14 * pop_menages_en_2014_princ) / SUM(pop_menages_en_2014_princ) AS gini,
       COUNT(*) AS nb_iris
FROM read_csv('{raw}/revenus_iris.csv', delim = ';', header = true)
WHERE dec_med14 IS NOT NULL AND dec_med14 > 0
GROUP BY com;

-- Demandeurs d'emploi inscrits en fin de mois, par commune
CREATE OR REPLACE TABLE od_chomage AS
SELECT CAST(code_commune_insee AS VARCHAR) AS code_insee, date AS mois, inscrits
FROM read_csv('{raw}/chomage.csv', delim = ';', header = true);

-- Permis de construire : dédoublonnés par numéro, 2023 exclu (millésime incomplet dans la source)
CREATE OR REPLACE TABLE od_permis AS
SELECT DISTINCT ON (num_dau) CAST(comm AS VARCHAR) AS code_insee, date_reelle_autorisation AS date_aut,
       year(date_reelle_autorisation) AS annee, nb_lgt_tot_crees AS lgt_tot, nb_lgt_ind_crees AS lgt_ind,
       nb_lgt_col_crees AS lgt_col, nb_lgt_pret_loc_social AS lgt_social
FROM read_csv('{raw}/permis.csv', delim = ';', header = true)
WHERE date_reelle_autorisation IS NOT NULL
  AND year(date_reelle_autorisation) <= 2022;

-- Accidents : codes commune hétérogènes ('97411', '411', '011') -> INSEE ; gravité max par accident
CREATE OR REPLACE TABLE od_accident AS
SELECT num_acc, CAST(timezone('Indian/Reunion', datetime) AS DATE) AS jour, an AS annee,
       hour(hrmn) AS heure, isodow(CAST(timezone('Indian/Reunion', datetime) AS DATE)) AS dow,
       '974' || right(com, 2) AS code_insee, lum, atm, agg, catr,
       CASE WHEN grav LIKE '%Tué%' THEN 'Mortel'
            WHEN grav LIKE '%hospitalisé%' THEN 'Grave (hospitalisé)'
            ELSE 'Léger' END AS gravite
FROM read_csv('{raw}/accidents.csv', delim = ';', header = true, types = {'com': 'VARCHAR'});

-- Météo Gillot : tri-horaire -> journalier (heure locale UTC+4)
CREATE OR REPLACE TABLE od_meteo_jour AS
SELECT CAST(timezone('Indian/Reunion', date) AS DATE) AS jour,
       SUM(GREATEST(rr3, 0)) AS pluie_mm, AVG(tc) AS t_moy, AVG(u) AS humidite, MAX(raf10) AS rafale_ms,
       COUNT(*) AS nb_obs
FROM read_csv('{raw}/meteo_gillot.csv', delim = ';', header = true)
GROUP BY 1;

-- Indicateurs communaux : base de la matrice de corrélation
CREATE OR REPLACE VIEW v_commune_features AS
WITH prix AS (
    SELECT code_insee,
           median(prix_m2) FILTER (WHERE annee BETWEEN 2023 AND 2025) AS prix_m2,
           median(prix_m2) FILTER (WHERE annee BETWEEN 2016 AND 2018) AS prix_m2_old,
           COUNT(*) FILTER (WHERE annee BETWEEN 2023 AND 2025) AS n_ventes
    FROM od_dvf GROUP BY 1
), cho AS (
    SELECT code_insee, AVG(inscrits) AS inscrits FROM od_chomage
    WHERE year(mois) = 2022 GROUP BY 1
), per AS (
    SELECT code_insee, SUM(lgt_tot) / 6.0 AS lgt_an FROM od_permis
    WHERE annee BETWEEN 2017 AND 2022 GROUP BY 1
), acc AS (
    SELECT code_insee, COUNT(*) / 6.0 AS acc_an FROM od_accident
    WHERE annee BETWEEN 2019 AND 2024 GROUP BY 1
)
SELECT c.code_insee, c.nom, c.region, c.pop_2016,
       ROUND(p.prix_m2) AS prix_m2,
       ROUND(100 * (p.prix_m2 / p.prix_m2_old - 1), 1) AS evol_prix_pct,
       ROUND(r.revenu_median) AS revenu_median,
       ROUND(r.taux_pauvrete, 1) AS taux_pauvrete,
       ROUND(r.gini, 3) AS gini,
       ROUND(c.pop_2016 / c.superficie) AS densite,
       ROUND(100 * (c.pop_2016 / c.pop_2006 - 1), 1) AS croissance_pop_pct,
       ROUND(100 * cho.inscrits / c.pop_2016, 2) AS chomeurs_pour_100hab,
       ROUND(1000 * per.lgt_an / c.pop_2016, 2) AS logements_pour_1000hab,
       ROUND(1000 * acc.acc_an / c.pop_2016, 2) AS accidents_pour_1000hab,
       p.n_ventes
FROM od_commune c
LEFT JOIN prix p USING (code_insee)
LEFT JOIN od_revenus r USING (code_insee)
LEFT JOIN cho USING (code_insee)
LEFT JOIN per USING (code_insee)
LEFT JOIN acc USING (code_insee);

-- Météo-France : relevés mensuels de toutes les stations de La Réunion depuis 1950 (base climatologique)
CREATE OR REPLACE TABLE od_meteo_mens AS
SELECT NUM_POSTE AS poste, NOM_USUEL AS station, LAT AS lat, LON AS lon, ALTI AS alti,
       AAAAMM // 100 AS annee, AAAAMM % 100 AS mois,
       RR AS pluie_mm, RRAB AS pluie_max_jour, RRABDAT AS jour_max, NBJRR1 AS jours_pluie,
       TM AS t_moy, TX AS t_max_moy, TN AS t_min_moy, TXAB AS t_max_abs, TNAB AS t_min_abs
FROM read_csv(['{raw}/meteo_mens_1950_2024.csv.gz', '{raw}/meteo_mens_2025_2026.csv.gz'],
              delim = ';', header = true, union_by_name = true);

-- Stations : position, altitude et exposition aux alizés d'est (azimut depuis le Piton des Neiges)
CREATE OR REPLACE TABLE od_station AS
WITH s AS (
    SELECT poste, arg_max(station, annee) AS station, arg_max(lat, annee) AS lat, arg_max(lon, annee) AS lon,
           arg_max(alti, annee) AS alti, MIN(annee) AS debut, MAX(annee) AS fin
    FROM od_meteo_mens GROUP BY poste
)
SELECT *, CAST((degrees(atan2((lon - 55.48) * 0.933, lat + 21.10)) + 360) % 360 AS INTEGER) AS azimut,
       CASE WHEN (degrees(atan2((lon - 55.48) * 0.933, lat + 21.10)) + 360) % 360 BETWEEN 20 AND 160 THEN 'Au vent (est)'
            WHEN (degrees(atan2((lon - 55.48) * 0.933, lat + 21.10)) + 360) % 360 BETWEEN 200 AND 340 THEN 'Sous le vent (ouest)'
            ELSE 'Nord / Sud' END AS exposition
FROM s;

-- Normales 1991-2020 par station : années complètes (12 mois) uniquement, au moins 15 ans
CREATE OR REPLACE VIEW v_station_normales AS
WITH annuel AS (
    SELECT poste, annee, SUM(pluie_mm) AS pluie, COUNT(pluie_mm) AS nm, AVG(t_moy) AS t, COUNT(t_moy) AS nt
    FROM od_meteo_mens WHERE annee BETWEEN 1991 AND 2020 GROUP BY poste, annee
)
SELECT s.poste, s.station, s.lat, s.lon, s.alti, s.exposition, s.azimut,
       ROUND(AVG(pluie) FILTER (WHERE nm = 12)) AS pluie_normale,
       COUNT(*) FILTER (WHERE nm = 12) AS annees_pluie,
       ROUND(AVG(t) FILTER (WHERE nt = 12), 1) AS t_normale,
       COUNT(*) FILTER (WHERE nt = 12) AS annees_t
FROM annuel JOIN od_station s USING (poste)
GROUP BY ALL
HAVING COUNT(*) FILTER (WHERE nm = 12) >= 15;
