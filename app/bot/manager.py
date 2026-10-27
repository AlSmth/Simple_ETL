"""Менеджер: одобряет мастеров, переписывается с AI-агентом и подтверждает его рассылки."""

import asyncio
import contextlib
import logging

from aiogram import Bot, F, Router
from aiogram.enums import ChatAction
from aiogram.filters import Command, StateFilter
from aiogram.types import CallbackQuery, Message

from ..agent import ManagerAgent
from ..config import Config
from ..db import Database
from ..notify import run_broadcast
from . import keyboards as kb
from .common import IsManager, esc
from .master import MASTER_HELP

log = logging.getLogger(__name__)
router = Router(name="manager")
router.message.filter(IsManager())
router.callback_query.filter(IsManager())

TELEGRAM_LIMIT = 4000
LANG_NAMES = {"ru": "русский", "en": "английский", "hy": "армянский"}

MANAGER_HELP = (
    "Вы менеджер. Пишите агенту обычным текстом, например:\n"
    "• сколько заявок за эту неделю и сколько из них ещё без мастера?\n"
    "• какая выручка по категориям за октябрь?\n"
    "• напиши заказчикам с открытыми заявками по сантехнике, что мастер приедет завтра до 12\n\n"
    "Рассылки агент только готовит — отправляете вы кнопкой.\n"
    "/reset — начать с агентом новый диалог"
)


# ---------- мастера ----------

@router.callback_query(F.data.startswith("mapprove:"))
async def approve_master(callback: CallbackQuery, db: Database, bot: Bot):
    user_id = int(callback.data.split(":", 1)[1])
    if await db.set_master_active(user_id, True) is None:
        await callback.answer("Заявка в мастера не найдена", show_alert=True)
        return
    await callback.answer("Мастер добавлен")
    await callback.message.edit_text(
        f"{callback.message.html_text}\n\n✅ Принят: {esc(callback.from_user.full_name)}"
    )
    with contextlib.suppress(Exception):
        await bot.send_message(user_id, "✅ Вас добавили в команду мастеров!\n\n" + MASTER_HELP)


@router.callback_query(F.data.startswith("mreject:"))
async def reject_master(callback: CallbackQuery, db: Database, bot: Bot):
    user_id = int(callback.data.split(":", 1)[1])
    await db.set_master_active(user_id, False)
    await callback.answer("Отклонено")
    await callback.message.edit_text(
        f"{callback.message.html_text}\n\n❌ Отклонён: {esc(callback.from_user.full_name)}"
    )
    with contextlib.suppress(Exception):
        await bot.send_message(user_id, "К сожалению, заявку в мастера отклонили.")


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
    customers = await db.customers_by_ids(broadcast["customer_ids"])
    langs = sorted({LANG_NAMES.get(c["lang"], c["lang"]) for c in customers})
    names = ", ".join(esc(c["contact_name"]) for c in customers[:10])
    if len(customers) > 10:
        names += f" и ещё {len(customers) - 10}"
    order = f" по заявке №{broadcast['order_id']}" if broadcast["order_id"] else ""
    await message.answer(
        f"📨 <b>Рассылка №{broadcast_id}{order}</b>\n"
        f"Получателей: {len(customers)} ({names})\n"
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
        await message.answer("Агент выключен: задайте ANTHROPIC_API_KEY в .env и перезапустите бота.")
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
