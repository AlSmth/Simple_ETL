"""Менеджер: переписывается с AI-агентом и подтверждает его рассылки.
CRM-кнопки и команды /leads, /tasks — в crm.py."""

import asyncio
import contextlib
import logging

from aiogram import Bot, F, Router
from aiogram.enums import ChatAction
from aiogram.filters import Command, StateFilter
from aiogram.types import CallbackQuery, Message

from ..agent import ManagerAgent
from ..db import Database
from ..notify import run_broadcast
from . import keyboards as kb
from .common import IsManager, esc

log = logging.getLogger(__name__)
router = Router(name="manager")
router.message.filter(IsManager())
router.callback_query.filter(IsManager())

TELEGRAM_LIMIT = 4000
LANG_NAMES = {"ru": "русский", "en": "английский", "hy": "армянский"}
AUDIENCE_NAMES = {"customers": "заказчикам", "leads": "мастерам"}

MANAGER_HELP = (
    "Вы менеджер. Мастера — наши основные клиенты, и бот ведёт их воронку:\n"
    "/leads — воронка мастеров\n"
    "/tasks — кому пора написать сегодня (задачи приходят и сами в 10:00)\n"
    "/lead 12 — карточка лида\n\n"
    "Всё остальное пишите агенту обычным текстом, например:\n"
    "• кто из мастеров отказался из-за цены и в каких районах?\n"
    "• добавь мастера Ашот, сантехник, Арабкир, +374 91 123456, позвонить завтра\n"
    "• напомни мастерам, которые не закончили регистрацию\n"
    "• какая конверсия в подключение за октябрь?\n\n"
    "Рассылки агент только готовит — отправляете вы кнопкой.\n"
    "/reset — начать с агентом новый диалог"
)


# ---------- рассылки агента ----------

@router.callback_query(F.data.startswith("bsend:"))
async def send_broadcast(callback: CallbackQuery, db: Database, bot: Bot,
                         agent: ManagerAgent | None):
    broadcast_id = int(callback.data.split(":", 1)[1])
    await callback.answer("Отправляю…")
    await callback.message.edit_reply_markup(reply_markup=None)
    result = await run_broadcast(bot, db, broadcast_id)
    if result is None:
        await callback.message.answer(f"Рассылка №{broadcast_id} уже отправлена или отменена.")
        return
    await callback.message.answer("📨 " + result.summary())
    if agent:
        agent.add_note(callback.message.chat.id, result.summary())


@router.callback_query(F.data.startswith("bcancel:"))
async def cancel_broadcast(callback: CallbackQuery, db: Database, agent: ManagerAgent | None):
    broadcast_id = int(callback.data.split(":", 1)[1])
    await callback.message.edit_reply_markup(reply_markup=None)
    if await db.decide_broadcast(broadcast_id, "cancelled") is None:
        await callback.answer("Рассылка уже отправлена или отменена", show_alert=True)
        return
    await callback.answer("Рассылка отменена")
    await callback.message.answer(f"Рассылка №{broadcast_id} отменена.")
    if agent:
        agent.add_note(callback.message.chat.id, f"менеджер отменил рассылку №{broadcast_id}")


async def show_broadcast(message: Message, db: Database, broadcast_id: int) -> None:
    broadcast = await db.get_broadcast(broadcast_id)
    if broadcast["audience"] == "leads":
        recipients = await db.leads.by_ids(broadcast["recipient_ids"])
        names = [r["full_name"] for r in recipients]
    else:
        recipients = await db.customers_by_ids(broadcast["recipient_ids"])
        names = [r["contact_name"] for r in recipients]
    langs = sorted({LANG_NAMES.get(r["lang"], r["lang"]) for r in recipients})
    shown = ", ".join(esc(n) for n in names[:10])
    if len(names) > 10:
        shown += f" и ещё {len(names) - 10}"
    order = f" по заявке №{broadcast['order_id']}" if broadcast["order_id"] else ""
    await message.answer(
        f"📨 <b>Рассылка №{broadcast_id} {AUDIENCE_NAMES[broadcast['audience']]}{order}</b>\n"
        f"Получателей: {len(recipients)} ({shown})\n"
        f"Язык: {', '.join(langs)}\n\n"
        f"<blockquote>{esc(broadcast['text'])}</blockquote>\n\n"
        "Отправить?",
        reply_markup=kb.broadcast_kb(broadcast_id),
    )


# ---------- диалог с агентом ----------

@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(MANAGER_HELP)


@router.message(Command("reset"))
async def cmd_reset(message: Message, agent: ManagerAgent | None):
    if agent:
        agent.reset(message.chat.id)
    await message.answer("Начинаем с агентом новый диалог.")


async def keep_typing(bot: Bot, chat_id: int) -> None:
    while True:
        with contextlib.suppress(Exception):
            await bot.send_chat_action(chat_id, ChatAction.TYPING)
        await asyncio.sleep(4)


@router.message(StateFilter(None), F.text, ~F.text.startswith("/"))
async def ask_agent(message: Message, db: Database, bot: Bot, agent: ManagerAgent | None):
    if agent is None:
        await message.answer("Агент выключен: задайте ANTHROPIC_API_KEY в .env и перезапустите бота.\n"
                             "Без агента доступны /leads и /tasks.")
        return
    typing = asyncio.create_task(keep_typing(bot, message.chat.id))
    try:
        reply = await agent.ask(message.chat.id, message.text)
    finally:
        typing.cancel()

    # ответ модели — обычный текст: шлём без HTML-разметки, длинный режем на части
    text = reply.text
    while text:
        chunk, text = text[:TELEGRAM_LIMIT], text[TELEGRAM_LIMIT:]
        await message.answer(chunk, parse_mode=None)
    for broadcast_id in reply.broadcast_ids:
        await show_broadcast(message, db, broadcast_id)
