from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from ..texts import CATEGORIES, CONTACT_METHODS, DISTRICTS, LANG_BUTTONS, t


def _one_row(*buttons: InlineKeyboardButton) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[list(buttons)])


# ---------- заказчик ----------

def language_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for code, label in LANG_BUTTONS.items():
        kb.button(text=label, callback_data=f"lang:{code}")
    kb.adjust(1)
    return kb.as_markup()


def categories_kb(lang: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for key in CATEGORIES:
        kb.button(text=t(lang, f"cat_{key}"), callback_data=f"cat:{key}")
    # по две в ряд, последняя («Другое») на всю ширину
    kb.adjust(*([2] * (len(CATEGORIES) // 2)), *([1] if len(CATEGORIES) % 2 else []))
    return kb.as_markup()


def districts_kb(lang: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for key in DISTRICTS:
        kb.button(text=t(lang, f"dist_{key}"), callback_data=f"dist:{key}")
    kb.adjust(*([2] * ((len(DISTRICTS) - 1) // 2)), 1)
    return kb.as_markup()


def contact_kb(lang: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for key in CONTACT_METHODS:
        kb.button(text=t(lang, f"contact_{key}"), callback_data=f"contact:{key}")
    kb.adjust(1)
    return kb.as_markup()


def phone_kb(lang: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=t(lang, "share_phone_btn"), request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def confirm_kb(lang: str) -> InlineKeyboardMarkup:
    return _one_row(
        InlineKeyboardButton(text=t(lang, "btn_send"), callback_data="confirm:send"),
        InlineKeyboardButton(text=t(lang, "btn_cancel"), callback_data="confirm:cancel"),
    )


def cancel_order_kb(lang: str, order_ids: list[int]) -> InlineKeyboardMarkup | None:
    if not order_ids:
        return None
    kb = InlineKeyboardBuilder()
    for order_id in order_ids:
        kb.button(text=t(lang, "btn_cancel_order", id=order_id), callback_data=f"ocancel:{order_id}")
    kb.adjust(2)
    return kb.as_markup()


# ---------- мастер ----------

def take_kb(order_id: int) -> InlineKeyboardMarkup:
    return _one_row(InlineKeyboardButton(text="🙋 Взять заявку", callback_data=f"take:{order_id}"))


def master_order_kb(order_id: int) -> InlineKeyboardMarkup:
    return _one_row(
        InlineKeyboardButton(text="✅ Выполнено", callback_data=f"done:{order_id}"),
        InlineKeyboardButton(text="↩️ Отказаться", callback_data=f"release:{order_id}"),
    )


def services_kb(services: list[dict]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for s in services:
        kb.button(text=s["product_name"], callback_data=f"svc:{s['product_id']}")
    kb.button(text="❌ Отмена", callback_data="svc:cancel")
    kb.adjust(1)
    return kb.as_markup()


def done_confirm_kb() -> InlineKeyboardMarkup:
    return _one_row(
        InlineKeyboardButton(text="✅ Закрыть заявку", callback_data="dconfirm:yes"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="dconfirm:no"),
    )


# ---------- менеджер ----------

def master_request_kb(user_id: int) -> InlineKeyboardMarkup:
    return _one_row(
        InlineKeyboardButton(text="✅ Принять", callback_data=f"mapprove:{user_id}"),
        InlineKeyboardButton(text="❌ Отклонить", callback_data=f"mreject:{user_id}"),
    )


def broadcast_kb(broadcast_id: int) -> InlineKeyboardMarkup:
    return _one_row(
        InlineKeyboardButton(text="✅ Отправить", callback_data=f"bsend:{broadcast_id}"),
        InlineKeyboardButton(text="❌ Отмена", callback_data=f"bcancel:{broadcast_id}"),
    )
