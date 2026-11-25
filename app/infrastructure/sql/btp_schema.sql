-- BTP à La Réunion : commande publique de travaux (DECP) et permis de construire (Sitadel). {raw} = dossier des CSV.
-- bt_famille_cpv, bt_tranche, bt_type_acheteur et bt_commune sont créées par le dépôt depuis le domaine (app/domain/btp.py).

-- Répertoire SIRENE : nom, taille et implantation de chaque titulaire et de chaque acheteur (un SIRET par ligne).
-- La recherche est plein texte : une réponse dont le SIREN n'est pas le début du SIRET cherché est une autre entreprise.
CREATE OR REPLACE TABLE bt_sirene AS
SELECT siret, siren, nom, categorie, nature_juridique, cp_etablissement, naf, section
FROM read_csv('{raw}/sirene_decp.csv', all_varchar = true)
WHERE siren = left(siret, 9);

-- Les deux formats réglementaires empilés. Le format de 2019 écrit la nature tantôt en capitales, tantôt non,
-- et lit les SIRET comme des nombres (zéro de tête perdu) ; « MQ NC » (non communiqué) devient NULL.
-- Les procédures négociées, écrites de cinq façons selon le format, sont regroupées.
CREATE OR REPLACE TABLE bt_attribution_brut AS
WITH brut AS (
    SELECT '2019' AS format, * FROM read_csv('{raw}/decp_arrete2019.csv', delim = ';', header = true, all_varchar = true)
    UNION ALL BY NAME
    SELECT '2022' AS format, * FROM read_csv('{raw}/decp_arrete2022.csv', delim = ';', header = true, all_varchar = true)
)
SELECT format, trim(id) AS id_marche, lpad(trim(acheteur_id), 14, '0') AS acheteur_siret,
       CASE WHEN titulaire_typeidentifiant_1 = 'SIRET' THEN lpad(trim(titulaire_id_1), 14, '0') END AS titulaire_siret,
       CASE upper(replace(nature, 'É', 'E')) WHEN 'MARCHE' THEN 'Marché' WHEN 'ACCORD-CADRE' THEN 'Accord-cadre'
            ELSE 'Marché subséquent' END AS nature,
       trim(objet) AS objet, left(codecpv, 8) AS cpv,
       CASE WHEN procedure ILIKE '%sans publicité%' THEN 'Sans publicité ni mise en concurrence'
            WHEN procedure ILIKE '%négoci%' THEN 'Procédure avec négociation'
            ELSE procedure END AS procedure,
       try_cast(dureemois AS INT) AS duree_mois,
       try_cast(datenotification AS DATE) AS date_notification, try_cast(montant AS DOUBLE) AS montant,
       try_cast(offresrecues AS INT) AS offres_recues, typegroupementoperateurs AS groupement
FROM brut;

-- Une ligne par attribution (un lot, un titulaire). Retirés : les doublons exacts, les dates hors 2019 à
-- aujourd'hui, et les montants de moins de 1 000 € (erreurs d'unité : un marché de travaux à 46 € n'existe pas).
CREATE OR REPLACE TABLE bt_attribution AS
SELECT a.*, year(date_notification) AS annee, coalesce(f.famille, 'generique') AS famille
FROM bt_attribution_brut a
LEFT JOIN bt_famille_cpv f ON f.prefixe = left(a.cpv, 4)
WHERE date_notification BETWEEN DATE '2019-01-01' AND current_date
  AND montant >= 1000
QUALIFY row_number() OVER (PARTITION BY acheteur_siret, id_marche, titulaire_siret, montant, date_notification
                           ORDER BY format DESC) = 1;

-- Un accord-cadre attribué à plusieurs entreprises répète le même montant (un plafond commun) sur chaque ligne :
-- on le compte une fois dans les totaux, et chaque titulaire en reçoit une part égale dans les classements.
CREATE OR REPLACE TABLE bt_marche AS
SELECT *, count(*) OVER (PARTITION BY acheteur_siret, objet, date_notification, montant) AS nb_attributaires,
       montant / count(*) OVER (PARTITION BY acheteur_siret, objet, date_notification, montant) AS montant_part,
       row_number() OVER (PARTITION BY acheteur_siret, objet, date_notification, montant ORDER BY titulaire_siret) = 1 AS compte_au_total,
       t.libelle AS tranche, t.ordre AS tranche_ordre
FROM bt_attribution
JOIN bt_tranche t ON montant >= t.borne_basse AND (t.borne_haute IS NULL OR montant < t.borne_haute)
WHERE montant < {hors_norme};

-- Contrats globaux de plus de 100 M€ (conception, réalisation et exploitation sur des années) : montrés à part
CREATE OR REPLACE TABLE bt_hors_norme AS
SELECT * FROM bt_attribution WHERE montant >= {hors_norme};

-- Acheteurs : nom et type (commune, Région, bailleur...) lus dans SIRENE, premier préfixe juridique qui correspond
CREATE OR REPLACE TABLE bt_acheteur AS
SELECT m.acheteur_siret, coalesce(any_value(s.nom), 'SIRET ' || m.acheteur_siret) AS nom,
       coalesce(arg_min(t.libelle, t.ordre), 'Autres ou inconnus') AS type_acheteur
FROM (SELECT DISTINCT acheteur_siret FROM bt_attribution) m
LEFT JOIN bt_sirene s ON s.siret = m.acheteur_siret
LEFT JOIN bt_type_acheteur t ON starts_with(s.nature_juridique, t.prefixe)
GROUP BY m.acheteur_siret;

-- Titulaires : un entrepreneur individuel n'est jamais nommé ; l'implantation est celle de l'établissement signataire.
-- Une entreprise signe parfois depuis plusieurs établissements : « entreprise » (le SIREN) les regroupe.
CREATE OR REPLACE TABLE bt_titulaire AS
SELECT DISTINCT m.titulaire_siret, coalesce(s.siren, m.titulaire_siret) AS entreprise,
       coalesce(s.nom, 'Non trouvé dans SIRENE') AS nom,
       coalesce(s.categorie, 'Inconnue') AS categorie,
       CASE WHEN s.cp_etablissement IS NULL THEN 'Inconnue'
            WHEN starts_with(s.cp_etablissement, '974') THEN 'À La Réunion' ELSE 'Hors de La Réunion' END AS implantation,
       s.section = 'F' AS entreprise_btp
FROM bt_attribution m LEFT JOIN bt_sirene s ON s.siret = m.titulaire_siret
WHERE m.titulaire_siret IS NOT NULL;

-- Permis de construire créant des logements : dédoublonnés par numéro, 2023 exclu (millésime incomplet dans la source)
CREATE OR REPLACE TABLE bt_permis AS
SELECT DISTINCT ON (num_dau) CAST(comm AS VARCHAR) AS code_insee, year(date_reelle_autorisation) AS annee,
       nb_lgt_tot_crees AS lgt_tot, nb_lgt_ind_crees AS lgt_ind, nb_lgt_col_crees AS lgt_col,
       nb_lgt_pret_loc_social AS lgt_social, surf_hab_creee AS surface
FROM read_csv('{raw}/permis.csv', delim = ';', header = true)
WHERE date_reelle_autorisation IS NOT NULL AND year(date_reelle_autorisation) BETWEEN 2017 AND 2022;

-- Population légale 2016 par commune (INSEE), pour rapporter la construction au nombre d'habitants
CREATE OR REPLACE TABLE bt_population AS
SELECT CAST(code_insee AS VARCHAR) AS code_insee, population_municipale AS pop
FROM read_csv('{raw}/population.csv', delim = ';', header = true)
WHERE annee_recensement = 2016;
