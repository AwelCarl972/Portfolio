-- name: fleet_risk
-- Score de risque 0-100 : dérive de panne (40%) + rang coût 12m (30%) + rang immobilisation 12m (30%)
WITH agg AS (
    SELECT asset_id,
           COUNT(*) FILTER (WHERE category = 'corrective') AS failures_12m,
           SUM(cost_eur) AS cost_12m,
           SUM(downtime_days) AS downtime_12m
    FROM interventions
    WHERE done_on >= current_date - INTERVAL 365 DAY
    GROUP BY asset_id
), base AS (
    SELECT a.id, a.label, a.plate, c.name AS client, s.commune, a.km_current,
           COALESCE(g.failures_12m, 0) AS failures_12m,
           COALESCE(g.cost_12m, 0) AS cost_12m,
           COALESCE(g.downtime_12m, 0) AS downtime_12m,
           d.drift_ratio
    FROM assets a
    JOIN clients c ON c.id = a.client_id
    JOIN sites s ON s.id = a.site_id
    LEFT JOIN agg g ON g.asset_id = a.id
    LEFT JOIN v_failure_drift d ON d.asset_id = a.id
)
SELECT id, label, plate, client, commune, km_current, failures_12m, cost_12m, downtime_12m, drift_ratio,
       CAST(ROUND(100 * (
           0.4 * LEAST(GREATEST(1 - COALESCE(drift_ratio, 1), 0), 1)
         + 0.3 * PERCENT_RANK() OVER (ORDER BY cost_12m)
         + 0.3 * PERCENT_RANK() OVER (ORDER BY downtime_12m)
       )) AS INTEGER) AS risk_score
FROM base
ORDER BY risk_score DESC, id;

-- name: supply_alerts
-- Prochaine échéance de remplacement (km -> date via vitesse d'usage 90j), confrontée au stock
-- partagé (ROW_NUMBER par pièce) et aux délais mer/air : quand faut-il commander ?
WITH rate AS (
    SELECT asset_id,
           (MAX(km) - MIN(km)) / NULLIF(DATE_DIFF('day', MIN(logged_on), MAX(logged_on)), 0) AS km_per_day
    FROM km_log
    WHERE logged_on >= current_date - INTERVAL 90 DAY
    GROUP BY asset_id
), last_done AS (
    SELECT asset_id, part_ref, MAX(km) AS km
    FROM interventions WHERE part_ref IS NOT NULL
    GROUP BY asset_id, part_ref
), plan AS (
    SELECT a.id AS asset_id, a.label, a.plate, p.ref AS part_ref, p.label AS part_label,
           p.sea_lead_days, p.air_lead_days, p.stock_qty,
           COALESCE(ld.km, 0) + mp.interval_km AS due_km,
           current_date + CAST(CEIL(GREATEST(COALESCE(ld.km, 0) + mp.interval_km - a.km_current, 0)
                                    / r.km_per_day) AS INTEGER) AS due_date
    FROM maintenance_plan mp
    JOIN assets a ON a.id = mp.asset_id
    JOIN parts p ON p.ref = mp.part_ref
    JOIN rate r ON r.asset_id = a.id AND r.km_per_day > 0
    LEFT JOIN last_done ld ON ld.asset_id = a.id AND ld.part_ref = mp.part_ref
), ranked AS (
    SELECT *, ROW_NUMBER() OVER (PARTITION BY part_ref ORDER BY due_date) AS demand_rank
    FROM plan
)
SELECT asset_id, label, plate, part_ref, part_label, due_km, due_date, stock_qty, demand_rank,
       CAST(DATE_DIFF('day', current_date, due_date - sea_lead_days) AS INTEGER) AS days_left_to_order,
       CASE WHEN demand_rank <= stock_qty THEN 'COUVERT_STOCK'
            WHEN due_date - sea_lead_days >= current_date THEN 'COMMANDER_MER'
            WHEN due_date - air_lead_days >= current_date THEN 'COMMANDER_AIR'
            ELSE 'RUPTURE_PROBABLE' END AS status
FROM ranked
WHERE due_date <= current_date + INTERVAL 120 DAY
ORDER BY CASE WHEN demand_rank <= stock_qty THEN 1 ELSE 0 END, due_date;

-- name: latest_report
SELECT report FROM interventions
WHERE asset_id = ? AND report IS NOT NULL
ORDER BY done_on DESC LIMIT 1;

-- name: catalog
-- Entités sensibles connues (dictionnaire de masquage, prioritaire sur les regex)
SELECT 'CLIENT' AS kind, name AS value FROM clients
UNION ALL SELECT 'ACTIF', plate FROM assets
UNION ALL SELECT 'ACTIF', serial FROM assets
UNION ALL SELECT 'LIEU', address FROM sites
UNION ALL SELECT 'LIEU', name FROM sites;
