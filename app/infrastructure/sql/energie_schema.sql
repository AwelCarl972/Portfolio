-- Électricité de La Réunion : données ouvertes d'EDF (opendata-reunion.edf.fr). {raw} = dossier des CSV.
-- en_filiere, en_filiere_h et en_commune sont créées par le dépôt depuis le domaine (app/domain/energie.py).

-- Production horaire par filière. Piège : l'horodatage annonce +00:00 jusqu'en 2023, puis +01:00 / +02:00
-- (heure de Paris) en 2024, alors que le pic solaire tombe toujours à midi heure locale. Les heures sont en
-- réalité l'heure de La Réunion écrite comme si c'était de l'UTC : on retire le décalage annoncé.
CREATE OR REPLACE TABLE en_horaire_brut AS
SELECT left(date_heure, 19)::TIMESTAMP - to_hours(substr(date_heure, 21, 2)::INT) AS heure,
       right(date_heure, 6) AS decalage_annonce,
       statut,
       production_totale_mw::DOUBLE AS total_mw,
       thermique_mw::DOUBLE AS thermique_mw,
       bagasse_charbon_mw::DOUBLE AS bagasse_charbon_mw,
       hydraulique_mw::DOUBLE AS hydraulique_mw,
       photovoltaique_mw::DOUBLE AS photovoltaique_mw,
       eolien_mw::DOUBLE AS eolien_mw,
       bioenergies_mw::DOUBLE AS bioenergies_mw
FROM read_csv('{raw}/edf_horaire.csv', all_varchar = true);

-- Une ligne par heure : le fichier contient un horodatage en double (1er juin 2021), on n'en garde qu'un
CREATE OR REPLACE TABLE en_horaire AS
SELECT * FROM en_horaire_brut
QUALIFY row_number() OVER (PARTITION BY heure ORDER BY statut DESC, total_mw) = 1;

-- Bilan annuel validé, en format long : une ligne par année et par filière
CREATE OR REPLACE TABLE en_annuel AS
-- (colonnes nommées une à une : la géothermie et les liaisons, toujours vides à La Réunion, sont absentes du fichier)
WITH brut AS (
    SELECT annee_prod, charbon, moteurs_diesel, turbines_a_combustion_fioul, bioenergie, hydraulique,
           solaire_photovoltaique, eolien
    FROM read_csv('{raw}/edf_annuel.csv')
)
SELECT b.annee_prod AS annee, f.filiere, f.libelle, f.renouvelable, f.ordre, coalesce(b.mwh, 0) AS mwh
FROM (UNPIVOT brut ON COLUMNS(* EXCLUDE annee_prod) INTO NAME filiere VALUE mwh) b
JOIN en_filiere f USING (filiere);

-- Part renouvelable recalculée, à comparer à celle qu'EDF publie (contrôle dans en_qualite)
CREATE OR REPLACE TABLE en_part AS
SELECT a.annee,
       sum(mwh) AS total_mwh,
       100 * sum(mwh) FILTER (WHERE renouvelable) / sum(mwh) AS part_enr,
       any_value(p.part_enr) AS part_enr_publiee
FROM en_annuel a
JOIN read_csv('{raw}/edf_annuel.csv') p ON p.annee_prod = a.annee
GROUP BY a.annee;

CREATE OR REPLACE TABLE en_co2 AS
SELECT annee, emissions_realisees_kt AS kt FROM read_csv('{raw}/edf_co2.csv');

-- Consommation par commune et secteur ; nombre_de_pds = points de livraison (compteurs)
CREATE OR REPLACE TABLE en_conso AS
SELECT c.annee, lpad(c.code_insee::VARCHAR, 5, '0') AS code_insee, m.nom, m.hauts, c.secteur,
       c.consommation_mwh AS mwh, c.nombre_de_pds AS compteurs
FROM read_csv('{raw}/edf_conso.csv') c
JOIN en_commune m ON m.code_insee = lpad(c.code_insee::VARCHAR, 5, '0');
