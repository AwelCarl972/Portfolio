-- name: bt_kpis
-- Chiffres clés de la commande publique de travaux recensée (montants comptés une fois par marché)
SELECT min(annee) AS an_min, max(annee) AS an_max,
       count(*) FILTER (WHERE compte_au_total) AS marches,
       count(DISTINCT acheteur_siret) AS acheteurs,
       count(DISTINCT t.entreprise) AS entreprises,
       sum(montant) FILTER (WHERE compte_au_total) / 1e6 AS montant_m,
       median(montant) FILTER (WHERE compte_au_total) AS montant_median,
       100 * sum(montant_part) FILTER (WHERE t.implantation = 'À La Réunion')
           / sum(montant_part) FILTER (WHERE t.implantation <> 'Inconnue') AS part_locale_pct,
       100 * count(*) FILTER (WHERE offres_recues = 1) / count(offres_recues) AS offre_unique_pct,
       median(offres_recues) AS offres_mediane
FROM bt_marche m LEFT JOIN bt_titulaire t USING (titulaire_siret);

-- name: bt_par_an
-- Marchés de travaux notifiés chaque année, par tranche de montant (nombre et millions d'euros)
SELECT annee, tranche, tranche_ordre, count(*) AS marches, round(sum(montant) / 1e6, 1) AS montant_m
FROM bt_marche
WHERE compte_au_total
GROUP BY ALL
ORDER BY annee, tranche_ordre;

-- name: bt_familles
-- Ce qui est commandé : familles de travaux (code CPV), nombre de marchés, montant total et médian
SELECT f.libelle, f.ordre, count(*) AS marches, round(sum(montant) / 1e6, 1) AS montant_m,
       round(median(montant) / 1000) AS median_k,
       round(100 * count(*) / sum(count(*)) OVER (), 1) AS part_marches_pct
FROM bt_marche m JOIN bt_famille f USING (famille)
WHERE compte_au_total
GROUP BY ALL
ORDER BY f.ordre;

-- name: bt_acheteurs_type
-- Qui commande : type d'acheteur public, nombre de marchés et montant
SELECT a.type_acheteur, count(*) AS marches, count(DISTINCT acheteur_siret) AS acheteurs,
       round(sum(montant) / 1e6, 1) AS montant_m,
       round(100 * sum(montant) / sum(sum(montant)) OVER (), 1) AS part_montant_pct
FROM bt_marche m JOIN bt_acheteur a USING (acheteur_siret)
WHERE compte_au_total
GROUP BY ALL
ORDER BY montant_m DESC;

-- name: bt_top_acheteurs
-- Les 15 acheteurs qui notifient le plus de travaux (montant), et leur marché médian
SELECT a.nom, a.type_acheteur, count(*) AS marches, round(sum(montant) / 1e6, 1) AS montant_m,
       round(median(montant) / 1000) AS median_k
FROM bt_marche m JOIN bt_acheteur a USING (acheteur_siret)
WHERE compte_au_total
GROUP BY ALL
ORDER BY sum(montant) DESC
LIMIT 15;

-- name: bt_concurrence
-- Combien d'entreprises répondent : offres reçues par tranche de montant (format 2022, seul à les publier)
SELECT tranche, tranche_ordre, count(offres_recues) AS marches,
       round(median(offres_recues), 1) AS offres_mediane,
       round(100 * count(*) FILTER (WHERE offres_recues = 1) / count(offres_recues), 1) AS une_offre_pct,
       round(100 * count(*) FILTER (WHERE offres_recues BETWEEN 2 AND 3) / count(offres_recues), 1) AS deux_trois_pct,
       round(100 * count(*) FILTER (WHERE offres_recues >= 4) / count(offres_recues), 1) AS quatre_plus_pct
FROM bt_marche
WHERE offres_recues BETWEEN 1 AND 200
GROUP BY ALL
ORDER BY tranche_ordre;

-- name: bt_procedures
-- Comment les marchés sont passés : procédure, nombre et montant médian
SELECT procedure, count(*) AS marches, round(median(montant) / 1000) AS median_k,
       round(100 * count(*) / sum(count(*)) OVER (), 1) AS part_pct
FROM bt_marche
WHERE compte_au_total AND procedure IS NOT NULL
GROUP BY 1
ORDER BY marches DESC;

-- name: bt_top_titulaires
-- Les 15 entreprises qui remportent le plus de montant ; un plafond partagé entre plusieurs titulaires est réparti
-- Une entreprise = un SIREN, tous établissements confondus ; l'implantation retenue est celle qui pèse le plus
WITH t AS (
    SELECT e.entreprise, any_value(e.nom) AS nom, any_value(e.categorie) AS categorie,
           arg_max(e.implantation, m.montant_part) AS implantation, count(*) AS marches, sum(m.montant_part) AS montant
    FROM bt_marche m JOIN bt_titulaire e USING (titulaire_siret) GROUP BY 1
)
SELECT rank() OVER (ORDER BY montant DESC) AS rang, nom, categorie, implantation, marches,
       round(montant / 1e6, 1) AS montant_m,
       round(100 * montant / sum(montant) OVER (), 1) AS part_pct
FROM t
QUALIFY rang <= 15
ORDER BY rang;

-- name: bt_concentration
-- Concentration du marché : part du montant captée par les 5, 10, 20 et 50 premières entreprises
WITH t AS (
    SELECT e.entreprise, sum(montant_part) AS montant FROM bt_marche m JOIN bt_titulaire e USING (titulaire_siret) GROUP BY 1
), r AS (
    SELECT montant, row_number() OVER (ORDER BY montant DESC) AS rang, sum(montant) OVER () AS total, count(*) OVER () AS n
    FROM t
)
SELECT premieres, any_value(n) AS entreprises,
       round(100 * sum(montant) FILTER (WHERE rang <= premieres) / any_value(total), 1) AS part_pct
FROM r CROSS JOIN (VALUES (5), (10), (20), (50)) v(premieres)
GROUP BY premieres
ORDER BY premieres;

-- name: bt_taille
-- Taille et implantation des entreprises titulaires : nombre de marchés et part du montant
SELECT e.categorie, e.implantation, count(*) AS marches, count(DISTINCT e.entreprise) AS entreprises,
       round(sum(montant_part) / 1e6, 1) AS montant_m,
       round(100 * sum(montant_part) / sum(sum(montant_part)) OVER (), 1) AS part_montant_pct
FROM bt_marche m JOIN bt_titulaire e USING (titulaire_siret)
GROUP BY e.categorie, e.implantation
ORDER BY CASE e.categorie WHEN 'PME' THEN 1 WHEN 'ETI' THEN 2 WHEN 'GE' THEN 3 ELSE 4 END, e.implantation;

-- name: bt_hors_norme_q
-- Les contrats globaux de plus de 100 M€, mis à part : qui, quoi, combien
SELECT annee, a.nom AS acheteur, coalesce(e.nom, '–') AS titulaire, objet, round(montant / 1e6, 1) AS montant_m
FROM bt_hors_norme h JOIN bt_acheteur a USING (acheteur_siret) LEFT JOIN bt_titulaire e USING (titulaire_siret)
ORDER BY montant DESC;

-- name: bt_logements_an
-- Logements autorisés chaque année (permis de construire) : individuel, collectif, et part sociale
SELECT annee, sum(lgt_ind) AS individuel, sum(lgt_col) AS collectif, sum(lgt_tot) AS total,
       sum(lgt_social) AS social, round(100 * sum(lgt_social) / sum(lgt_tot), 1) AS part_sociale_pct,
       round(100 * (sum(lgt_tot) / LAG(sum(lgt_tot)) OVER (ORDER BY annee) - 1), 1) AS variation_pct
FROM bt_permis
GROUP BY annee
ORDER BY annee;

-- name: bt_logements_region
-- Où l'on construit : logements autorisés par micro-région et par an, pour 1 000 habitants (population 2016)
WITH pop AS (
    SELECT c.region, sum(p.pop) AS pop FROM bt_population p JOIN bt_commune c USING (code_insee) GROUP BY 1
)
SELECT c.region, sum(lgt_tot) AS logements, sum(lgt_col) AS collectif, sum(lgt_social) AS social,
       round(1000 * sum(lgt_tot) / 6.0 / any_value(pop.pop), 1) AS par_an_pour_1000hab,
       round(100 * sum(lgt_col) / sum(lgt_tot), 1) AS part_collectif_pct
FROM bt_permis p JOIN bt_commune c USING (code_insee) JOIN pop USING (region)
GROUP BY c.region
ORDER BY par_an_pour_1000hab DESC;

-- name: bt_top_communes
-- Les communes qui autorisent le plus de logements (2017-2022), et leur part de collectif et de social
SELECT c.nom, c.region, sum(lgt_tot) AS logements,
       round(100 * sum(lgt_col) / sum(lgt_tot), 1) AS part_collectif_pct,
       round(100 * sum(lgt_social) / sum(lgt_tot), 1) AS part_sociale_pct,
       round(sum(surface) FILTER (WHERE lgt_col = 0 AND lgt_ind > 0) / sum(lgt_ind) FILTER (WHERE lgt_col = 0 AND lgt_ind > 0)) AS m2_maison
FROM bt_permis p JOIN bt_commune c USING (code_insee)
GROUP BY ALL
ORDER BY logements DESC;

-- name: bt_qualite
-- Du brut au retenu : ce que chaque règle de nettoyage retire
SELECT 'Lignes brutes (deux formats DECP)' AS etape, count(*) AS valeur FROM bt_attribution_brut
UNION ALL SELECT 'Hors 2019 à aujourd''hui ou sans date', count(*) FROM bt_attribution_brut
    WHERE date_notification IS NULL OR date_notification NOT BETWEEN DATE '2019-01-01' AND current_date
UNION ALL SELECT 'Montant de moins de 1 000 € (erreur d''unité)', count(*) FROM bt_attribution_brut
    WHERE montant < 1000 AND date_notification BETWEEN DATE '2019-01-01' AND current_date
UNION ALL SELECT 'Attributions retenues (après doublons exacts)', count(*) FROM bt_attribution
UNION ALL SELECT 'Contrats globaux de plus de 100 M€, mis à part', count(*) FROM bt_hors_norme
UNION ALL SELECT 'Marchés comptés une fois (plafonds partagés regroupés)', count(*) FROM bt_marche WHERE compte_au_total
UNION ALL SELECT 'Entreprises titulaires distinctes (SIREN, contrats globaux compris)', count(DISTINCT entreprise) FROM bt_titulaire
UNION ALL SELECT 'Titulaires trouvés dans SIRENE (%)', round(100 * count(*) FILTER (WHERE nom <> 'Non trouvé dans SIRENE') / count(*), 1) FROM bt_titulaire
UNION ALL SELECT 'Acheteurs distincts', count(*) FROM bt_acheteur
UNION ALL SELECT 'Permis de construire retenus (2017-2022)', count(*) FROM bt_permis;
