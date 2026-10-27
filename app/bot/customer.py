"""Сценарий заказчика: язык → категория → описание (+фото) → район → адрес → способ связи
→ телефон → проверка → заявка уходит мастерам и менеджерам. Плюс /orders — свои заявки."""

import logging

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove

from ..config import Config
from ..db import Database
from ..texts import CATEGORIES, CONTACT_METHODS, DEFAULT_LANG, DISTRICTS, LANGS, t
from . import keyboards as kb
from .common import esc, normalize_phone, notify_managers, order_card, user_lang

log = logging.getLogger(__name__)
router = Router(name="customer")

DESCRIPTION_LIMIT = 1000
ADDRESS_LIMIT = 200


class RequestForm(StatesGroup):
    description = State()
    district = State()
    address = State()
    contact = State()
    phone = State()
    confirm = State()


async def remember_user(db: Database, event: Message | CallbackQuery, lang: str | None = None) -> None:
    user = event.from_user
    await db.save_customer(user.id, user.full_name, user.username, lang)


# ---------- команды ----------

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, db: Database):
    await state.clear()
    lang = await db.get_lang(message.from_user.id)
    if lang is None:
        await message.answer(t(DEFAULT_LANG, "choose_language"), reply_markup=kb.language_kb())
        return
    await remember_user(db, message)
    await message.answer(t(lang, "welcome"), reply_markup=kb.categories_kb(lang))


@router.message(Command("language"))
async def cmd_language(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(t(DEFAULT_LANG, "choose_language"), reply_markup=kb.language_kb())


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext, db: Database):
    await state.clear()
    lang = await user_lang(db, message.from_user.id)
    await message.answer(t(lang, "cancelled"), reply_markup=ReplyKeyboardRemove())


@router.message(Command("myid"))
async def cmd_myid(message: Message):
    # нужен при настройке: этот id вписывают в MANAGER_CHAT_IDS
    await message.answer(f"Chat id: <code>{message.chat.id}</code>")


@router.message(Command("orders"))
async def cmd_orders(message: Message, state: FSMContext, db: Database):
    await state.clear()
    lang = await user_lang(db, message.from_user.id)
    orders = await db.customer_orders(message.from_user.id)
    if not orders:
        await message.answer(t(lang, "no_orders"))
        return
    lines = [f"<b>{t(lang, 'my_orders_title')}</b>", ""]
    for o in orders:
        lines.append(
            f"<b>№{o['order_id']}</b> · {o['order_date']:%d.%m.%Y} · "
            f"{esc(t(lang, 'cat_' + o['category_code']))}\n{t(lang, 'status_' + o['status'])}"
        )
    cancellable = [o["order_id"] for o in orders if o["status"] == "new"]
    await message.answer("\n\n".join(lines), reply_markup=kb.cancel_order_kb(lang, cancellable))


@router.callback_query(F.data.startswith("ocancel:"))
async def cancel_order(callback: CallbackQuery, db: Database, bot: Bot, config: Config):
    lang = await user_lang(db, callback.from_user.id)
    order_id = int(callback.data.split(":", 1)[1])
    if not await db.cancel_order(order_id, callback.from_user.id):
        await callback.answer(t(lang, "cannot_cancel"), show_alert=True)
        return
    await callback.answer()
    await callback.message.answer(t(lang, "order_cancelled", id=order_id))
    order = await db.get_order(order_id)
    await notify_managers(bot, config, order_card(order, contacts=True,
                                                  title=f"Заказчик отменил заявку №{order_id}"))


# ---------- язык и категория ----------

@router.callback_query(F.data.startswith("lang:"))
async def choose_language(callback: CallbackQuery, state: FSMContext, db: Database):
    lang = callback.data.split(":", 1)[1]
    if lang not in LANGS:
        await callback.answer()
        return
    await state.clear()
    await remember_user(db, callback, lang)
    await callback.message.edit_text(t(lang, "welcome"), reply_markup=kb.categories_kb(lang))
    await callback.answer()


@router.callback_query(F.data.startswith("cat:"))
async def choose_category(callback: CallbackQuery, state: FSMContext, db: Database):
    category = callback.data.split(":", 1)[1]
    if category not in CATEGORIES:
        await callback.answer()
        return
    lang = await user_lang(db, callback.from_user.id)
    await state.clear()
    await state.update_data(category=category)
    await state.set_state(RequestForm.description)
    await callback.message.edit_text(f"<b>{esc(t(lang, 'cat_' + category))}</b>")
    await callback.message.answer(t(lang, "ask_description"))
    await callback.answer()


# ---------- описание, район, адрес ----------

@router.message(RequestForm.description)
async def got_description(message: Message, state: FSMContext, db: Database):
    lang = await user_lang(db, message.from_user.id)
    text = message.text or message.caption
    if not text:
        await message.answer(t(lang, "need_description"))
        return
    if len(text) > DESCRIPTION_LIMIT:
        await message.answer(t(lang, "description_too_long", limit=DESCRIPTION_LIMIT))
        return
    photo_id = message.photo[-1].file_id if message.photo else None
    await state.update_data(description=text.strip(), photo_file_id=photo_id)
    await state.set_state(RequestForm.district)
    await message.answer(t(lang, "ask_district"), reply_markup=kb.districts_kb(lang))


@router.callback_query(RequestForm.district, F.data.startswith("dist:"))
async def choose_district(callback: CallbackQuery, state: FSMContext, db: Database):
    district = callback.data.split(":", 1)[1]
    if district not in DISTRICTS:
        await callback.answer()
        return
    lang = await user_lang(db, callback.from_user.id)
    await state.update_data(district=district)
    await state.set_state(RequestForm.address)
    await callback.message.edit_text(f"<b>📍 {esc(t(lang, 'dist_' + district))}</b>")
    await callback.message.answer(t(lang, "ask_address"))
    await callback.answer()


@router.message(RequestForm.address)
async def got_address(message: Message, state: FSMContext, db: Database):
    lang = await user_lang(db, message.from_user.id)
    if not message.text:
        await message.answer(t(lang, "need_text"))
        return
    if len(message.text) > ADDRESS_LIMIT:
        await message.answer(t(lang, "description_too_long", limit=ADDRESS_LIMIT))
        return
    await state.update_data(address=message.text.strip())
    await state.set_state(RequestForm.contact)
    await message.answer(t(lang, "ask_contact"), reply_markup=kb.contact_kb(lang))


# ---------- способ связи ----------

@router.callback_query(RequestForm.contact, F.data.startswith("contact:"))
async def choose_contact(callback: CallbackQuery, state: FSMContext, db: Database):
    method = callback.data.split(":", 1)[1]
    if method not in CONTACT_METHODS:
        await callback.answer()
        return
    lang = await user_lang(db, callback.from_user.id)
    await state.update_data(contact_method=method)
    await callback.message.edit_text(f"<b>{esc(t(lang, 'contact_' + method))}</b>")
    await callback.answer()

    if method == "telegram":
        await state.update_data(phone=None)
        await show_summary(callback.message, state, lang)
    else:
        await state.set_state(RequestForm.phone)
        await callback.message.answer(t(lang, "ask_phone"), reply_markup=kb.phone_kb(lang))


@router.message(RequestForm.phone)
async def got_phone(message: Message, state: FSMContext, db: Database):
    lang = await user_lang(db, message.from_user.id)
    raw = message.contact.phone_number if message.contact else message.text
    phone = normalize_phone(raw) if raw else None
    if phone is None:
        await message.answer(t(lang, "bad_phone"))
        return
    await state.update_data(phone=phone)
    # одновременно убираем reply-клавиатуру с кнопкой «поделиться номером»
    await message.answer(f"📞 +{phone}", reply_markup=ReplyKeyboardRemove())
    await show_summary(message, state, lang)


# ---------- подтверждение ----------

async def show_summary(message: Message, state: FSMContext, lang: str) -> None:
    data = await state.get_data()
    await state.set_state(RequestForm.confirm)

    problem = esc(data["description"])
    if data.get("photo_file_id"):
        problem += f" <i>(📷 {esc(t(lang, 'has_photo'))})</i>"
    lines = [
        f"<b>{esc(t(lang, 'summary_title'))}</b>",
        "",
        f"<b>{t(lang, 'label_category')}:</b> {esc(t(lang, 'cat_' + data['category']))}",
        f"<b>{t(lang, 'label_problem')}:</b> {problem}",
        f"<b>{t(lang, 'label_district')}:</b> {esc(t(lang, 'dist_' + data['district']))}",
        f"<b>{t(lang, 'label_address')}:</b> {esc(data['address'])}",
        f"<b>{t(lang, 'label_contact')}:</b> {esc(t(lang, 'contact_' + data['contact_method']))}",
    ]
    if data.get("phone"):
        lines.append(f"<b>{t(lang, 'label_phone')}:</b> +{data['phone']}")
    lines += ["", t(lang, "summary_confirm")]
    await message.answer("\n".join(lines), reply_markup=kb.confirm_kb(lang))


@router.callback_query(RequestForm.confirm, F.data == "confirm:cancel")
async def confirm_cancel(callback: CallbackQuery, state: FSMContext, db: Database):
    lang = await user_lang(db, callback.from_user.id)
    await state.clear()
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(t(lang, "cancelled"))
    await callback.answer()


@router.callback_query(RequestForm.confirm, F.data == "confirm:send")
async def confirm_send(callback: CallbackQuery, state: FSMContext, db: Database, bot: Bot,
                       config: Config):
    lang = await user_lang(db, callback.from_user.id)
    data = await state.get_data()
    # чистим состояние сразу, чтобы двойной клик не создал дубль заявки
    await state.clear()
    await callback.message.edit_reply_markup(reply_markup=None)

    await remember_user(db, callback)
    order_id = await db.add_order({
        "customer_id": callback.from_user.id,
        "category": data["category"],
        "description": data["description"],
        "photo_file_id": data.get("photo_file_id"),
        "city": config.default_city,
        "district": data["district"],
        "address": data["address"],
        "contact_method": data["contact_method"],
        "phone": data.get("phone"),
    })
    order = await db.get_order(order_id)
    await announce_order(bot, db, config, order)

    contact = t(lang, "contact_" + data["contact_method"])
    await callback.message.answer(t(lang, "sent", id=order_id, contact=esc(contact)))
    await callback.answer()


async def announce_order(bot: Bot, db: Database, config: Config, order: dict, *,
                         title: str | None = None) -> None:
    """Новая (или снова свободная) заявка: мастерам — без контактов и с кнопкой «Взять»,
    менеджерам — полная карточка."""
    title = title or f"🆕 Новая заявка №{order['order_id']}"
    for master_id in await db.active_master_ids():
        try:
            sent = await bot.send_message(master_id, order_card(order, contacts=False, title=title),
                                          reply_markup=kb.take_kb(order["order_id"]))
            if order["photo_file_id"]:
                await sent.reply_photo(order["photo_file_id"])
        except Exception:
            log.exception("Не удалось отправить заявку №%s мастеру %s", order["order_id"], master_id)

    await notify_managers(bot, config, order_card(order, contacts=True, title=title),
                          photo_file_id=order["photo_file_id"])
