-- Francophonie canadienne : chargement + nettoyage des 4 tableaux historiques de Statistique Canada (1951-2021).
-- {raw} est remplacé par le dossier data/raw. fr_geo (codes et noms français) est créée par l'adaptateur depuis le domaine.

-- Les 4 tableaux bruts empilés au format long : une ligne = une source, un recensement, une géographie, une catégorie, une mesure
CREATE OR REPLACE TABLE fr_brut AS
SELECT 'langue_maternelle' AS source, "REF_DATE"::INT AS an, "GEO" AS geo_brut, "Mother tongue" AS categorie,
       "Statistics" AS mesure, "Multiple responses" AS reponses, "VALUE"::DOUBLE AS valeur
FROM read_csv('{raw}/statcan_langue_maternelle.csv', header = true, all_varchar = true)
UNION ALL
SELECT 'plos', "REF_DATE"::INT, "GEO", "First official language spoken", "Statistics", "Multiple responses", "VALUE"::DOUBLE
FROM read_csv('{raw}/statcan_plos.csv', header = true, all_varchar = true)
UNION ALL
SELECT 'connaissance', "REF_DATE"::INT, "GEO", "Knowledge of official languages", "Statistics", NULL, "VALUE"::DOUBLE
FROM read_csv('{raw}/statcan_connaissance.csv', header = true, all_varchar = true)
UNION ALL
SELECT 'langue_maison', "REF_DATE"::INT, "GEO", "Language spoken most often at home", "Statistics", "Multiple responses", "VALUE"::DOUBLE
FROM read_csv('{raw}/statcan_langue_maison.csv', header = true, all_varchar = true);

-- Effectifs nettoyés : libellé géographique sans espaces parasites (« Saskatchewan  » dans un tableau), effectifs seulement
-- (les pourcentages publiés servent au contrôle, pas au calcul), réponses multiples « réparties » pour comparer 1951 et 2021
CREATE OR REPLACE TABLE fr_langue AS
SELECT b.source, b.an, g.code, b.categorie,
       CASE WHEN b.categorie LIKE 'Total%' THEN 'total'
            WHEN b.categorie IN ('French', 'French only') THEN 'fr'
            WHEN b.categorie IN ('English', 'English only') THEN 'en'
            WHEN b.categorie = 'English and French' THEN 'en_fr'
            ELSE 'autre' END AS cle,
       b.valeur AS n
FROM fr_brut b
JOIN fr_geo g ON g.geo_en = trim(b.geo_brut)
WHERE b.mesure = 'Number' AND coalesce(b.reponses, 'Distributed') = 'Distributed' AND b.valeur IS NOT NULL;

-- Indicateurs par géographie et recensement : parts recalculées depuis les effectifs, indice de continuité linguistique
CREATE OR REPLACE TABLE fr_indicateurs AS
WITH p AS (
    PIVOT (SELECT an, code, source || '_' || cle AS k, n FROM fr_langue
           WHERE (source, cle) IN (('langue_maternelle', 'total'), ('langue_maternelle', 'fr'), ('connaissance', 'en_fr'),
                                   ('connaissance', 'fr'), ('langue_maison', 'fr'), ('plos', 'fr')))
    ON k USING sum(n)
)
SELECT p.an, p.code, g.nom, g.type,
       p.langue_maternelle_total AS population,
       p.langue_maternelle_fr AS mat_fr,
       round(100 * p.langue_maternelle_fr / p.langue_maternelle_total, 2) AS mat_fr_pct,
       p.connaissance_en_fr AS bilingues,
       round(100 * p.connaissance_en_fr / p.langue_maternelle_total, 2) AS bilingues_pct,
       round(100 * p.connaissance_fr / p.langue_maternelle_total, 2) AS francais_seul_pct,
       p.langue_maison_fr AS maison_fr,
       round(100 * p.langue_maison_fr / p.langue_maternelle_total, 2) AS maison_fr_pct,
       p.plos_fr AS plos_fr,
       round(100 * p.plos_fr / p.langue_maternelle_total, 2) AS plos_fr_pct,
       round(p.langue_maison_fr / nullif(p.langue_maternelle_fr, 0), 3) AS continuite
FROM p JOIN fr_geo g USING (code);

-- Contrôle : chaque part recalculée confrontée à celle que publie Statistique Canada (écart en points)
CREATE OR REPLACE TABLE fr_controle AS
WITH publie AS (
    SELECT b.source, b.an, g.code, b.valeur AS pct_publie
    FROM fr_brut b JOIN fr_geo g ON g.geo_en = trim(b.geo_brut)
    WHERE b.mesure = 'Percentage' AND coalesce(b.reponses, 'Distributed') = 'Distributed'
      AND b.categorie IN ('French', 'English and French')
      AND (b.source, b.categorie) IN (('langue_maternelle', 'French'), ('connaissance', 'English and French'))
)
SELECT p.source, count(*) AS comparaisons,
       round(max(abs(p.pct_publie - CASE p.source WHEN 'langue_maternelle' THEN i.mat_fr_pct ELSE i.bilingues_pct END)), 2) AS ecart_max_points
FROM publie p JOIN fr_indicateurs i USING (an, code)
GROUP BY p.source;

-- Immigration francophone (IRCC) : résidents permanents par mois et par ville de destination, francophones et tous profils.
-- Les effectifs sont arrondis à 5 et les cellules de 1 à 4 personnes masquées (« -- ») : gardées, mais à NULL
CREATE OR REPLACE TABLE fr_ircc AS
SELECT 'francophones' AS profil, "EN_YEAR"::INT AS annee, "EN_MONTH" AS mois, "EN_PROVINCE_TERRITORY" AS province,
       "EN_CENSUS_METROPOLITAN_AREA" AS rmr, try_cast(replace("TOTAL", ',', '') AS INT) AS n, "TOTAL" = '--' AS masque
FROM read_csv('{raw}/ircc_francophones_rmr.csv', delim = '\t', header = true, all_varchar = true)
UNION ALL
SELECT 'tous', "EN_YEAR"::INT, "EN_MONTH", "EN_PROVINCE_TERRITORY", "EN_CENSUS_METROPOLITAN_AREA",
       try_cast(replace("TOTAL", ',', '') AS INT), "TOTAL" = '--'
FROM read_csv('{raw}/ircc_rp_rmr.csv', delim = '\t', header = true, all_varchar = true);

-- Indicateurs des villes comparées : la valeur la plus récente de chaque source (arg_max sur l'année), au niveau
-- géographique que la source publie (ville ou, à défaut, province : colonne niveau_revenu). Francophonie : recensement
-- 2021 par ville (98-10-0192-01, cellules extraites par l'API de Statistique Canada)
CREATE OR REPLACE TABLE fr_villes AS
WITH
mpc AS (SELECT GEO, arg_max("VALUE"::DOUBLE, REF_DATE) AS v, max(REF_DATE) AS an
        FROM read_csv('{raw}/statcan_mbm.csv.gz', all_varchar = true)
        WHERE "Base year" = '2023 base' AND "Dollar concept" = 'Current dollars' AND Component = 'Total threshold' AND "VALUE" IS NOT NULL
        GROUP BY GEO),
loyer AS (SELECT GEO, arg_max("VALUE"::DOUBLE, REF_DATE) AS v, max(REF_DATE) AS an
          FROM read_csv('{raw}/statcan_loyers.csv.gz', all_varchar = true)
          WHERE "Type of unit" = 'Two bedroom units' AND "Type of structure" = 'Row and apartment structures of three units and over'
            AND "VALUE" IS NOT NULL
          GROUP BY GEO),
revenu AS (SELECT GEO, arg_max("VALUE"::DOUBLE, REF_DATE) AS v, max(REF_DATE) AS an
           FROM read_csv('{raw}/statcan_revenus.csv.gz', all_varchar = true)
           WHERE "Income concept" = 'Median after-tax income' AND "Economic family type" = 'Couples with children' AND "VALUE" IS NOT NULL
           GROUP BY GEO),
crime AS (SELECT GEO, arg_max("VALUE"::DOUBLE, REF_DATE) AS v, max(REF_DATE) AS an
          FROM read_csv('{raw}/statcan_criminalite.csv.gz', all_varchar = true)
          WHERE "Statistics" = 'Crime severity index' AND "VALUE" IS NOT NULL
          GROUP BY GEO),
chomage AS (SELECT GEO, arg_max("VALUE"::DOUBLE, REF_DATE) AS v, max(REF_DATE) AS an
            FROM read_csv('{raw}/statcan_chomage_rmr.csv.gz', all_varchar = true)
            WHERE "Labour force characteristics" = 'Unemployment rate' AND Sex = 'Both sexes' AND "Age group" = '15 years and over'
              AND "VALUE" IS NOT NULL
            GROUP BY GEO),
satisfaction AS (SELECT GEO, arg_max("VALUE"::DOUBLE, REF_DATE) AS v, max(REF_DATE) AS an
                 FROM read_csv('{raw}/statcan_satisfaction.csv.gz', all_varchar = true)
                 WHERE Gender = 'Total, all persons' AND Indicators = 'Life satisfaction rating of 8, 9 or 10'
                   AND "Statistics" = 'Percentage of persons' AND "VALUE" IS NOT NULL
                 GROUP BY GEO),
arrivees AS (SELECT rmr, annee, sum(n) FILTER (WHERE profil = 'francophones') AS fr, sum(n) FILTER (WHERE profil = 'tous') AS tous
             FROM fr_ircc WHERE annee = (SELECT max(annee) FROM fr_ircc WHERE mois = 'Dec') GROUP BY rmr, annee),
recensement AS (PIVOT (SELECT geo, mesure, valeur::DOUBLE AS valeur
                        FROM read_csv('{raw}/statcan_recensement_villes.csv', header = true, all_varchar = true))
                 ON mesure USING sum(valeur))
SELECT v.code, v.nom, v.province,
       round(100 * r.plop_fr / r.population, 1) AS plop_fr_pct,
       round(100 * r.plop_fr_maison_fr / r.plop_fr, 1) AS maison_fr_pct,
       round(100 * r.enfants_plop_fr / r.enfants, 1) AS enfants_fr_pct,
       r.plop_fr AS francophones,
       a.fr AS arrivees_fr, a.tous AS arrivees, round(100 * a.fr / a.tous, 1) AS part_fr_arrivees, a.annee AS an_arrivees,
       l.v AS loyer, l.an AS an_loyer,
       m.v AS mpc, m.an AS an_mpc, CASE WHEN v.geo_mpc LIKE '%population%' THEN 'taille de ville' ELSE 'ville' END AS niveau_mpc,
       rv.v AS revenu, rv.an AS an_revenu, CASE WHEN v.geo_revenu = g.geo_en THEN 'province' ELSE 'ville' END AS niveau_revenu,
       round(rv.v / m.v, 2) AS pouvoir_achat,
       round(100 * 12 * l.v / rv.v, 1) AS loyer_part_revenu,
       c.v AS chomage, c.an AS an_chomage,
       cr.v AS criminalite, cr.an AS an_criminalite,
       s.v AS satisfaction, s.an AS an_satisfaction
FROM fr_ville v
JOIN fr_geo g ON g.code = v.province
LEFT JOIN recensement r ON r.geo = v.geo_recensement
LEFT JOIN arrivees a ON a.rmr = v.rmr_ircc
LEFT JOIN loyer l ON l.GEO = v.geo_loyer
LEFT JOIN mpc m ON m.GEO = v.geo_mpc
LEFT JOIN revenu rv ON rv.GEO = v.geo_revenu
LEFT JOIN chomage c ON c.GEO = v.geo_chomage
LEFT JOIN crime cr ON cr.GEO = v.geo_crime
LEFT JOIN satisfaction s ON s.GEO = g.geo_en;

-- Notes de 0 à 100 par indicateur : min-max sur les villes comparées, inversé quand « moins, c'est mieux » (UNPIVOT + fenêtres)
CREATE OR REPLACE TABLE fr_villes_notes AS
WITH longue AS (
    UNPIVOT (SELECT code, nom, plop_fr_pct, maison_fr_pct, enfants_fr_pct, part_fr_arrivees, loyer, mpc, pouvoir_achat, chomage, revenu,
                    criminalite, satisfaction FROM fr_villes)
    ON COLUMNS(* EXCLUDE (code, nom)) INTO NAME indicateur VALUE valeur
)
SELECT l.code, l.nom, p.pilier, l.indicateur, p.libelle, p.sens, l.valeur,
       round(100 * CASE WHEN p.sens > 0 THEN l.valeur - min(l.valeur) OVER w ELSE max(l.valeur) OVER w - l.valeur END
                  / nullif(max(l.valeur) OVER w - min(l.valeur) OVER w, 0), 1) AS note
FROM longue l JOIN fr_pilier p USING (indicateur)
WINDOW w AS (PARTITION BY l.indicateur);
