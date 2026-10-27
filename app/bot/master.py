"""Мастера: регистрация через одобрение менеджера, свободные заявки, взятие, закрытие."""

import logging
from decimal import Decimal, InvalidOperation

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message

from ..config import Config
from ..db import Database
from ..notify import send_to_customer
from ..texts import t
from . import keyboards as kb
from .common import IsMaster, contact_buttons, esc, notify_managers, order_card
from .customer import announce_order

log = logging.getLogger(__name__)
router = Router(name="master")

MASTER_HELP = (
    "👷 Вы в команде мастеров.\n\n"
    "/new — свободные заявки\n"
    "/my — мои заявки в работе\n\n"
    "Новые заявки будут приходить сюда автоматически."
)


class CompleteForm(StatesGroup):
    service = State()
    price = State()
    confirm = State()


def _order_id(callback: CallbackQuery) -> int:
    return int(callback.data.split(":", 1)[1])


def assigned_markup(order: dict) -> InlineKeyboardMarkup:
    markup = kb.master_order_kb(order["order_id"])
    buttons = contact_buttons(order)
    if buttons:
        markup.inline_keyboard.insert(0, buttons)
    return markup


# ---------- регистрация ----------

@router.message(Command("master"))
async def cmd_master(message: Message, state: FSMContext, db: Database, bot: Bot, config: Config):
    await state.clear()
    master = await db.get_master(message.from_user.id)
    if master and master["is_active"]:
        await message.answer(MASTER_HELP)
        return
    user = message.from_user
    await db.request_master(user.id, user.full_name, user.username)
    username = f" (@{esc(user.username)})" if user.username else ""
    await notify_managers(
        bot, config,
        f"🙋 <b>Заявка в мастера</b>\n"
        f'<a href="tg://user?id={user.id}">{esc(user.full_name)}</a>{username}, id <code>{user.id}</code>',
        markup=kb.master_request_kb(user.id),
    )
    await message.answer("Заявка отправлена менеджеру. Как только её одобрят, я напишу.")


# ---------- свободные заявки и взятие ----------

@router.message(Command("new"), IsMaster())
async def cmd_new(message: Message, db: Database):
    orders = await db.open_orders(limit=10)
    if not orders:
        await message.answer("Свободных заявок сейчас нет. Новые придут сюда автоматически.")
        return
    for order in orders:
        await message.answer(order_card(order, contacts=False), reply_markup=kb.take_kb(order["order_id"]))


@router.callback_query(F.data.startswith("take:"), IsMaster())
async def take_order(callback: CallbackQuery, db: Database, bot: Bot, config: Config):
    order_id = _order_id(callback)
    if not await db.take_order(order_id, callback.from_user.id):
        await callback.answer("Заявку уже взяли или отменили.", show_alert=True)
        await callback.message.edit_reply_markup(reply_markup=None)
        return
    await callback.answer("Заявка ваша!")
    order = await db.get_order(order_id)
    await callback.message.edit_text(
        order_card(order, contacts=True, title=f"✅ Вы взяли заявку №{order_id}"),
        reply_markup=assigned_markup(order),
    )

    lang = order["customer_lang"]
    await send_to_customer(bot, db, order["customer_id"],
                           t(lang, "notify_assigned", id=order_id, master=order["master_name"]),
                           source="system", order_id=order_id)
    await notify_managers(bot, config, f"👷 {esc(order['master_name'])} взял заявку №{order_id}")


@router.callback_query(F.data.startswith("take:"))
async def take_not_master(callback: CallbackQuery):
    await callback.answer("Брать заявки могут только мастера. Подать заявку: /master", show_alert=True)


@router.message(Command("new", "my"))
async def master_only(message: Message):
    await message.answer("Эти команды — для мастеров. Подать заявку в команду: /master")


# ---------- мои заявки ----------

@router.message(Command("my"), IsMaster())
async def cmd_my(message: Message, db: Database):
    orders = await db.master_orders(message.from_user.id)
    if not orders:
        await message.answer("У вас нет заявок в работе. Свободные: /new")
        return
    for order in orders:
        await message.answer(order_card(order, contacts=True), reply_markup=assigned_markup(order))


@router.callback_query(F.data.startswith("release:"), IsMaster())
async def release_order(callback: CallbackQuery, db: Database, bot: Bot, config: Config):
    order_id = _order_id(callback)
    if not await db.release_order(order_id, callback.from_user.id):
        await callback.answer("Эта заявка уже не у вас в работе.", show_alert=True)
        return
    await callback.answer("Вы отказались от заявки")
    await callback.message.edit_reply_markup(reply_markup=None)
    order = await db.get_order(order_id)
    await send_to_customer(bot, db, order["customer_id"],
                           t(order["customer_lang"], "notify_released", id=order_id),
                           source="system", order_id=order_id)
    await announce_order(bot, db, config, order, title=f"🔁 Заявка №{order_id} снова свободна")


# ---------- закрытие заявки ----------

@router.callback_query(F.data.startswith("done:"), IsMaster())
async def start_done(callback: CallbackQuery, state: FSMContext, db: Database):
    order_id = _order_id(callback)
    order = await db.get_order(order_id)
    if not order or order["master_id"] != callback.from_user.id or order["status"] != "assigned":
        await callback.answer("Эта заявка уже не у вас в работе.", show_alert=True)
        return
    await callback.answer()
    await state.clear()
    await state.update_data(order_id=order_id)
    services = await db.services(order["category_code"])
    if len(services) == 1:
        await state.update_data(product_id=services[0]["product_id"],
                                product_name=services[0]["product_name"])
        await ask_price(callback.message, state)
        return
    await state.set_state(CompleteForm.service)
    await callback.message.answer(f"Заявка №{order_id}: какая работа выполнена?",
                                  reply_markup=kb.services_kb(services))


@router.callback_query(CompleteForm.service, F.data.startswith("svc:"))
async def choose_service(callback: CallbackQuery, state: FSMContext, db: Database):
    value = callback.data.split(":", 1)[1]
    await callback.answer()
    if value == "cancel":
        await state.clear()
        await callback.message.edit_text("Закрытие заявки отменено.")
        return
    data = await state.get_data()
    order = await db.get_order(data["order_id"])
    service = next((s for s in await db.services(order["category_code"])
                    if s["product_id"] == int(value)), None)
    if service is None:
        return
    await state.update_data(product_id=service["product_id"], product_name=service["product_name"])
    await callback.message.edit_text(f"Работа: <b>{esc(service['product_name'])}</b>")
    await ask_price(callback.message, state)


async def ask_price(message: Message, state: FSMContext) -> None:
    await state.set_state(CompleteForm.price)
    await message.answer("Сколько заплатил заказчик за работу? Отправьте сумму числом, например 15000.")


@router.message(CompleteForm.price)
async def got_price(message: Message, state: FSMContext, config: Config):
    raw = (message.text or "").replace(" ", "").replace(",", ".")
    try:
        price = Decimal(raw)
    except InvalidOperation:
        price = None
    if price is None or price < 0 or price > Decimal("100000000"):
        await message.answer("Нужна сумма числом, например 15000.")
        return
    await state.update_data(price=str(price))
    await state.set_state(CompleteForm.confirm)
    data = await state.get_data()
    fee = f"\nВыезд: {config.visit_fee:,.0f} {config.currency}" if config.visit_fee else ""
    await message.answer(
        f"Заявка №{data['order_id']}\n"
        f"Работа: {esc(data['product_name'])}\n"
        f"Сумма: {price:,.0f} {config.currency}{fee}\n\nЗакрыть заявку?",
        reply_markup=kb.done_confirm_kb(),
    )


@router.callback_query(CompleteForm.confirm, F.data.startswith("dconfirm:"))
async def confirm_done(callback: CallbackQuery, state: FSMContext, db: Database, bot: Bot,
                       config: Config):
    data = await state.get_data()
    await state.clear()
    await callback.message.edit_reply_markup(reply_markup=None)
    if callback.data != "dconfirm:yes":
        await callback.answer("Отменено")
        return

    order_id = data["order_id"]
    ok = await db.complete_order(order_id, callback.from_user.id, data["product_id"],
                                 Decimal(data["price"]), config.visit_fee)
    if not ok:
        await callback.answer("Эта заявка уже не у вас в работе.", show_alert=True)
        return
    await callback.answer("Заявка закрыта")
    await callback.message.answer(f"✅ Заявка №{order_id} закрыта. Спасибо!")

    order = await db.get_order(order_id)
    await send_to_customer(bot, db, order["customer_id"],
                           t(order["customer_lang"], "notify_done", id=order_id),
                           source="system", order_id=order_id)
    await notify_managers(
        bot, config,
        f"✅ {esc(order['master_name'])} закрыл заявку №{order_id}: "
        f"{esc(data['product_name'])}, {Decimal(data['price']):,.0f} {config.currency}",
    )
