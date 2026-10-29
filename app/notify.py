"""Отправка сообщений заказчикам и мастерам. Заказчикам — с записью в message_log,
мастерам-лидам — с записью в историю CRM (lead_events)."""

import asyncio
import logging
from dataclasses import dataclass

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter
from aiogram.types import InlineKeyboardMarkup

from .db import Database

log = logging.getLogger(__name__)

# Telegram разрешает боту около 30 сообщений в секунду; держимся с запасом
SEND_INTERVAL = 0.05


async def _send(bot: Bot, chat_id: int, text: str, *, html: bool,
                markup: InlineKeyboardMarkup | None = None) -> tuple[str | None, bool]:
    """Возвращает (ошибка, заблокировал ли бота). html=False — текст уходит как есть:
    так текст от агента не сломает разметку."""
    error = None
    for attempt in range(2):
        try:
            await bot.send_message(chat_id, text, parse_mode="HTML" if html else None,
                                   reply_markup=markup)
            return None, False
        except TelegramRetryAfter as e:
            # упёрлись в лимит Telegram: ждём сколько просят и пробуем ещё раз
            error = str(e)
            if attempt == 0:
                await asyncio.sleep(e.retry_after)
        except TelegramForbiddenError as e:
            return str(e), True
        except Exception as e:
            log.exception("Не удалось отправить сообщение в чат %s", chat_id)
            return str(e), False
    return error, False


async def send_to_customer(bot: Bot, db: Database, customer_id: int, text: str, *,
                           source: str, order_id: int | None = None,
                           broadcast_id: int | None = None, html: bool = False) -> bool:
    error, blocked = await _send(bot, customer_id, text, html=html)
    if blocked:
        # заказчик заблокировал бота — больше ему не пишем
        await db.mark_blocked(customer_id)
    await db.log_message(customer_id, text, "failed" if error else "sent", source,
                         order_id=order_id, broadcast_id=broadcast_id,
                         error=error[:500] if error else None)
    return error is None


async def send_to_lead(bot: Bot, db: Database, lead: dict, text: str, *, via: str, actor: int = 0,
                       markup: InlineKeyboardMarkup | None = None) -> bool:
    error, blocked = await _send(bot, lead["tg_user_id"], text, html=False, markup=markup)
    await db.leads.log_outgoing(lead["lead_id"], text, via=via, actor=actor, delivered=error is None)
    if blocked:
        await db.leads.set_consent(lead["tg_user_id"], False)
    return error is None


@dataclass
class BroadcastResult:
    broadcast_id: int
    sent: int
    failed: int
    skipped: int  # заблокировали бота или отказались от рассылок к моменту отправки

    def summary(self) -> str:
        text = f"Рассылка №{self.broadcast_id} отправлена: доставлено {self.sent}"
        if self.failed:
            text += f", не доставлено {self.failed}"
        if self.skipped:
            text += f", пропущено (нет согласия или бот заблокирован) {self.skipped}"
        return text


async def run_broadcast(bot: Bot, db: Database, broadcast_id: int) -> BroadcastResult | None:
    """Отправляет подтверждённую рассылку. None — если её уже отправили или отменили."""
    broadcast = await db.decide_broadcast(broadcast_id, "sent")
    if broadcast is None:
        return None

    ids = broadcast["recipient_ids"]
    result = BroadcastResult(broadcast_id, sent=0, failed=0, skipped=0)
    if broadcast["audience"] == "leads":
        recipients = {r["lead_id"]: r for r in await db.leads.by_ids(ids)}
        allowed = lambda r: r["tg_user_id"] is not None and r["contact_consent"] is not False
    else:
        recipients = {r["customer_id"]: r for r in await db.customers_by_ids(ids)}
        allowed = lambda r: not r["is_blocked"] and r["contact_consent"] is not False

    for recipient_id in ids:
        recipient = recipients.get(recipient_id)
        if recipient is None or not allowed(recipient):
            result.skipped += 1
            continue
        if broadcast["audience"] == "leads":
            ok = await send_to_lead(bot, db, recipient, broadcast["text"], via="agent",
                                    actor=broadcast["created_by"])
        else:
            ok = await send_to_customer(bot, db, recipient_id, broadcast["text"], source="agent",
                                        order_id=broadcast["order_id"], broadcast_id=broadcast_id)
        if ok:
            result.sent += 1
        else:
            result.failed += 1
        await asyncio.sleep(SEND_INTERVAL)
    return result
