-- name: fr_kpis
-- Chiffres clés hors Québec : 1951 contre 2021 (langue maternelle), bilinguisme, transmission au Nouveau-Brunswick
SELECT
    max(mat_fr) FILTER (WHERE code = 'HQ' AND an = 2021) AS hq_mat_fr_2021,
    max(mat_fr) FILTER (WHERE code = 'HQ' AND an = 1951) AS hq_mat_fr_1951,
    max(mat_fr_pct) FILTER (WHERE code = 'HQ' AND an = 2021) AS hq_pct_2021,
    max(mat_fr_pct) FILTER (WHERE code = 'HQ' AND an = 1951) AS hq_pct_1951,
    max(plos_fr) FILTER (WHERE code = 'HQ' AND an = 2021) AS hq_plos_2021,
    max(bilingues_pct) FILTER (WHERE code = 'HQ' AND an = 2021) AS hq_bil_2021,
    max(bilingues_pct) FILTER (WHERE code = 'NB' AND an = 2021) AS nb_bil_2021,
    max(continuite) FILTER (WHERE code = 'NB' AND an = 2021) AS nb_cont_2021,
    max(continuite) FILTER (WHERE code = 'HQ' AND an = 2021) AS hq_cont_2021
FROM fr_indicateurs;

-- name: fr_paradoxe
-- Hors Québec : effectif francophone et population totale ramenés à 100 en 1951 (FIRST_VALUE sur fenêtre ordonnée)
SELECT an, mat_fr, population, mat_fr_pct,
       round(100 * mat_fr / FIRST_VALUE(mat_fr) OVER w, 1) AS indice_fr,
       round(100 * population / FIRST_VALUE(population) OVER w, 1) AS indice_pop
FROM fr_indicateurs
WHERE code = 'HQ'
WINDOW w AS (ORDER BY an)
ORDER BY an;

-- name: fr_haltere
-- Part de langue maternelle française par province hors Québec : premier et dernier recensement (arg_min / arg_max)
SELECT code, nom,
       arg_min(mat_fr_pct, an) AS pct_1951, arg_max(mat_fr_pct, an) AS pct_2021,
       round(arg_max(mat_fr_pct, an) - arg_min(mat_fr_pct, an), 1) AS ecart
FROM fr_indicateurs
WHERE type = 'province' AND code <> 'QC'
GROUP BY code, nom
ORDER BY pct_2021;

-- name: fr_series
-- Séries par province et recensement : langue maternelle, langue de la maison, 1re langue officielle, bilinguisme
SELECT code, nom, an, mat_fr_pct, maison_fr_pct, plos_fr_pct, bilingues_pct, mat_fr, continuite
FROM fr_indicateurs
WHERE type = 'province' OR code IN ('HQ', 'CA')
ORDER BY code, an;

-- name: fr_continuite
-- Indice de continuité (langue de la maison ÷ langue maternelle) : 1971 contre 2021, provinces hors Québec + ensemble
SELECT code, nom,
       max(continuite) FILTER (WHERE an = 1971) AS c_1971,
       max(continuite) FILTER (WHERE an = 2021) AS c_2021,
       max(mat_fr) FILTER (WHERE an = 2021) AS mat_fr_2021
FROM fr_indicateurs
WHERE (type = 'province' AND code <> 'QC') OR code = 'HQ'
GROUP BY code, nom
ORDER BY c_2021 DESC;

-- name: fr_ou
-- Où vivent les francophones hors Québec en 2021 (1re langue officielle parlée) : effectif, part du total hors Québec
-- (SUM sur fenêtre), part dans la province, et rang
SELECT code, nom, plos_fr, plos_fr_pct,
       round(100 * plos_fr / SUM(plos_fr) OVER (), 1) AS part_hq,
       RANK() OVER (ORDER BY plos_fr DESC) AS rang
FROM fr_indicateurs
WHERE an = 2021 AND type IN ('province', 'territoire') AND code NOT IN ('QC', 'NTNU')
ORDER BY plos_fr DESC;

-- name: fr_variations
-- Variation de l'effectif de langue maternelle française d'un recensement au suivant, en % (LAG par province)
SELECT code, nom, an, an_prec, round(100 * (mat_fr - prec) / prec, 1) AS variation_pct
FROM (
    SELECT code, nom, an, mat_fr,
           LAG(an) OVER (PARTITION BY code ORDER BY an) AS an_prec,
           LAG(mat_fr) OVER (PARTITION BY code ORDER BY an) AS prec
    FROM fr_indicateurs
    WHERE type = 'province' AND code <> 'QC'
)
WHERE prec IS NOT NULL
ORDER BY code, an;

-- name: fr_bilinguisme
-- Taux de bilinguisme anglais-français : Québec, Canada hors Québec, Nouveau-Brunswick, Canada
SELECT code, nom, an, bilingues_pct
FROM fr_indicateurs
WHERE code IN ('QC', 'HQ', 'NB', 'CA')
ORDER BY code, an;

-- name: fr_qualite
-- Du brut au retenu, et écart maximal entre les parts recalculées et celles publiées par Statistique Canada
SELECT 'Lignes brutes (4 tableaux)' AS etape, (SELECT count(*) FROM fr_brut)::DOUBLE AS valeur
UNION ALL SELECT 'Effectifs retenus (réponses réparties)', (SELECT count(*) FROM fr_langue)
UNION ALL SELECT 'Libellés géographiques à nettoyer (espaces)', (SELECT count(*) FROM fr_brut WHERE geo_brut <> trim(geo_brut))
UNION ALL SELECT 'Indicateurs calculés (géographie × recensement)', (SELECT count(*) FROM fr_indicateurs)
UNION ALL SELECT 'Écart max. recalcul / publié, langue maternelle (points)', (SELECT ecart_max_points FROM fr_controle WHERE source = 'langue_maternelle')
UNION ALL SELECT 'Écart max. recalcul / publié, bilinguisme (points)', (SELECT ecart_max_points FROM fr_controle WHERE source = 'connaissance')
UNION ALL SELECT 'IRCC : lignes mensuelles (francophones + tous)', (SELECT count(*) FROM fr_ircc)
UNION ALL SELECT 'IRCC : cellules masquées (1 à 4 personnes)', (SELECT count(*) FROM fr_ircc WHERE masque)
UNION ALL SELECT 'Villes comparées', (SELECT count(*) FROM fr_villes)
UNION ALL SELECT 'Indicateurs de ville manquants', (SELECT count(*) FROM fr_villes_notes WHERE valeur IS NULL);

-- name: fr_immig_annuel
-- Résidents permanents d'expression française hors Québec, par année : effectif, part de toutes les admissions hors
-- Québec, et nombre de mois connus (la dernière année est partielle). Effectifs arrondis à 5 par IRCC, cellules < 5 masquées
SELECT annee,
       sum(n) FILTER (WHERE profil = 'francophones') AS francophones,
       sum(n) FILTER (WHERE profil = 'tous' AND province NOT IN ('Quebec', 'Not stated')) AS admissions_hq,
       round(100 * sum(n) FILTER (WHERE profil = 'francophones')
                 / sum(n) FILTER (WHERE profil = 'tous' AND province NOT IN ('Quebec', 'Not stated')), 1) AS part_pct,
       count(DISTINCT mois) AS mois
FROM fr_ircc
GROUP BY annee
ORDER BY annee;

-- name: fr_immig_prov
-- Destination des francophones par province, dernière année complète, et part des francophones parmi toutes les
-- admissions de la province
WITH an AS (SELECT max(annee) AS a FROM fr_ircc WHERE mois = 'Dec')
SELECT g.code, g.nom,
       sum(n) FILTER (WHERE profil = 'francophones') AS francophones,
       round(100 * sum(n) FILTER (WHERE profil = 'francophones') / sum(n) FILTER (WHERE profil = 'tous'), 1) AS part_pct
FROM fr_ircc i JOIN fr_geo g ON g.geo_en = i.province, an
WHERE i.annee = an.a AND g.code <> 'QC'
GROUP BY g.code, g.nom
HAVING sum(n) FILTER (WHERE profil = 'francophones') > 0
ORDER BY francophones DESC;

-- name: fr_immig_villes
-- Les 10 villes qui accueillent le plus de francophones (dernière année complète) et leur évolution depuis 2019 (avant la
-- hausse des cibles) : FILTER par année, RANK sur la dernière, rapport calculé seulement au-dessus de 50 arrivées en 2019
WITH an AS (SELECT max(annee) AS a FROM fr_ircc WHERE mois = 'Dec'),
v AS (
    SELECT rmr, province,
           sum(n) FILTER (WHERE annee = 2019) AS n_2019,
           sum(n) FILTER (WHERE annee = an.a) AS n_dernier
    FROM fr_ircc, an
    WHERE profil = 'francophones' AND rmr NOT LIKE 'Other%' AND rmr NOT LIKE '%not stated%'
    GROUP BY rmr, province
)
SELECT replace(regexp_replace(rmr, ' (- Gatineau )?\((Ontario|New Brunswick) part\)', ''), 'Greater Sudbury', 'Grand Sudbury') AS ville,
       g.code AS province, n_2019, n_dernier,
       -- sous 50 arrivées, l'arrondi à 5 et le masquage rendent le rapport trompeur (Sudbury : 5 en 2019, « ×96 »)
       CASE WHEN n_2019 >= 50 THEN round(n_dernier / n_2019, 1) END AS multiplie_par,
       RANK() OVER (ORDER BY n_dernier DESC) AS rang
FROM v JOIN fr_geo g ON g.geo_en = v.province
QUALIFY rang <= 10
ORDER BY rang;

-- name: fr_villes_tableau
-- Les indicateurs bruts des villes comparées, avec l'année et le niveau géographique de chaque source
SELECT * FROM fr_villes ORDER BY nom;

-- name: fr_villes_notes_q
-- Notes de 0 à 100 par ville et par indicateur (min-max sur les 9 villes, inversé quand « moins, c'est mieux »)
SELECT code, nom, pilier, indicateur, libelle, sens, valeur, note FROM fr_villes_notes ORDER BY pilier, indicateur, note DESC;

-- name: fr_villes_classement
-- Classement à poids égaux : moyenne des notes dans chaque pilier, puis moyenne des 4 piliers (les curseurs de la page
-- refont ce calcul avec vos poids)
WITH p AS (SELECT code, nom, pilier, avg(note) AS note FROM fr_villes_notes GROUP BY ALL)
SELECT code, nom,
       round(avg(note) FILTER (WHERE pilier = 'Francophonie'), 1) AS francophonie,
       round(avg(note) FILTER (WHERE pilier = 'Coût de la vie'), 1) AS cout,
       round(avg(note) FILTER (WHERE pilier = 'Emploi'), 1) AS emploi,
       round(avg(note) FILTER (WHERE pilier = 'Cadre de vie'), 1) AS cadre,
       round(avg(note), 1) AS total,
       RANK() OVER (ORDER BY avg(note) DESC) AS rang
FROM p
GROUP BY code, nom
ORDER BY rang;
