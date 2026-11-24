CREATE TABLE IF NOT EXISTS sites (
    id INTEGER PRIMARY KEY, name TEXT NOT NULL, address TEXT NOT NULL, commune TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS clients (
    id INTEGER PRIMARY KEY, name TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS assets (
    id INTEGER PRIMARY KEY, label TEXT NOT NULL, plate TEXT NOT NULL, serial TEXT NOT NULL,
    kind TEXT NOT NULL, client_id INTEGER NOT NULL REFERENCES clients(id),
    site_id INTEGER NOT NULL REFERENCES sites(id), km_current INTEGER NOT NULL
);
-- Délais d'approvisionnement insulaires : fret maritime vs aérien
CREATE TABLE IF NOT EXISTS parts (
    ref TEXT PRIMARY KEY, label TEXT NOT NULL, origin TEXT NOT NULL,
    sea_lead_days INTEGER NOT NULL, air_lead_days INTEGER NOT NULL, stock_qty INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS maintenance_plan (
    asset_id INTEGER REFERENCES assets(id), part_ref TEXT REFERENCES parts(ref),
    interval_km INTEGER NOT NULL, PRIMARY KEY (asset_id, part_ref)
);
CREATE TABLE IF NOT EXISTS interventions (
    id INTEGER PRIMARY KEY, asset_id INTEGER NOT NULL REFERENCES assets(id),
    done_on DATE NOT NULL, km INTEGER NOT NULL,
    category TEXT NOT NULL CHECK (category IN ('corrective', 'preventive')),
    part_ref TEXT, cost_eur DOUBLE NOT NULL, downtime_days DOUBLE NOT NULL, report TEXT
);
CREATE TABLE IF NOT EXISTS km_log (
    asset_id INTEGER NOT NULL REFERENCES assets(id), logged_on DATE NOT NULL, km INTEGER NOT NULL
);
-- Table de correspondance : reste LOCALE, jamais exposée à l'IA
CREATE TABLE IF NOT EXISTS privacy_map (
    alias TEXT PRIMARY KEY, kind TEXT NOT NULL, original TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT current_timestamp
);

-- Dérive : l'intervalle entre deux pannes raccourcit-il ? (ratio < 1 = dégradation)
CREATE OR REPLACE VIEW v_failure_drift AS
WITH gaps AS (
    SELECT asset_id, done_on, km - LAG(km) OVER w AS km_gap
    FROM interventions WHERE category = 'corrective'
    WINDOW w AS (PARTITION BY asset_id ORDER BY done_on)
), s AS (
    SELECT asset_id, km_gap,
           ROW_NUMBER() OVER (PARTITION BY asset_id ORDER BY done_on DESC) AS rn,
           AVG(km_gap) OVER (PARTITION BY asset_id ORDER BY done_on
                             ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING) AS avg_prev
    FROM gaps WHERE km_gap IS NOT NULL
)
SELECT asset_id, km_gap AS last_gap, ROUND(avg_prev) AS avg_prev,
       ROUND(km_gap / NULLIF(avg_prev, 0), 2) AS drift_ratio
FROM s WHERE rn = 1 AND avg_prev IS NOT NULL;
