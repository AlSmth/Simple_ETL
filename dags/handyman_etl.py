from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook
from psycopg2.extras import execute_values

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
    Table("masters", "dim_masters",
          ("master_id", "full_name", "is_active", "created_at", "updated_at"),
          ("master_id",)),
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


# ---------- журнал запусков ----------

def log_to_db(dag_id, task_id, status, start_time, end_time, error_message=None):
    hook = PostgresHook(postgres_conn_id='postgres_dwh')
    duration = int((end_time - start_time).total_seconds())

    hook.run("""
        INSERT INTO etl_logs (
            dag_id, task_id, status, start_time, end_time, duration_seconds, error_message
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """, parameters=(
        dag_id, task_id, status, start_time, end_time, duration, error_message
    ))


def _log_task(context, status, error_message=None):
    try:
        ti = context['task_instance']
        start_time = ti.start_date.replace(tzinfo=None) if ti.start_date else datetime.utcnow()
        log_to_db(
            dag_id=ti.dag_id,
            task_id=ti.task_id,
            status=status,
            start_time=start_time,
            end_time=datetime.utcnow(),
            error_message=error_message,
        )
    except Exception as e:
        # падение логирования не должно ронять сам пайплайн
        print(f"ERROR IN {status} CALLBACK: {e}")


def on_success(context):
    _log_task(context, 'SUCCESS')


def on_failure(context):
    _log_task(context, 'FAILED', str(context.get('exception')))


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


default_args = {
    'on_success_callback': on_success,
    'on_failure_callback': on_failure,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

with DAG(
    'handyman_etl',
    default_args=default_args,
    description='Заявки Telegram-бота: база бота -> MRR -> STG -> DWH',
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

    load_tasks >> t_stg >> t_dwh
