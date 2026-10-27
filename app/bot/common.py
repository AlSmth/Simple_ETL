"""Общее для хендлеров: фильтры ролей, экранирование, карточка заявки для мастеров и менеджеров."""

import html
import logging
import re

from aiogram import Bot
from aiogram.filters import BaseFilter
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from ..config import Config
from ..db import Database
from ..texts import DEFAULT_LANG, t

log = logging.getLogger(__name__)

STATUS_RU = {
    "new": "🟢 Новая",
    "assigned": "👷 В работе",
    "done": "✅ Выполнена",
    "cancelled": "⚪️ Отменена",
}


def esc(text: str | None) -> str:
    return html.escape(text or "", quote=False)


def normalize_phone(raw: str) -> str | None:
    """Возвращает номер только из цифр в международном формате (по умолчанию Армения, +374)."""
    raw = raw.strip()
    if not re.fullmatch(r"[+\d\s()\-.]+", raw):
        return None
    digits = re.sub(r"\D", "", raw)
    if raw.startswith("00"):
        digits = digits[2:]
    if len(digits) == 8:  # 91123456
        digits = "374" + digits
    elif len(digits) == 9 and digits.startswith("0"):  # 091123456
        digits = "374" + digits[1:]
    return digits if 8 <= len(digits) <= 15 else None


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


def contact_buttons(order: dict) -> list[InlineKeyboardButton]:
    buttons = []
    if order["contact_method"] == "whatsapp" and order["phone"]:
        buttons.append(InlineKeyboardButton(text="💬 WhatsApp", url=f"https://wa.me/{order['phone']}"))
    if order["contact_method"] == "telegram" and order["customer_username"]:
        buttons.append(InlineKeyboardButton(text="✈️ Telegram",
                                            url=f"https://t.me/{order['customer_username']}"))
    return buttons


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
