"""Инструменты агента: чтение баз только на чтение и подготовка рассылки.
Отправляет рассылку не агент, а менеджер — кнопкой после превью (app/notify.py)."""

import json
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal

import asyncpg

from ..db import Database

MAX_ROWS = 200
MAX_RESULT_CHARS = 30_000
MAX_RECIPIENTS = 1000
MAX_MESSAGE_CHARS = 3500  # лимит Telegram — 4096, оставляем запас
STATEMENT_TIMEOUT = "10s"

TOOL_DEFINITIONS = [
    {
        "name": "run_sql",
        "description": (
            "Выполняет один SELECT-запрос (PostgreSQL) в выбранной базе и возвращает колонки и "
            f"строки (не больше {MAX_ROWS}). Транзакция только на чтение, таймаут {STATEMENT_TIMEOUT}. "
            "operational — живая база бота, dwh — хранилище, обновляется раз в сутки."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "database": {"type": "string", "enum": ["operational", "dwh"]},
                "query": {"type": "string", "description": "Один SQL-запрос без точки с запятой в конце."},
            },
            "required": ["database", "query"],
            "additionalProperties": False,
        },
    },
    {
        "name": "prepare_broadcast",
        "description": (
            "Готовит рассылку одного текста выбранным заказчикам через Telegram-бота. Ничего не "
            "отправляет: менеджер увидит превью и подтвердит или отменит. Заблокировавшие бота и "
            "неизвестные id отбрасываются, их список вернётся в ответе."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "customer_ids": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "customer_id получателей из таблицы customers.",
                },
                "text": {
                    "type": "string",
                    "description": "Текст сообщения на языке получателей, обычный текст без разметки.",
                },
                "order_id": {
                    "type": ["integer", "null"],
                    "description": "Номер заявки, если сообщение о конкретной заявке, иначе null.",
                },
            },
            "required": ["customer_ids", "text", "order_id"],
            "additionalProperties": False,
        },
    },
]


class ToolError(Exception):
    """Ошибка, которую стоит показать модели: она поправит запрос и попробует снова."""


@dataclass
class TurnContext:
    chat_id: int  # кто попросил: chat id менеджера (0 — консоль)
    broadcast_ids: list[int] = field(default_factory=list)


def _jsonable(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    return value


class AgentTools:
    definitions = TOOL_DEFINITIONS

    def __init__(self, db: Database, operational: asyncpg.Pool, dwh: asyncpg.Pool | None):
        self.db = db
        self.pools = {"operational": operational, "dwh": dwh}

    async def execute(self, name: str, args: dict, ctx: TurnContext) -> str:
        if name == "run_sql":
            result = await self.run_sql(args["database"], args["query"])
        elif name == "prepare_broadcast":
            result = await self.prepare_broadcast(args["customer_ids"], args["text"],
                                                  args.get("order_id"), ctx)
        else:
            raise ToolError(f"Неизвестный инструмент {name}")
        return json.dumps(result, ensure_ascii=False, default=str)

    async def run_sql(self, database: str, query: str) -> dict:
        pool = self.pools.get(database)
        if pool is None:
            raise ToolError(f"База {database} не подключена. Доступна: operational.")
        query = query.strip().rstrip(";")
        try:
            async with pool.acquire() as conn, conn.transaction(readonly=True):
                await conn.execute(f"SET LOCAL statement_timeout = '{STATEMENT_TIMEOUT}'")
                stmt = await conn.prepare(query)
                columns = [a.name for a in stmt.get_attributes()]
                rows, truncated = [], False
                async for record in stmt.cursor():
                    if len(rows) == MAX_ROWS:
                        truncated = True
                        break
                    rows.append([_jsonable(v) for v in record.values()])
        except asyncpg.PostgresError as e:
            raise ToolError(f"Ошибка PostgreSQL: {e}") from e

        result = {"columns": columns, "rows": rows, "truncated": truncated}
        if len(json.dumps(result, ensure_ascii=False, default=str)) > MAX_RESULT_CHARS:
            # слишком широкий результат: отдаём начало и просим сузить запрос
            while rows and len(json.dumps(result, ensure_ascii=False, default=str)) > MAX_RESULT_CHARS:
                rows = rows[: len(rows) // 2]
                result["rows"] = rows
            result["truncated"] = True
            result["note"] = "Результат обрезан по размеру — выберите меньше колонок или строк."
        return result

    async def prepare_broadcast(self, customer_ids: list[int], text: str, order_id: int | None,
                                ctx: TurnContext) -> dict:
        text = text.strip()
        if not text:
            raise ToolError("Пустой текст сообщения.")
        if len(text) > MAX_MESSAGE_CHARS:
            raise ToolError(f"Текст длиннее {MAX_MESSAGE_CHARS} символов — сократите.")
        ids = list(dict.fromkeys(customer_ids))
        if not ids:
            raise ToolError("Не указаны получатели.")
        if len(ids) > MAX_RECIPIENTS:
            raise ToolError(f"Больше {MAX_RECIPIENTS} получателей за раз — разбейте рассылку.")
        if order_id is not None and await self.db.get_order(order_id) is None:
            raise ToolError(f"Заявки №{order_id} нет.")

        found = {c["customer_id"]: c for c in await self.db.customers_by_ids(ids)}
        unknown = [i for i in ids if i not in found]
        blocked = [i for i in ids if i in found and found[i]["is_blocked"]]
        recipients = [i for i in ids if i in found and not found[i]["is_blocked"]]
        if not recipients:
            raise ToolError("Ни одного получателя: все id неизвестны или заблокировали бота.")

        broadcast_id = await self.db.create_broadcast(ctx.chat_id, text, recipients, order_id)
        ctx.broadcast_ids.append(broadcast_id)
        return {
            "broadcast_id": broadcast_id,
            "status": "ждёт подтверждения менеджера",
            "recipients": len(recipients),
            "languages": dict(Counter(found[i]["lang"] for i in recipients)),
            "skipped_blocked": blocked,
            "unknown_ids": unknown,
        }
