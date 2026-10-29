"""Общее для хендлеров: фильтры ролей, экранирование, карточка заявки для мастеров и менеджеров."""

import html
import logging

from aiogram import Bot
from aiogram.filters import BaseFilter
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from ..config import Config
from ..db import Database
from ..leads import to_local
from ..texts import DEFAULT_LANG, t
from .keyboards import REFUSAL_RU, lead_kb

log = logging.getLogger(__name__)

STATUS_RU = {
    "new": "🟢 Новая",
    "assigned": "👷 В работе",
    "done": "✅ Выполнена",
    "cancelled": "⚪️ Отменена",
}


def esc(text: str | None) -> str:
    return html.escape(text or "", quote=False)


async def user_lang(db: Database, user_id: int) -> str:
    return await db.get_lang(user_id) or DEFAULT_LANG


def is_manager(config: Config, user_id: int, chat_id: int | None = None) -> bool:
    # менеджер пишет лично или из группы, id которой указан в MANAGER_CHAT_IDS
    return user_id in config.manager_chat_ids or (chat_id is not None and chat_id in config.manager_chat_ids)


class IsManager(BaseFilter):
    async def __call__(self, event: Message | CallbackQuery, config: Config) -> bool:
        chat = event.chat if isinstance(event, Message) else (event.message.chat if event.message else None)
        return is_manager(config, event.from_user.id, chat.id if chat else None)


class IsMaster(BaseFilter):
    async def __call__(self, event: Message | CallbackQuery, db: Database) -> bool:
        master = await db.get_master(event.from_user.id)
        return bool(master and master["is_active"])


def order_card(order: dict, *, contacts: bool, title: str | None = None) -> str:
    """Карточка заявки на русском. contacts=False — без телефона и точного адреса:
    так её видят мастера, пока никто не взял заявку."""
    title = title or f"Заявка №{order['order_id']}"
    lines = [
        f"<b>{esc(title)}</b>",
        f"<b>Статус:</b> {STATUS_RU[order['status']]}",
        "",
        f"<b>Категория:</b> {esc(t('ru', 'cat_' + order['category_code']))}",
        f"<b>Проблема:</b> {esc(order['description'])}",
        f"<b>Район:</b> {esc(t('ru', 'dist_' + order['district']) if order['district'] else '—')}",
    ]
    if order.get("photo_file_id"):
        lines.append("<b>Фото:</b> есть")
    if contacts:
        name = f'<a href="tg://user?id={order["customer_id"]}">{esc(order["contact_name"])}</a>'
        username = f" (@{esc(order['customer_username'])})" if order["customer_username"] else ""
        lines += [
            f"<b>Адрес:</b> {esc(order['address'])}",
            f"<b>Способ связи:</b> {esc(t('ru', 'contact_' + order['contact_method']))}",
        ]
        if order["phone"]:
            lines.append(f"<b>Телефон:</b> +{order['phone']}")
        lines.append(f"<b>Заказчик:</b> {name}{username}, язык: {order['customer_lang']}")
    if order.get("master_name"):
        lines.append(f"<b>Мастер:</b> {esc(order['master_name'])}")
    return "\n".join(lines)


LEAD_STATUS_RU = {
    "new": "🆕 Новый контакт",
    "contacted": "💬 Связались",
    "negotiation": "🤝 Переговоры",
    "registration": "📝 Регистрация",
    "connected": "✅ Подключён",
    "refused": "🚫 Отказ",
}

FOLLOW_UP_RU = {
    "first_contact": "Написать впервые",
    "send_info": "Отправить информацию об услуге",
    "call": "Созвониться",
    "decide_later": "Обещал решить позже — напомнить",
    "no_response": "Перестал отвечать — напомнить",
    "finish_registration": "Помочь завершить подключение",
    "check_activity": "Проверить активность",
}

SOURCE_RU = {"bot": "пришёл в бота", "manual": "добавлен вручную", "referral": "по рекомендации"}


def lead_card(lead: dict, *, title: str | None = None) -> str:
    """Карточка лида для менеджера: кто, на каком этапе и какой следующий шаг."""
    name = esc(lead["full_name"])
    if lead["tg_user_id"]:
        name = f'<a href="tg://user?id={lead["tg_user_id"]}">{name}</a>'
    if lead["username"]:
        name += f" (@{esc(lead['username'])})"
    title = title or f"👷 Мастер · лид №{lead['lead_id']}"
    lines = [f"<b>{esc(title)}</b>", name, "",
             f"<b>Статус:</b> {LEAD_STATUS_RU[lead['status']]}"]
    if lead["status"] == "refused" and lead["refusal_reason"]:
        reason = REFUSAL_RU.get(lead["refusal_reason"], lead["refusal_reason"])
        lines.append(f"<b>Причина отказа:</b> {esc(reason)}"
                     + (f" ({esc(lead['refusal_comment'])})" if lead["refusal_comment"] else ""))
    if lead["categories"]:
        lines.append("<b>Специализации:</b> " + ", ".join(
            esc(t("ru", "cat_" + c)) for c in lead["categories"]))
    if lead["districts"]:
        lines.append("<b>Районы:</b> " + ", ".join(esc(t("ru", "dist_" + d)) for d in lead["districts"]))
    if lead["phone"]:
        lines.append(f"<b>Телефон:</b> +{esc(lead['phone'].lstrip('+'))}")
    consent = {True: "да", False: "нет (просил не писать)", None: "не спрашивали"}[lead["contact_consent"]]
    lines += [
        f"<b>Источник:</b> {SOURCE_RU.get(lead['source'], lead['source'])}, сценарий {esc(lead['script_version'])}",
        f"<b>Напоминания и новости:</b> {consent}",
        f"<b>Последний контакт:</b> "
        + (f"{to_local(lead['last_contact_at']):%d.%m %H:%M}" if lead["last_contact_at"] else "—"),
    ]
    if lead["next_contact_at"]:
        reason = FOLLOW_UP_RU.get(lead["follow_up_reason"], "Связаться")
        lines.append(f"<b>Следующий шаг:</b> {to_local(lead['next_contact_at']):%d.%m %H:%M} — {reason}")
    else:
        lines.append("<b>Следующий шаг:</b> —")
    return "\n".join(lines)


def contact_buttons(order: dict) -> list[InlineKeyboardButton]:
    buttons = []
    if order["contact_method"] == "whatsapp" and order["phone"]:
        buttons.append(InlineKeyboardButton(text="💬 WhatsApp", url=f"https://wa.me/{order['phone']}"))
    if order["contact_method"] == "telegram" and order["customer_username"]:
        buttons.append(InlineKeyboardButton(text="✈️ Telegram",
                                            url=f"https://t.me/{order['customer_username']}"))
    return buttons


async def send_lead_card(bot: Bot, config: Config, lead: dict, title: str) -> None:
    await notify_managers(bot, config, lead_card(lead, title=title), markup=lead_kb(lead))


async def notify_managers(bot: Bot, config: Config, text: str,
                          markup: InlineKeyboardMarkup | None = None,
                          photo_file_id: str | None = None) -> None:
    for chat_id in config.manager_chat_ids:
        try:
            sent = await bot.send_message(chat_id, text, reply_markup=markup)
            if photo_file_id:
                await sent.reply_photo(photo_file_id)
        except Exception:
            log.exception("Не удалось отправить уведомление менеджеру %s", chat_id)
