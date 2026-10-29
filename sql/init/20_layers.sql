-- Слои хранилища. Колонки совпадают со списками в dags/handyman_etl.py (TABLES).
-- В аналитику не попадают телефоны, адреса, описания, фото и тексты сообщений: они нужны только боту.
-- Скрипт идемпотентный, как и 10_operational.sql.

------------------------------------------------------------------ MRR
-- Зеркало источника: инкрементальная загрузка с upsert по первичному ключу.
\connect mrr

CREATE TABLE IF NOT EXISTS mrr_dim_leads (
    lead_id INTEGER PRIMARY KEY, full_name TEXT, lang TEXT, source TEXT, categories TEXT[],
    districts TEXT[], status TEXT, refusal_reason TEXT, contact_consent BOOLEAN,
    script_version TEXT, last_contact_at TIMESTAMP, next_contact_at TIMESTAMP,
    follow_up_reason TEXT, auto_reminders SMALLINT, registration_done_at TIMESTAMP,
    connected_at TIMESTAMP, first_payment_at TIMESTAMP, created_at TIMESTAMP, updated_at TIMESTAMP
);
CREATE TABLE IF NOT EXISTS mrr_fact_lead_events (
    event_id INTEGER PRIMARY KEY, lead_id INTEGER, event_type TEXT, from_status TEXT,
    to_status TEXT, created_by BIGINT, via TEXT, created_at TIMESTAMP, updated_at TIMESTAMP
);
CREATE TABLE IF NOT EXISTS mrr_dim_categories (
    category_id SMALLINT PRIMARY KEY, code TEXT, category_name TEXT, updated_at TIMESTAMP
);
CREATE TABLE IF NOT EXISTS mrr_dim_products (
    product_id SMALLINT PRIMARY KEY, product_name TEXT, category_id SMALLINT,
    unit_price NUMERIC(12, 2), discontinued BOOLEAN, updated_at TIMESTAMP
);
CREATE TABLE IF NOT EXISTS mrr_dim_customers (
    customer_id BIGINT PRIMARY KEY, contact_name TEXT, lang TEXT, city TEXT, district TEXT,
    is_blocked BOOLEAN, created_at TIMESTAMP, updated_at TIMESTAMP
);
CREATE TABLE IF NOT EXISTS mrr_dim_masters (
    master_id BIGINT PRIMARY KEY, full_name TEXT, is_active BOOLEAN,
    created_at TIMESTAMP, updated_at TIMESTAMP
);
ALTER TABLE mrr_dim_masters ADD COLUMN IF NOT EXISTS lead_id INTEGER;
CREATE TABLE IF NOT EXISTS mrr_fact_orders (
    order_id INTEGER PRIMARY KEY, customer_id BIGINT, master_id BIGINT, category_id SMALLINT,
    city TEXT, district TEXT, contact_method TEXT, status TEXT, order_date TIMESTAMP,
    assigned_at TIMESTAMP, completed_at TIMESTAMP, cancelled_at TIMESTAMP,
    freight NUMERIC(12, 2), updated_at TIMESTAMP
);
CREATE TABLE IF NOT EXISTS mrr_fact_order_details (
    order_id INTEGER, product_id SMALLINT, unit_price NUMERIC(12, 2), quantity SMALLINT,
    discount NUMERIC(4, 3), updated_at TIMESTAMP, PRIMARY KEY (order_id, product_id)
);
CREATE TABLE IF NOT EXISTS mrr_fact_messages (
    message_id INTEGER PRIMARY KEY, broadcast_id INTEGER, customer_id BIGINT, order_id INTEGER,
    source TEXT, status TEXT, created_at TIMESTAMP, updated_at TIMESTAMP
);

------------------------------------------------------------------ STG
-- Промежуточный слой: полностью перезаливается из MRR перед публикацией в DWH.
\connect stg

CREATE TABLE IF NOT EXISTS stg_dim_leads (
    lead_id INTEGER PRIMARY KEY, full_name TEXT, lang TEXT, source TEXT, categories TEXT[],
    districts TEXT[], status TEXT, refusal_reason TEXT, contact_consent BOOLEAN,
    script_version TEXT, last_contact_at TIMESTAMP, next_contact_at TIMESTAMP,
    follow_up_reason TEXT, auto_reminders SMALLINT, registration_done_at TIMESTAMP,
    connected_at TIMESTAMP, first_payment_at TIMESTAMP, created_at TIMESTAMP, updated_at TIMESTAMP
);
CREATE TABLE IF NOT EXISTS stg_fact_lead_events (
    event_id INTEGER PRIMARY KEY, lead_id INTEGER, event_type TEXT, from_status TEXT,
    to_status TEXT, created_by BIGINT, via TEXT, created_at TIMESTAMP, updated_at TIMESTAMP
);
CREATE TABLE IF NOT EXISTS stg_dim_categories (
    category_id SMALLINT PRIMARY KEY, code TEXT, category_name TEXT, updated_at TIMESTAMP
);
CREATE TABLE IF NOT EXISTS stg_dim_products (
    product_id SMALLINT PRIMARY KEY, product_name TEXT, category_id SMALLINT,
    unit_price NUMERIC(12, 2), discontinued BOOLEAN, updated_at TIMESTAMP
);
CREATE TABLE IF NOT EXISTS stg_dim_customers (
    customer_id BIGINT PRIMARY KEY, contact_name TEXT, lang TEXT, city TEXT, district TEXT,
    is_blocked BOOLEAN, created_at TIMESTAMP, updated_at TIMESTAMP
);
CREATE TABLE IF NOT EXISTS stg_dim_masters (
    master_id BIGINT PRIMARY KEY, full_name TEXT, is_active BOOLEAN,
    created_at TIMESTAMP, updated_at TIMESTAMP
);
ALTER TABLE stg_dim_masters ADD COLUMN IF NOT EXISTS lead_id INTEGER;
CREATE TABLE IF NOT EXISTS stg_fact_orders (
    order_id INTEGER PRIMARY KEY, customer_id BIGINT, master_id BIGINT, category_id SMALLINT,
    city TEXT, district TEXT, contact_method TEXT, status TEXT, order_date TIMESTAMP,
    assigned_at TIMESTAMP, completed_at TIMESTAMP, cancelled_at TIMESTAMP,
    freight NUMERIC(12, 2), updated_at TIMESTAMP
);
CREATE TABLE IF NOT EXISTS stg_fact_order_details (
    order_id INTEGER, product_id SMALLINT, unit_price NUMERIC(12, 2), quantity SMALLINT,
    discount NUMERIC(4, 3), updated_at TIMESTAMP, PRIMARY KEY (order_id, product_id)
);
CREATE TABLE IF NOT EXISTS stg_fact_messages (
    message_id INTEGER PRIMARY KEY, broadcast_id INTEGER, customer_id BIGINT, order_id INTEGER,
    source TEXT, status TEXT, created_at TIMESTAMP, updated_at TIMESTAMP
);

------------------------------------------------------------------ DWH
-- Витрина для Power BI и агента, плюс служебные таблицы ETL.
\connect dwh

CREATE TABLE IF NOT EXISTS dwh_dim_leads (
    lead_id INTEGER PRIMARY KEY, full_name TEXT, lang TEXT, source TEXT, categories TEXT[],
    districts TEXT[], status TEXT, refusal_reason TEXT, contact_consent BOOLEAN,
    script_version TEXT, last_contact_at TIMESTAMP, next_contact_at TIMESTAMP,
    follow_up_reason TEXT, auto_reminders SMALLINT, registration_done_at TIMESTAMP,
    connected_at TIMESTAMP, first_payment_at TIMESTAMP, created_at TIMESTAMP, updated_at TIMESTAMP,
    days_to_connect NUMERIC GENERATED ALWAYS AS
        (EXTRACT(EPOCH FROM connected_at - created_at) / 86400) STORED
);
CREATE TABLE IF NOT EXISTS dwh_fact_lead_events (
    event_id INTEGER PRIMARY KEY, lead_id INTEGER, event_type TEXT, from_status TEXT,
    to_status TEXT, created_by BIGINT, via TEXT, created_at TIMESTAMP, updated_at TIMESTAMP
);
CREATE TABLE IF NOT EXISTS dwh_dim_categories (
    category_id SMALLINT PRIMARY KEY, code TEXT, category_name TEXT, updated_at TIMESTAMP
);
CREATE TABLE IF NOT EXISTS dwh_dim_products (
    product_id SMALLINT PRIMARY KEY, product_name TEXT, category_id SMALLINT,
    unit_price NUMERIC(12, 2), discontinued BOOLEAN, updated_at TIMESTAMP
);
CREATE TABLE IF NOT EXISTS dwh_dim_customers (
    customer_id BIGINT PRIMARY KEY, contact_name TEXT, lang TEXT, city TEXT, district TEXT,
    is_blocked BOOLEAN, created_at TIMESTAMP, updated_at TIMESTAMP
);
CREATE TABLE IF NOT EXISTS dwh_dim_masters (
    master_id BIGINT PRIMARY KEY, full_name TEXT, is_active BOOLEAN,
    created_at TIMESTAMP, updated_at TIMESTAMP
);
ALTER TABLE dwh_dim_masters ADD COLUMN IF NOT EXISTS lead_id INTEGER;
CREATE TABLE IF NOT EXISTS dwh_fact_orders (
    order_id INTEGER PRIMARY KEY, customer_id BIGINT, master_id BIGINT, category_id SMALLINT,
    city TEXT, district TEXT, contact_method TEXT, status TEXT, order_date TIMESTAMP,
    assigned_at TIMESTAMP, completed_at TIMESTAMP, cancelled_at TIMESTAMP,
    freight NUMERIC(12, 2), updated_at TIMESTAMP,
    -- вычисляемые поля для дашборда
    order_day DATE GENERATED ALWAYS AS (order_date::date) STORED,
    hours_to_assign NUMERIC GENERATED ALWAYS AS
        (EXTRACT(EPOCH FROM assigned_at - order_date) / 3600) STORED,
    hours_to_complete NUMERIC GENERATED ALWAYS AS
        (EXTRACT(EPOCH FROM completed_at - order_date) / 3600) STORED
);
CREATE TABLE IF NOT EXISTS dwh_fact_order_details (
    order_id INTEGER, product_id SMALLINT, unit_price NUMERIC(12, 2), quantity SMALLINT,
    discount NUMERIC(4, 3), updated_at TIMESTAMP,
    revenue NUMERIC GENERATED ALWAYS AS (unit_price * quantity * (1 - discount)) STORED,
    PRIMARY KEY (order_id, product_id)
);
CREATE TABLE IF NOT EXISTS dwh_fact_messages (
    message_id INTEGER PRIMARY KEY, broadcast_id INTEGER, customer_id BIGINT, order_id INTEGER,
    source TEXT, status TEXT, created_at TIMESTAMP, updated_at TIMESTAMP
);

-- ---------- витрины CRM: пересчитывает задача build_crm_marts ----------

-- Воронка по когортам: месяц появления лида × источник × версия сценария.
-- Сравнивать конверсию честно только внутри сопоставимых когорт.
CREATE TABLE IF NOT EXISTS dwh_mart_lead_funnel (
    cohort_month              DATE,
    source                    TEXT,
    script_version            TEXT,
    leads                     INTEGER,  -- все потенциальные мастера когорты
    contacted                 INTEGER,  -- дошли хотя бы до «связались»
    negotiation               INTEGER,  -- дошли до переговоров или дальше
    connected                 INTEGER,
    paid                      INTEGER,
    refused                   INTEGER,
    conv_contact_to_connected NUMERIC,  -- connected / leads
    conv_negotiation_to_paid  NUMERIC,  -- paid / negotiation
    refusal_rate              NUMERIC,  -- refused / leads
    avg_days_to_connect       NUMERIC,
    PRIMARY KEY (cohort_month, source, script_version)
);

-- Причины отказов в разрезе районов: «мало заказов в районе» — сигнал про спрос, а не про продажи
CREATE TABLE IF NOT EXISTS dwh_mart_refusals (
    refusal_reason TEXT,
    district       TEXT,
    source         TEXT,
    refused        INTEGER,
    PRIMARY KEY (refusal_reason, district, source)
);

-- Баланс спроса и предложения по районам
CREATE TABLE IF NOT EXISTS dwh_mart_district_balance (
    district           TEXT PRIMARY KEY,
    connected_masters  INTEGER,
    leads_in_funnel    INTEGER,
    refused_few_orders INTEGER,
    orders_30d         INTEGER,
    orders_per_master  NUMERIC
);

-- Снимок воронки на каждый день: история не перезаписывается
CREATE TABLE IF NOT EXISTS dwh_mart_lead_status_daily (
    snapshot_date DATE,
    status        TEXT,
    leads         INTEGER,
    PRIMARY KEY (snapshot_date, status)
);

CREATE TABLE IF NOT EXISTS dwh_high_water_mark (
    table_name     TEXT PRIMARY KEY,
    last_loaded_at TIMESTAMP NOT NULL
);
CREATE TABLE IF NOT EXISTS etl_logs (
    log_id           SERIAL PRIMARY KEY,
    dag_id           TEXT NOT NULL,
    task_id          TEXT NOT NULL,
    status           TEXT NOT NULL,
    start_time       TIMESTAMP,
    end_time         TIMESTAMP,
    duration_seconds INTEGER,
    error_message    TEXT
);

GRANT CONNECT ON DATABASE dwh TO agent_ro;
GRANT USAGE ON SCHEMA public TO agent_ro;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO agent_ro;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO agent_ro;
