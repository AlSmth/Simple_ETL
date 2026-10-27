-- Слои хранилища. Колонки совпадают со списками в dags/handyman_etl.py (TABLES).
-- В аналитику не попадают телефоны, адреса, описания и фото: они нужны только боту.

------------------------------------------------------------------ MRR
-- Зеркало источника: инкрементальная загрузка с upsert по первичному ключу.
\connect mrr

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
