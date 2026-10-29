"""Фоновая обработка CRM раз в час: находит лидов, которым пора написать, и ставит задачу
(next_contact_at + follow_up_reason). Сами сообщения Airflow не отправляет — это делают бот
(напоминания о незавершённой регистрации) и менеджер (задачи в /tasks)."""

from contextlib import closing
from datetime import datetime

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook

from etl_common import default_args

FIRST_CONTACT_AFTER = '1 day'      # лид, добавленный вручную, ждёт первого контакта
NO_RESPONSE_AFTER = '14 days'      # переговоры без контакта
CHECK_ACTIVITY_AFTER = '14 days'   # подключённый мастер не берёт заявки

FLAG_SQL = f"""
WITH due AS (
    SELECT lead_id, 'first_contact' AS reason FROM leads
    WHERE status = 'new' AND source <> 'bot' AND next_contact_at IS NULL
      AND last_contact_at IS NULL AND created_at < now() - interval '{FIRST_CONTACT_AFTER}'
    UNION ALL
    SELECT lead_id, 'no_response' FROM leads
    WHERE status IN ('contacted', 'negotiation') AND next_contact_at IS NULL
      AND COALESCE(last_contact_at, created_at) < now() - interval '{NO_RESPONSE_AFTER}'
    UNION ALL
    SELECT l.lead_id, 'check_activity' FROM leads l
    JOIN masters m ON m.lead_id = l.lead_id AND m.is_active
    WHERE l.status = 'connected' AND l.next_contact_at IS NULL
      AND COALESCE(l.last_contact_at, l.connected_at) < now() - interval '{CHECK_ACTIVITY_AFTER}'
      AND NOT EXISTS (SELECT 1 FROM orders o WHERE o.master_id = m.master_id
                      AND o.assigned_at > now() - interval '{CHECK_ACTIVITY_AFTER}')
), flagged AS (
    UPDATE leads SET next_contact_at = now(), follow_up_reason = due.reason
    FROM due WHERE leads.lead_id = due.lead_id
    RETURNING leads.lead_id, due.reason
)
INSERT INTO lead_events (lead_id, event_type, text, via)
SELECT lead_id, 'follow_up', reason, 'airflow' FROM flagged
RETURNING lead_id, text
"""


def flag_follow_ups():
    hook = PostgresHook(postgres_conn_id='postgres_operational')
    with closing(hook.get_conn()) as conn, conn, conn.cursor() as cur:
        cur.execute(FLAG_SQL)
        flagged = cur.fetchall()
    for lead_id, reason in flagged:
        print(f"lead {lead_id}: {reason}")
    print(f"Задач на повторный контакт поставлено: {len(flagged)}")


with DAG(
    'crm_follow_ups',
    default_args=default_args,
    description='Ставит задачи на повторный контакт с мастерами',
    start_date=datetime(2026, 10, 1),
    schedule='@hourly',
    catchup=False,
    tags=['handyman', 'crm'],
) as dag:
    PythonOperator(task_id='flag_follow_ups', python_callable=flag_follow_ups)
