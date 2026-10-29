"""Фоновая работа бота с воронкой мастеров:
- напоминает мастерам, которые начали подключение и не закончили (не чаще раза в 3 дня,
  не больше двух раз и только если не просили не писать), — дальше задача уходит менеджеру;
- раз в день в 10:00 по Еревану присылает менеджерам задачи на сегодня.
Задачи «перестал отвечать», «проверить активность» и т. п. ставит Airflow (dags/crm_follow_ups.py)."""

import asyncio
import logging
from datetime import date

from aiogram import Bot

from ..config import Config
from ..db import Database
from ..leads import to_local, utcnow
from ..notify import send_to_lead
from ..texts import t
from . import keyboards as kb
from .crm import send_tasks

log = logging.getLogger(__name__)

CHECK_INTERVAL = 300  # секунд
DIGEST_HOUR = 10      # по Еревану


async def send_auto_reminders(bot: Bot, db: Database) -> int:
    leads = await db.leads.claim_auto_reminders()
    for lead in leads:
        await send_to_lead(bot, db, lead, t(lead["lang"], "reminder_finish"), via="system",
                           markup=kb.continue_kb(lead["lang"]))
    return len(leads)


async def send_digest(bot: Bot, db: Database, config: Config) -> None:
    for chat_id in config.manager_chat_ids:
        try:
            await send_tasks(bot, db, chat_id, header="📋 Задачи по мастерам на сегодня")
        except Exception:
            log.exception("Не удалось отправить задачи менеджеру %s", chat_id)


async def run(bot: Bot, db: Database, config: Config) -> None:
    last_digest: date | None = None
    while True:
        try:
            sent = await send_auto_reminders(bot, db)
            if sent:
                log.info("Напоминаний мастерам отправлено: %s", sent)
            now = to_local(utcnow())
            if now.hour >= DIGEST_HOUR and last_digest != now.date():
                last_digest = now.date()
                await send_digest(bot, db, config)
        except Exception:
            log.exception("Ошибка в фоновой обработке воронки")
        await asyncio.sleep(CHECK_INTERVAL)
