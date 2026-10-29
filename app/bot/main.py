import asyncio
import logging

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, BotCommandScopeChat, CallbackQuery, Message

from ..agent import create_agent
from ..config import load_config
from ..db import Database
from ..texts import DEFAULT_LANG, LANGS, t
from . import crm, customer, followups, manager, master, onboarding
from . import keyboards as kb
from .common import user_lang

log = logging.getLogger(__name__)

fallback_router = Router(name="fallback")


@fallback_router.callback_query()
async def stale_callback(callback: CallbackQuery, db: Database):
    lang = await user_lang(db, callback.from_user.id)
    await callback.answer(t(lang, "expired"), show_alert=True)


@fallback_router.message(F.chat.type == "private")
async def fallback(message: Message, db: Database):
    lang = await db.get_lang(message.from_user.id)
    if lang is None:
        await message.answer(t(DEFAULT_LANG, "choose_language"), reply_markup=kb.language_kb())
    else:
        await message.answer(t(lang, "expired"))


async def set_commands(bot: Bot, manager_ids: list[int]) -> None:
    def commands(lang: str) -> list[BotCommand]:
        return [
            BotCommand(command="start", description=t(lang, "cmd_start")),
            BotCommand(command="orders", description=t(lang, "cmd_orders")),
            BotCommand(command="language", description=t(lang, "cmd_language")),
            BotCommand(command="cancel", description=t(lang, "cmd_cancel")),
            BotCommand(command="stop", description=t(lang, "cmd_stop")),
        ]

    staff = [
        BotCommand(command="leads", description="Воронка мастеров"),
        BotCommand(command="tasks", description="Кому написать сегодня"),
        BotCommand(command="help", description="Как работать с ботом и агентом"),
        BotCommand(command="reset", description="Новый диалог с агентом"),
        BotCommand(command="start", description="Меню: мастер или заказчик"),
    ]
    try:
        await bot.set_my_commands(commands(DEFAULT_LANG))
        for lang in LANGS:
            await bot.set_my_commands(commands(lang), language_code=lang)
    except Exception:
        log.warning("Не удалось обновить меню команд", exc_info=True)
    for chat_id in manager_ids:
        try:
            await bot.set_my_commands(staff, scope=BotCommandScopeChat(chat_id=chat_id))
        except Exception as e:
            # Telegram не знает чат, пока менеджер сам не написал боту /start
            log.warning("Меню менеджера %s не установлено (%s). Напишите боту /start "
                        "и перезапустите его", chat_id, e)


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    config = load_config()

    if not config.manager_chat_ids:
        log.warning("MANAGER_CHAT_IDS пуст: заявки сохраняются, но менеджерам не приходят, "
                    "а агент недоступен. Отправьте боту /myid и впишите id в .env")

    db = Database(config.database_url)
    await db.connect()
    agent = await create_agent(config, db)

    bot = Bot(config.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    # db, config и agent попадают в хендлеры как именованные аргументы
    dp = Dispatcher(storage=MemoryStorage(), db=db, config=config, agent=agent)
    # порядок важен: сценарии с состояниями раньше, чем «всё остальное»
    dp.include_routers(customer.router, onboarding.router, master.router, crm.router,
                       manager.router, fallback_router)

    await set_commands(bot, config.manager_chat_ids)
    me = await bot.get_me()
    log.info("Бот запущен: @%s, агент %s", me.username, "включён" if agent else "выключен")
    worker = asyncio.create_task(followups.run(bot, db, config))
    try:
        await dp.start_polling(bot)
    finally:
        worker.cancel()
        await db.close()
