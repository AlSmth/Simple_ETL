from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook
from psycopg2.extras import execute_values

from etl_common import default_args

# Перекрытие окна загрузки: строка, закоммиченная чуть позже, чем проставлен её updated_at,
# не потеряется. Повторно прочитанные строки безопасны — запись идёт через upsert.
HWM_LOOKBACK = timedelta(minutes=10)


@dataclass(frozen=True)
class Table:
    source: str          # таблица в базе бота
    name: str            # имя в слоях: mrr_<name>, stg_<name>, dwh_<name>
    columns: tuple
    key: tuple

    @property
    def mrr(self):
        return f"mrr_{self.name}"

    @property
    def stg(self):
        return f"stg_{self.name}"

    @property
    def dwh(self):
        return f"dwh_{self.name}"


TABLES = [
    # CRM: мастера — основные клиенты
    Table("leads", "dim_leads",
          ("lead_id", "full_name", "lang", "source", "categories", "districts", "status",
           "refusal_reason", "contact_consent", "script_version", "last_contact_at",
           "next_contact_at", "follow_up_reason", "auto_reminders", "registration_done_at",
           "connected_at", "first_payment_at", "created_at", "updated_at"),
          ("lead_id",)),
    Table("lead_events", "fact_lead_events",
          ("event_id", "lead_id", "event_type", "from_status", "to_status", "created_by", "via",
           "created_at", "updated_at"),
          ("event_id",)),
    Table("masters", "dim_masters",
          ("master_id", "lead_id", "full_name", "is_active", "created_at", "updated_at"),
          ("master_id",)),
    # заявки заказчиков — то, ради чего мастера подключаются
    Table("categories", "dim_categories",
          ("category_id", "code", "category_name", "updated_at"),
          ("category_id",)),
    Table("products", "dim_products",
          ("product_id", "product_name", "category_id", "unit_price", "discontinued", "updated_at"),
          ("product_id",)),
    Table("customers", "dim_customers",
          ("customer_id", "contact_name", "lang", "city", "district", "is_blocked",
           "created_at", "updated_at"),
          ("customer_id",)),
    Table("orders", "fact_orders",
          ("order_id", "customer_id", "master_id", "category_id", "city", "district",
           "contact_method", "status", "order_date", "assigned_at", "completed_at",
           "cancelled_at", "freight", "updated_at"),
          ("order_id",)),
    Table("order_details", "fact_order_details",
          ("order_id", "product_id", "unit_price", "quantity", "discount", "updated_at"),
          ("order_id", "product_id")),
    Table("message_log", "fact_messages",
          ("message_id", "broadcast_id", "customer_id", "order_id", "source", "status",
           "created_at", "updated_at"),
          ("message_id",)),
]

# Этапы воронки по порядку; отказ — отдельный исход, этапом не считается
STAGES = "ARRAY['new', 'contacted', 'negotiation', 'registration', 'connected']"

CRM_MARTS_SQL = f"""
TRUNCATE dwh_mart_lead_funnel;
WITH reached AS (
    SELECT l.lead_id, l.source, l.script_version, l.status, l.first_payment_at,
           l.days_to_connect, date_trunc('month', l.created_at)::date AS cohort_month,
           -- самый дальний этап, до которого лид дошёл: по текущему статусу и по истории
           GREATEST(
               COALESCE(array_position({STAGES}, l.status), 1),
               COALESCE((SELECT max(array_position({STAGES}, e.to_status))
                         FROM dwh_fact_lead_events e WHERE e.lead_id = l.lead_id), 1)
           ) AS stage
    FROM dwh_dim_leads l
)
INSERT INTO dwh_mart_lead_funnel
SELECT cohort_month, source, script_version,
       count(*),
       count(*) FILTER (WHERE stage >= 2),
       count(*) FILTER (WHERE stage >= 3),
       count(*) FILTER (WHERE stage >= 5),
       count(*) FILTER (WHERE first_payment_at IS NOT NULL),
       count(*) FILTER (WHERE status = 'refused'),
       round(count(*) FILTER (WHERE stage >= 5)::numeric / count(*), 4),
       round(count(*) FILTER (WHERE first_payment_at IS NOT NULL)::numeric
             / NULLIF(count(*) FILTER (WHERE stage >= 3), 0), 4),
       round(count(*) FILTER (WHERE status = 'refused')::numeric / count(*), 4),
       round(avg(days_to_connect), 2)
FROM reached
GROUP BY cohort_month, source, script_version;

TRUNCATE dwh_mart_refusals;
INSERT INTO dwh_mart_refusals
SELECT COALESCE(l.refusal_reason, 'unknown'), d.district, l.source, count(*)
FROM dwh_dim_leads l
CROSS JOIN LATERAL unnest(CASE WHEN cardinality(l.districts) > 0 THEN l.districts
                               ELSE ARRAY['unknown'] END) AS d(district)
WHERE l.status = 'refused'
GROUP BY 1, 2, 3;

TRUNCATE dwh_mart_district_balance;
WITH lead_districts AS (
    SELECT d.district, l.status, l.refusal_reason
    FROM dwh_dim_leads l CROSS JOIN LATERAL unnest(l.districts) AS d(district)
), orders AS (
    SELECT district, count(*) AS orders_30d
    FROM dwh_fact_orders
    WHERE order_date >= now() - interval '30 days' AND district IS NOT NULL
    GROUP BY district
), districts AS (
    SELECT district FROM lead_districts UNION SELECT district FROM orders
)
INSERT INTO dwh_mart_district_balance
SELECT d.district,
       count(ld.status) FILTER (WHERE ld.status = 'connected'),
       count(ld.status) FILTER (WHERE ld.status NOT IN ('connected', 'refused')),
       count(ld.status) FILTER (WHERE ld.status = 'refused' AND ld.refusal_reason = 'few_orders'),
       COALESCE(max(o.orders_30d), 0),
       round(COALESCE(max(o.orders_30d), 0)::numeric
             / NULLIF(count(ld.status) FILTER (WHERE ld.status = 'connected'), 0), 2)
FROM districts d
LEFT JOIN lead_districts ld USING (district)
LEFT JOIN orders o USING (district)
GROUP BY d.district;

-- снимок за сегодня пересчитывается, прошлые дни остаются как есть
DELETE FROM dwh_mart_lead_status_daily WHERE snapshot_date = current_date;
INSERT INTO dwh_mart_lead_status_daily
SELECT current_date, status, count(*) FROM dwh_dim_leads GROUP BY status;
"""


# ---------- High Water Mark ----------

def get_hwm(dwh, table_name):
    result = dwh.get_first("""
        SELECT last_loaded_at
        FROM dwh_high_water_mark
        WHERE table_name = %s
    """, parameters=(table_name,))

    return result[0] if result else datetime(1900, 1, 1)


def update_hwm(dwh, table_name, new_hwm):
    dwh.run("""
        INSERT INTO dwh_high_water_mark (table_name, last_loaded_at)
        VALUES (%s, %s)
        ON CONFLICT (table_name)
        DO UPDATE SET last_loaded_at = GREATEST(dwh_high_water_mark.last_loaded_at,
                                                EXCLUDED.last_loaded_at)
    """, parameters=(table_name, new_hwm))


# ---------- шаги пайплайна ----------

def load_table_to_mrr(table: Table):
    source = PostgresHook(postgres_conn_id='postgres_operational')
    target = PostgresHook(postgres_conn_id='postgres_mrr')
    dwh = PostgresHook(postgres_conn_id='postgres_dwh')

    hwm_value = get_hwm(dwh, table.source)
    rows = source.get_records(f"""
        SELECT {', '.join(table.columns)}
        FROM {table.source}
        WHERE updated_at > %s
        ORDER BY updated_at
    """, parameters=(hwm_value - HWM_LOOKBACK,))

    if not rows:
        print(f"No new data for {table.source}")
        return

    update_columns = [c for c in table.columns if c not in table.key]
    upsert_sql = f"""
        INSERT INTO {table.mrr} ({', '.join(table.columns)})
        VALUES %s
        ON CONFLICT ({', '.join(table.key)}) DO UPDATE SET
        {', '.join(f'{c} = EXCLUDED.{c}' for c in update_columns)}
    """
    # одна транзакция и пачки строк вместо отдельного запроса на каждую строку
    with closing(target.get_conn()) as conn, conn, conn.cursor() as cur:
        execute_values(cur, upsert_sql, rows, page_size=1000)

    new_hwm = max(r[table.columns.index('updated_at')] for r in rows)
    update_hwm(dwh, table.source, new_hwm)
    print(f"{table.source}: {len(rows)} rows loaded, HWM updated to {new_hwm}")


def copy_layer(src_conn_id, dst_conn_id, pairs):
    """Полная перезаливка таблиц: TRUNCATE и вставка в одной транзакции,
    чтобы дашборд никогда не увидел пустую таблицу."""
    src = PostgresHook(postgres_conn_id=src_conn_id)
    dst = PostgresHook(postgres_conn_id=dst_conn_id)

    with closing(dst.get_conn()) as conn, conn, conn.cursor() as cur:
        for src_table, dst_table, columns in pairs:
            cols = ', '.join(columns)
            rows = src.get_records(f"SELECT {cols} FROM {src_table}")
            cur.execute(f"TRUNCATE {dst_table}")
            if rows:
                execute_values(cur, f"INSERT INTO {dst_table} ({cols}) VALUES %s", rows,
                               page_size=1000)
            print(f"{src_table} -> {dst_table}: {len(rows)} rows")


def mrr_to_stg():
    copy_layer('postgres_mrr', 'postgres_stg', [(t.mrr, t.stg, t.columns) for t in TABLES])


def stg_to_dwh():
    copy_layer('postgres_stg', 'postgres_dwh', [(t.stg, t.dwh, t.columns) for t in TABLES])


def build_crm_marts():
    """Витрины CRM внутри DWH: воронка, отказы, баланс районов, снимок статусов."""
    dwh = PostgresHook(postgres_conn_id='postgres_dwh')
    with closing(dwh.get_conn()) as conn, conn, conn.cursor() as cur:
        cur.execute(CRM_MARTS_SQL)
        for mart in ("dwh_mart_lead_funnel", "dwh_mart_refusals", "dwh_mart_district_balance"):
            cur.execute(f"SELECT count(*) FROM {mart}")
            print(f"{mart}: {cur.fetchone()[0]} rows")


with DAG(
    'handyman_etl',
    default_args=default_args,
    description='База бота -> MRR -> STG -> DWH и витрины CRM',
    start_date=datetime(2026, 3, 23),
    schedule='@daily',
    catchup=False,
    tags=['handyman'],
) as dag:
    load_tasks = [
        PythonOperator(
            task_id=f'load_{table.source}_to_mrr',
            python_callable=load_table_to_mrr,
            op_kwargs={'table': table},
        )
        for table in TABLES
    ]

    t_stg = PythonOperator(task_id='mrr_to_stg', python_callable=mrr_to_stg)
    t_dwh = PythonOperator(task_id='stg_to_dwh', python_callable=stg_to_dwh)
    t_marts = PythonOperator(task_id='build_crm_marts', python_callable=build_crm_marts)

    load_tasks >> t_stg >> t_dwh >> t_marts
