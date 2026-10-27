"""Отправка сообщений заказчикам. Каждое сообщение пишется в message_log."""

import asyncio
import logging
from dataclasses import dataclass

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter

from .db import Database

log = logging.getLogger(__name__)

# Telegram разрешает боту около 30 сообщений в секунду; держимся с запасом
SEND_INTERVAL = 0.05


async def send_to_customer(bot: Bot, db: Database, customer_id: int, text: str, *,
                           source: str, order_id: int | None = None,
                           broadcast_id: int | None = None, html: bool = False) -> bool:
    """html=False — текст уходит как есть: так текст от агента не сломает разметку."""
    error = None
    for attempt in range(2):
        try:
            await bot.send_message(customer_id, text, parse_mode="HTML" if html else None)
            error = None
            break
        except TelegramRetryAfter as e:
            # упёрлись в лимит Telegram: ждём сколько просят и пробуем ещё раз
            error = str(e)
            if attempt == 0:
                await asyncio.sleep(e.retry_after)
        except TelegramForbiddenError as e:
            # заказчик заблокировал бота — больше ему не пишем
            await db.mark_blocked(customer_id)
            error = str(e)
            break
        except Exception as e:
            log.exception("Не удалось отправить сообщение заказчику %s", customer_id)
            error = str(e)
            break

    await db.log_message(customer_id, text, "failed" if error else "sent", source,
                         order_id=order_id, broadcast_id=broadcast_id,
                         error=error[:500] if error else None)
    return error is None


@dataclass
class BroadcastResult:
    broadcast_id: int
    sent: int
    failed: int
    skipped: int  # заблокировали бота к моменту отправки

    def summary(self) -> str:
        text = f"Рассылка №{self.broadcast_id} отправлена: доставлено {self.sent}"
        if self.failed:
            text += f", не доставлено {self.failed}"
        if self.skipped:
            text += f", пропущено (бот заблокирован) {self.skipped}"
        return text


async def run_broadcast(bot: Bot, db: Database, broadcast_id: int) -> BroadcastResult | None:
    """Отправляет подтверждённую рассылку. None — если её уже отправили или отменили."""
    broadcast = await db.decide_broadcast(broadcast_id, "sent")
    if broadcast is None:
        return None

    customers = {c["customer_id"]: c for c in await db.customers_by_ids(broadcast["customer_ids"])}
    result = BroadcastResult(broadcast_id, sent=0, failed=0, skipped=0)
    for customer_id in broadcast["customer_ids"]:
        customer = customers.get(customer_id)
        if customer is None or customer["is_blocked"]:
            result.skipped += 1
            continue
        ok = await send_to_customer(bot, db, customer_id, broadcast["text"], source="agent",
                                    order_id=broadcast["order_id"], broadcast_id=broadcast_id)
        if ok:
            result.sent += 1
        else:
            result.failed += 1
        await asyncio.sleep(SEND_INTERVAL)
    return result
