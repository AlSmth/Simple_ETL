"""Агент в терминале: python -m app.agent

Те же инструменты, что и в Telegram. Подготовленную рассылку отправляет бот после вашего «y»
(нужен BOT_TOKEN); без токена рассылки только сохраняются в базе."""

import asyncio
import logging

from aiogram import Bot

from ..config import load_config
from ..db import Database
from ..notify import run_broadcast
from . import create_agent

CONSOLE_CHAT_ID = 0  # created_by у рассылок, подготовленных из консоли


async def confirm(prompt: str) -> bool:
    answer = await asyncio.to_thread(input, prompt)
    return answer.strip().lower() in ("y", "yes", "д", "да")


async def main() -> None:
    logging.basicConfig(level=logging.WARNING)
    config = load_config(require_token=False)
    db = Database(config.database_url)
    await db.connect()
    agent = await create_agent(config, db)
    if agent is None:
        raise SystemExit("Задайте ANTHROPIC_API_KEY в .env")
    bot = Bot(config.bot_token) if config.bot_token else None

    print("Агент менеджера. Пустая строка или Ctrl+C — выход, /reset — новый диалог.")
    try:
        while True:
            text = (await asyncio.to_thread(input, "\nВы: ")).strip()
            if not text:
                break
            if text == "/reset":
                agent.reset(CONSOLE_CHAT_ID)
                print("Новый диалог.")
                continue
            reply = await agent.ask(CONSOLE_CHAT_ID, text)
            print(f"\nАгент: {reply.text}")

            for broadcast_id in reply.broadcast_ids:
                broadcast = await db.get_broadcast(broadcast_id)
                print(f"\n--- Рассылка №{broadcast_id}: получателей {len(broadcast['customer_ids'])}\n"
                      f"{broadcast['text']}\n---")
                if bot is None:
                    print("BOT_TOKEN не задан — рассылка останется неотправленной.")
                    continue
                if await confirm("Отправить? [y/N] "):
                    result = await run_broadcast(bot, db, broadcast_id)
                    note = result.summary() if result else f"рассылка №{broadcast_id} уже обработана"
                else:
                    await db.decide_broadcast(broadcast_id, "cancelled")
                    note = f"менеджер отменил рассылку №{broadcast_id}"
                print(note)
                agent.add_note(CONSOLE_CHAT_ID, note)
    except (KeyboardInterrupt, EOFError):
        pass
    finally:
        if bot:
            await bot.session.close()
        await db.close()


asyncio.run(main())
