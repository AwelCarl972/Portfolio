-- name: en_kpis
-- Chiffres clés : la bascule entre 2021 (dernière année « d'avant ») et la dernière année publiée
WITH d AS (SELECT max(annee) AS an FROM en_part)
SELECT (SELECT an FROM d) AS an,
       (SELECT part_enr FROM en_part WHERE annee = (SELECT an FROM d)) AS part_enr,
       (SELECT part_enr FROM en_part WHERE annee = 2021) AS part_enr_2021,
       (SELECT kt FROM en_co2 WHERE annee = (SELECT an FROM d)) AS co2_kt,
       (SELECT kt FROM en_co2 WHERE annee = 2021) AS co2_kt_2021,
       (SELECT sum(mwh) / 1000 FROM en_annuel WHERE annee = (SELECT an FROM d) AND filiere = 'charbon') AS charbon_gwh,
       (SELECT sum(mwh) / 1000 FROM en_annuel WHERE annee = 2020 AND filiere = 'charbon') AS charbon_gwh_2020,
       (SELECT total_mwh / 1e6 FROM en_part WHERE annee = (SELECT an FROM d)) AS total_twh;

-- name: en_mix
-- Production annuelle par filière, en GWh (bilan validé d'EDF)
SELECT annee, filiere, libelle, renouvelable, round(mwh / 1000, 1) AS gwh,
       round(100 * mwh / sum(mwh) OVER (PARTITION BY annee), 1) AS part_pct
FROM en_annuel
ORDER BY annee, ordre;

-- name: en_part_q
-- Part renouvelable par année : recalculée et publiée par EDF
SELECT annee, round(total_mwh / 1000) AS total_gwh, round(part_enr, 1) AS part_enr,
       round(part_enr_publiee, 1) AS part_enr_publiee
FROM en_part ORDER BY annee;

-- name: en_co2_q
-- Émissions directes de CO2 de la production d'électricité, et variation sur un an
SELECT annee, kt, round(100 * (kt / LAG(kt) OVER (ORDER BY annee) - 1), 1) AS variation_pct
FROM en_co2 ORDER BY annee;

-- name: en_journee
-- Une journée moyenne en 2023, heure par heure (heure locale) : qui produit quand
SELECT hour(heure) AS h, f.libelle, f.ordre,
       round(avg(greatest(CASE f.colonne
           WHEN 'thermique_mw' THEN thermique_mw WHEN 'bagasse_charbon_mw' THEN bagasse_charbon_mw
           WHEN 'hydraulique_mw' THEN hydraulique_mw WHEN 'photovoltaique_mw' THEN photovoltaique_mw
           WHEN 'eolien_mw' THEN eolien_mw ELSE bioenergies_mw END, 0)), 1) AS mw
FROM en_horaire CROSS JOIN en_filiere_h f
WHERE year(heure) = 2023
GROUP BY ALL
ORDER BY h, f.ordre;

-- name: en_saisons
-- Appel de puissance moyen par heure, été contre hiver austral (2019-2024)
SELECT hour(heure) AS h,
       round(avg(total_mw) FILTER (WHERE month(heure) IN (12, 1, 2, 3)), 1) AS ete_mw,
       round(avg(total_mw) FILTER (WHERE month(heure) IN (6, 7, 8, 9)), 1) AS hiver_mw
FROM en_horaire
GROUP BY 1 ORDER BY 1;

-- name: en_pointe
-- L'heure la plus chargée de chaque année, et à quel moment de la journée elle tombe
SELECT year(heure) AS annee, arg_max(heure, total_mw) AS heure_pointe, round(max(total_mw)) AS pointe_mw,
       round(avg(total_mw)) AS moyenne_mw
FROM en_horaire GROUP BY 1 ORDER BY 1;

-- name: en_communes
-- Consommation résidentielle moyenne par compteur, par commune (dernière année publiée)
WITH d AS (SELECT max(annee) AS an FROM en_conso)
SELECT annee, nom, code_insee, hauts, round(mwh) AS mwh, compteurs,
       round(1000 * mwh / compteurs) AS kwh_par_foyer,
       RANK() OVER (ORDER BY mwh / compteurs DESC) AS rang
FROM en_conso
WHERE secteur = 'Résidentiel' AND annee = (SELECT an FROM d) AND compteurs > 0
ORDER BY kwh_par_foyer DESC;

-- name: en_secteurs
-- Qui consomme l'électricité de l'île : répartition par secteur, dernière année publiée
WITH d AS (SELECT max(annee) AS an FROM en_conso)
SELECT secteur, round(sum(mwh) / 1000) AS gwh, round(100 * sum(mwh) / sum(sum(mwh)) OVER (), 1) AS part_pct
FROM en_conso WHERE annee = (SELECT an FROM d)
GROUP BY 1 ORDER BY gwh DESC;

-- name: en_qualite
-- Contrôles : heures complètes après correction des fuseaux, totaux horaires contre bilan annuel, part recalculée
SELECT 'Heures distinctes après correction (attendu : ' || (date_diff('hour', min(heure), max(heure)) + 1) || ')' AS etape,
       count(DISTINCT heure)::DOUBLE AS valeur FROM en_horaire
UNION ALL
SELECT 'Horodatages en double dans le fichier brut (une heure de juin 2021 manque en face)',
       count(*) - count(DISTINCT heure)
FROM en_horaire_brut
UNION ALL
SELECT 'Décalages horaires annoncés dans le fichier', count(DISTINCT decalage_annonce) FROM en_horaire
UNION ALL
SELECT 'Heures « estimées » (non validées)', count(*) FILTER (WHERE statut <> 'Validé') FROM en_horaire
UNION ALL
SELECT 'Écart max. total horaire / bilan annuel (%)',
       round(max(abs(100 * (h.mwh / p.total_mwh - 1))), 1)
FROM (SELECT year(heure) AS annee, sum(total_mw) AS mwh FROM en_horaire GROUP BY 1) h JOIN en_part p USING (annee)
UNION ALL
SELECT 'Écart max. part renouvelable recalculée / publiée (pts)', round(max(abs(part_enr - part_enr_publiee)), 2)
FROM en_part
UNION ALL
SELECT 'Communes reconnues dans la consommation', count(DISTINCT code_insee) FROM en_conso;
