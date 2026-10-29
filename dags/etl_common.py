"""Общее для DAG-ов: журнал запусков в etl_logs. Файл без DAG — Airflow его просто импортирует."""

from datetime import datetime, timedelta

from airflow.providers.postgres.hooks.postgres import PostgresHook


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


default_args = {
    'on_success_callback': on_success,
    'on_failure_callback': on_failure,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}
