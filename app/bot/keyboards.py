from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from ..texts import CATEGORIES, CONTACT_METHODS, DISTRICTS, LANG_BUTTONS, REFUSAL_REASONS, t


def _one_row(*buttons: InlineKeyboardButton) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[list(buttons)])


# ---------- общее ----------

def role_kb(lang: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text=t(lang, "role_master"), callback_data="role:master")
    kb.button(text=t(lang, "role_customer"), callback_data="role:customer")
    kb.adjust(1)
    return kb.as_markup()


# ---------- мастер: воронка подключения ----------

def master_about_kb(lang: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text=t(lang, "btn_master_join"), callback_data="mjoin")
    kb.button(text=t(lang, "btn_master_info"), callback_data="minfo")
    kb.button(text=t(lang, "btn_master_later"), callback_data="mlater")
    kb.adjust(1)
    return kb.as_markup()


def later_kb(lang: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text=t(lang, "later_think"), callback_data="mthink")
    for reason in REFUSAL_REASONS:
        kb.button(text=t(lang, f"reason_{reason}"), callback_data=f"mrefuse:{reason}")
    kb.adjust(1)
    return kb.as_markup()


def multiselect_kb(lang: str, field: str, codes, label_prefix: str, selected: list[str],
                   per_row: int = 2) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for code in codes:
        mark = "✓ " if code in selected else ""
        kb.button(text=mark + t(lang, f"{label_prefix}{code}"), callback_data=f"msel:{field}:{code}")
    kb.button(text=t(lang, "btn_done"), callback_data=f"mdone:{field}")
    count = len(list(codes))
    kb.adjust(*([per_row] * (count // per_row)), *([1] if count % per_row else []), 1)
    return kb.as_markup()


def consent_kb(lang: str) -> InlineKeyboardMarkup:
    return _one_row(
        InlineKeyboardButton(text=t(lang, "btn_yes"), callback_data="mconsent:yes"),
        InlineKeyboardButton(text=t(lang, "btn_no"), callback_data="mconsent:no"),
    )


def master_confirm_kb(lang: str) -> InlineKeyboardMarkup:
    return _one_row(
        InlineKeyboardButton(text=t(lang, "btn_send"), callback_data="mconfirm:send"),
        InlineKeyboardButton(text=t(lang, "btn_cancel"), callback_data="mconfirm:cancel"),
    )


def continue_kb(lang: str) -> InlineKeyboardMarkup:
    return _one_row(InlineKeyboardButton(text=t(lang, "btn_continue"), callback_data="mjoin"))


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


# ---------- менеджер: CRM ----------

REFUSAL_RU = {
    "conditions": "Не подошли условия",
    "price": "Дорого",
    "few_orders": "Мало заказов в районе",
    "complex_registration": "Сложная регистрация",
    "unclear_value": "Не понимает ценность",
    "missing_feature": "Нет нужной функции",
    "other": "Другое",
}


def lead_kb(lead: dict) -> InlineKeyboardMarkup:
    lid = lead["lead_id"]
    kb = InlineKeyboardBuilder()
    rows = []
    if lead["status"] == "registration" and lead["registration_done_at"] and lead["tg_user_id"]:
        kb.button(text="✅ Подключить", callback_data=f"mapprove:{lid}")
        kb.button(text="❌ Отклонить", callback_data=f"mreject:{lid}")
        rows.append(2)
    if lead["status"] != "refused":
        kb.button(text="📞 Связался", callback_data=f"lc:{lid}")
        if lead["status"] in ("new", "contacted"):
            kb.button(text="🤝 Переговоры", callback_data=f"ln:{lid}")
            rows.append(2)
        else:
            rows.append(1)
        kb.button(text="⏰ Завтра", callback_data=f"ls:{lid}:1")
        kb.button(text="⏰ 3 дня", callback_data=f"ls:{lid}:3")
        kb.button(text="⏰ Неделя", callback_data=f"ls:{lid}:7")
        rows.append(3)
        kb.button(text="🚫 Отказ", callback_data=f"lr:{lid}")
        if lead["status"] == "connected" and not lead["first_payment_at"]:
            kb.button(text="💳 Оплатил", callback_data=f"lp:{lid}")
            rows.append(2)
        else:
            rows.append(1)
    kb.adjust(*rows)
    return kb.as_markup()


def next_contact_kb(lead_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="⏰ Завтра", callback_data=f"ls:{lead_id}:1"),
        InlineKeyboardButton(text="⏰ 3 дня", callback_data=f"ls:{lead_id}:3"),
        InlineKeyboardButton(text="⏰ Неделя", callback_data=f"ls:{lead_id}:7"),
    ], [
        InlineKeyboardButton(text="Не нужно", callback_data=f"lx:{lead_id}"),
    ]])


def refusal_kb(lead_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for code, label in REFUSAL_RU.items():
        kb.button(text=label, callback_data=f"lrr:{lead_id}:{code}")
    kb.button(text="↩️ Назад", callback_data=f"lv:{lead_id}")
    kb.adjust(2, 2, 2, 1, 1)
    return kb.as_markup()


def broadcast_kb(broadcast_id: int) -> InlineKeyboardMarkup:
    return _one_row(
        InlineKeyboardButton(text="✅ Отправить", callback_data=f"bsend:{broadcast_id}"),
        InlineKeyboardButton(text="❌ Отмена", callback_data=f"bcancel:{broadcast_id}"),
    )
