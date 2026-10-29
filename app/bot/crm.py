"""CRM для менеджера: воронка мастеров, задачи на повторный контакт и карточка лида с кнопками."""

from datetime import datetime, time, timedelta

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from ..config import Config
from ..db import Database
from ..leads import from_local, to_local, utcnow
from ..notify import send_to_lead
from ..texts import LEAD_STATUSES, REFUSAL_REASONS, t
from . import keyboards as kb
from .common import IsManager, LEAD_STATUS_RU, esc, lead_card

router = Router(name="crm")
router.message.filter(IsManager())
router.callback_query.filter(IsManager())

TASKS_LIMIT = 15
CONTACT_HOUR = 10  # «завтра», «через 3 дня» — в 10:00 по Еревану


def end_of_today_utc() -> datetime:
    today = to_local(utcnow()).date()
    return from_local(datetime.combine(today + timedelta(days=1), time()))


def local_morning_utc(days: int) -> datetime:
    day = to_local(utcnow()).date() + timedelta(days=days)
    return from_local(datetime.combine(day, time(CONTACT_HOUR)))


async def send_tasks(bot: Bot, db: Database, chat_id: int, *, header: str) -> int:
    """Отправляет менеджеру задачи до конца дня, каждую — карточкой с кнопками."""
    until = end_of_today_utc()
    total = await db.leads.count_due(until)
    if not total:
        return 0
    tasks = await db.leads.due_tasks(until, limit=TASKS_LIMIT)
    more = f"\nПоказаны первые {len(tasks)}, остальные — после них." if total > len(tasks) else ""
    await bot.send_message(chat_id, f"<b>{esc(header)}: {total}</b>{more}")
    for lead in tasks:
        await bot.send_message(chat_id, lead_card(lead), reply_markup=kb.lead_kb(lead))
    return total


# ---------- команды ----------

@router.message(Command("leads"))
async def cmd_leads(message: Message, db: Database):
    counts = await db.leads.funnel_counts()
    total = sum(counts.values())
    lines = [f"<b>Воронка мастеров: {total}</b>", ""]
    for status in LEAD_STATUSES:
        lines.append(f"{LEAD_STATUS_RU[status]}: {counts.get(status, 0)}")
    if total:
        connected = counts.get("connected", 0)
        lines += ["", f"Конверсия в подключение: {connected / total:.0%}"]
    due = await db.leads.count_due(end_of_today_utc())
    lines += ["", f"Задач на сегодня: {due} — /tasks",
              "Подробнее — спросите агента, например «кто отказался из-за цены?»"]
    await message.answer("\n".join(lines))


@router.message(Command("tasks"))
async def cmd_tasks(message: Message, db: Database, bot: Bot):
    if not await send_tasks(bot, db, message.chat.id, header="Задачи на сегодня"):
        await message.answer("Задач на сегодня нет 👌")


@router.message(Command("lead"))
async def cmd_lead(message: Message, db: Database):
    parts = (message.text or "").split()
    lead = await db.leads.get(int(parts[1])) if len(parts) > 1 and parts[1].isdigit() else None
    if lead is None:
        await message.answer("Использование: /lead <номер лида>")
        return
    await message.answer(lead_card(lead), reply_markup=kb.lead_kb(lead))


# ---------- карточка лида ----------

def _ids(callback: CallbackQuery) -> list[str]:
    return callback.data.split(":")[1:]


async def refresh(callback: CallbackQuery, lead: dict | None, toast: str) -> None:
    if lead is None:
        await callback.answer("Лид не найден", show_alert=True)
        return
    await callback.answer(toast)
    await callback.message.edit_text(lead_card(lead), reply_markup=kb.lead_kb(lead))


@router.callback_query(F.data.startswith("lv:"))
async def view(callback: CallbackQuery, db: Database):
    await refresh(callback, await db.leads.get(int(_ids(callback)[0])), "")


@router.callback_query(F.data.startswith("lc:"))
async def contacted(callback: CallbackQuery, db: Database):
    lead_id = int(_ids(callback)[0])
    lead = await db.leads.contacted(lead_id, via="manager", actor=callback.from_user.id)
    await refresh(callback, lead, "Контакт записан")
    if lead:
        await callback.message.answer(f"Когда следующий контакт с «{esc(lead['full_name'])}»?",
                                      reply_markup=kb.next_contact_kb(lead_id))


@router.callback_query(F.data.startswith("ln:"))
async def negotiation(callback: CallbackQuery, db: Database):
    lead_id = int(_ids(callback)[0])
    lead = await db.leads.set_status(lead_id, "negotiation", via="manager", actor=callback.from_user.id)
    await refresh(callback, lead, "Переговоры")


@router.callback_query(F.data.startswith("ls:"))
async def schedule(callback: CallbackQuery, db: Database):
    lead_id, days = map(int, _ids(callback))
    lead = await db.leads.schedule(lead_id, local_morning_utc(days), None, via="manager",
                                   actor=callback.from_user.id)
    if lead and callback.message.text and callback.message.text.startswith("Когда следующий"):
        # ответ на вопрос после «Связался»: карточку не перерисовываем, просто подтверждаем
        await callback.answer("Запланировано")
        await callback.message.edit_text(
            f"⏰ {esc(lead['full_name'])}: {to_local(lead['next_contact_at']):%d.%m %H:%M}")
        return
    await refresh(callback, lead, "Запланировано")


@router.callback_query(F.data.startswith("lx:"))
async def no_next(callback: CallbackQuery, db: Database):
    lead = await db.leads.clear_next(int(_ids(callback)[0]), via="manager", actor=callback.from_user.id)
    await callback.answer("Без следующего контакта")
    if lead:
        await callback.message.edit_text(f"{esc(lead['full_name'])}: следующий контакт не нужен")


@router.callback_query(F.data.startswith("lr:"))
async def ask_reason(callback: CallbackQuery):
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=kb.refusal_kb(int(_ids(callback)[0])))


@router.callback_query(F.data.startswith("lrr:"))
async def refused(callback: CallbackQuery, db: Database):
    lead_id, reason = _ids(callback)
    if reason not in REFUSAL_REASONS:
        await callback.answer()
        return
    lead = await db.leads.refuse(int(lead_id), reason, via="manager", actor=callback.from_user.id)
    await refresh(callback, lead, "Отказ записан")


@router.callback_query(F.data.startswith("lp:"))
async def paid(callback: CallbackQuery, db: Database):
    lead = await db.leads.mark_paid(int(_ids(callback)[0]), via="manager", actor=callback.from_user.id)
    await refresh(callback, lead, "Оплата записана")


# ---------- подключение мастера ----------

@router.callback_query(F.data.startswith("mapprove:"))
async def approve(callback: CallbackQuery, db: Database, bot: Bot):
    lead = await db.leads.connect(int(_ids(callback)[0]), actor=callback.from_user.id)
    if lead is None:
        await callback.answer("Уже подключён или нет Telegram", show_alert=True)
        return
    await refresh(callback, lead, "Мастер подключён")
    await send_to_lead(bot, db, lead, t(lead["lang"], "master_approved"), via="manager",
                       actor=callback.from_user.id)


@router.callback_query(F.data.startswith("mreject:"))
async def reject(callback: CallbackQuery, db: Database, bot: Bot):
    lead = await db.leads.refuse(int(_ids(callback)[0]), "other", via="manager",
                                 actor=callback.from_user.id, comment="отклонён менеджером")
    await refresh(callback, lead, "Отклонено")
    if lead and lead["tg_user_id"]:
        await send_to_lead(bot, db, lead, t(lead["lang"], "master_rejected"), via="manager",
                           actor=callback.from_user.id)
