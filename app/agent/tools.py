"""Инструменты агента: чтение баз только на чтение, работа с лидами CRM и подготовка рассылки.
Отправляет рассылку не агент, а менеджер — кнопкой после превью (app/notify.py)."""

import json
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, time
from decimal import Decimal

import asyncpg

from ..db import Database
from ..leads import from_local, to_local
from ..phone import normalize_phone
from ..texts import CATEGORIES, DISTRICTS, FOLLOW_UP_REASONS, REFUSAL_REASONS

MAX_ROWS = 200
MAX_RESULT_CHARS = 30_000
MAX_RECIPIENTS = 1000
MAX_MESSAGE_CHARS = 3500  # лимит Telegram — 4096, оставляем запас
STATEMENT_TIMEOUT = "10s"

# Статусы, которые агент может поставить сам. «Подключён» — только кнопкой менеджера
# в карточке лида: при подключении мастер начинает получать заявки.
AGENT_STATUSES = ("new", "contacted", "negotiation", "registration", "refused")

LOCAL_TIME = {
    "type": ["string", "null"],
    "description": "Местное время Еревана: 'YYYY-MM-DD HH:MM' или 'YYYY-MM-DD' (тогда 10:00). null — не менять.",
}


def _nullable_enum(values) -> dict:
    return {"type": ["string", "null"], "enum": [*values, None]}


TOOL_DEFINITIONS = [
    {
        "name": "run_sql",
        "description": (
            "Выполняет один SELECT-запрос (PostgreSQL) в выбранной базе и возвращает колонки и "
            f"строки (не больше {MAX_ROWS}). Транзакция только на чтение, таймаут {STATEMENT_TIMEOUT}. "
            "operational — живая база бота, dwh — хранилище и витрины, обновляется раз в сутки."
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
        "name": "add_lead",
        "description": (
            "Добавляет потенциального мастера в CRM (например, менеджер нашёл контакт сам). "
            "Перед добавлением проверь через run_sql, что такого лида ещё нет (по телефону или имени)."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "full_name": {"type": "string"},
                "phone": {"type": ["string", "null"]},
                "username": {"type": ["string", "null"], "description": "Telegram username без @."},
                "categories": {"type": "array", "items": {"type": "string", "enum": list(CATEGORIES)}},
                "districts": {"type": "array", "items": {"type": "string", "enum": list(DISTRICTS)}},
                "source": {"type": "string", "enum": ["manual", "referral"]},
                "next_contact_at": LOCAL_TIME,
                "follow_up_reason": _nullable_enum(FOLLOW_UP_REASONS),
                "note": {"type": ["string", "null"], "description": "Заметка в историю лида."},
            },
            "required": ["full_name", "phone", "username", "categories", "districts", "source",
                         "next_contact_at", "follow_up_reason", "note"],
            "additionalProperties": False,
        },
    },
    {
        "name": "update_lead",
        "description": (
            "Обновляет лида: статус, причину отказа, факт контакта, следующий контакт, оплату, "
            "заметку. Каждое изменение пишется в историю лида. Поля со значением null или false "
            "не меняются. Статус «connected» ставит только менеджер кнопкой «Подключить»."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "lead_id": {"type": "integer"},
                "status": _nullable_enum(AGENT_STATUSES),
                "refusal_reason": {**_nullable_enum(REFUSAL_REASONS),
                                   "description": "Обязательна, если status = refused."},
                "contacted_now": {"type": "boolean", "description": "Менеджер только что связался с лидом."},
                "next_contact_at": LOCAL_TIME,
                "follow_up_reason": _nullable_enum(FOLLOW_UP_REASONS),
                "clear_next_contact": {"type": "boolean", "description": "Следующий контакт не нужен."},
                "payment_received": {"type": "boolean", "description": "Подключённый мастер оплатил."},
                "note": {"type": ["string", "null"]},
            },
            "required": ["lead_id", "status", "refusal_reason", "contacted_now", "next_contact_at",
                         "follow_up_reason", "clear_next_contact", "payment_received", "note"],
            "additionalProperties": False,
        },
    },
    {
        "name": "prepare_broadcast",
        "description": (
            "Готовит рассылку одного текста через Telegram-бота: заказчикам (customer_id) или "
            "мастерам-лидам (lead_id). Ничего не отправляет: менеджер увидит превью и подтвердит "
            "или отменит. Получатели без Telegram, без согласия на сообщения или заблокировавшие "
            "бота отбрасываются, их список вернётся в ответе."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "audience": {"type": "string", "enum": ["leads", "customers"]},
                "recipient_ids": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "lead_id для audience=leads, customer_id для audience=customers.",
                },
                "text": {
                    "type": "string",
                    "description": "Текст на языке получателей, обычный текст без разметки.",
                },
                "order_id": {
                    "type": ["integer", "null"],
                    "description": "Номер заявки, если сообщение заказчикам о конкретной заявке, иначе null.",
                },
            },
            "required": ["audience", "recipient_ids", "text", "order_id"],
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


def _parse_local(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.strip())
    except ValueError as e:
        raise ToolError(f"Не понял время «{value}»: нужно 'YYYY-MM-DD HH:MM'.") from e
    if len(value.strip()) == 10:
        parsed = datetime.combine(parsed.date(), time(10))
    return from_local(parsed.replace(tzinfo=None))


def _lead_summary(lead: dict) -> dict:
    return {
        "lead_id": lead["lead_id"],
        "full_name": lead["full_name"],
        "status": lead["status"],
        "refusal_reason": lead["refusal_reason"],
        "next_contact_at_local": f"{to_local(lead['next_contact_at']):%Y-%m-%d %H:%M}"
        if lead["next_contact_at"] else None,
        "follow_up_reason": lead["follow_up_reason"],
        "contact_consent": lead["contact_consent"],
        "has_telegram": lead["tg_user_id"] is not None,
    }


class AgentTools:
    definitions = TOOL_DEFINITIONS

    def __init__(self, db: Database, operational: asyncpg.Pool, dwh: asyncpg.Pool | None,
                 script_version: str = "v1"):
        self.db = db
        self.pools = {"operational": operational, "dwh": dwh}
        self.script_version = script_version

    async def execute(self, name: str, args: dict, ctx: TurnContext) -> str:
        handlers = {
            "run_sql": lambda: self.run_sql(args["database"], args["query"]),
            "add_lead": lambda: self.add_lead(args, ctx),
            "update_lead": lambda: self.update_lead(args, ctx),
            "prepare_broadcast": lambda: self.prepare_broadcast(
                args["audience"], args["recipient_ids"], args["text"], args.get("order_id"), ctx),
        }
        if name not in handlers:
            raise ToolError(f"Неизвестный инструмент {name}")
        return json.dumps(await handlers[name](), ensure_ascii=False, default=str)

    # ---------- чтение ----------

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

    # ---------- CRM ----------

    async def add_lead(self, args: dict, ctx: TurnContext) -> dict:
        name = args["full_name"].strip()
        if not name:
            raise ToolError("Нужно имя мастера.")
        phone = None
        if args.get("phone"):
            phone = normalize_phone(args["phone"])
            if phone is None:
                raise ToolError(f"Не похоже на телефон: {args['phone']}")
        next_at = _parse_local(args.get("next_contact_at"))
        lead = await self.db.leads.add_manual(
            full_name=name, phone=phone, username=(args.get("username") or "").lstrip("@") or None,
            categories=[c for c in CATEGORIES if c in args["categories"]],
            districts=[d for d in DISTRICTS if d in args["districts"]],
            source=args["source"], script_version=self.script_version, actor=ctx.chat_id,
            via="agent", next_contact_at=next_at,
            follow_up_reason=args.get("follow_up_reason") or ("first_contact" if next_at else None),
            note=args.get("note"),
        )
        return {"created": _lead_summary(lead)}

    async def update_lead(self, args: dict, ctx: TurnContext) -> dict:
        leads, lead_id, actor = self.db.leads, args["lead_id"], ctx.chat_id
        lead = await leads.get(lead_id)
        if lead is None:
            raise ToolError(f"Лида №{lead_id} нет.")
        done = []

        if args.get("contacted_now"):
            lead = await leads.contacted(lead_id, via="agent", actor=actor)
            done.append("контакт записан")
        status = args.get("status")
        if status == "refused":
            if not args.get("refusal_reason"):
                raise ToolError("Для отказа нужна refusal_reason.")
            lead = await leads.refuse(lead_id, args["refusal_reason"], via="agent", actor=actor,
                                      comment=args.get("note"))
            done.append("отказ записан")
        elif status and status != lead["status"]:
            if lead["status"] == "connected":
                raise ToolError("Лид уже подключён: менять ему статус воронки нельзя, только отказ.")
            lead = await leads.set_status(lead_id, status, via="agent", actor=actor)
            done.append(f"статус {status}")
        next_at = _parse_local(args.get("next_contact_at"))
        if next_at:
            lead = await leads.schedule(lead_id, next_at, args.get("follow_up_reason"), via="agent",
                                        actor=actor)
            done.append("следующий контакт запланирован")
        elif args.get("clear_next_contact"):
            lead = await leads.clear_next(lead_id, via="agent", actor=actor)
            done.append("следующий контакт снят")
        if args.get("payment_received"):
            if lead["status"] != "connected":
                raise ToolError("Оплату можно отметить только у подключённого мастера.")
            lead = await leads.mark_paid(lead_id, via="agent", actor=actor)
            done.append("оплата записана")
        if args.get("note") and status != "refused":
            await leads.note(lead_id, args["note"], via="agent", actor=actor)
            done.append("заметка добавлена")
        return {"done": done or ["ничего не изменилось"], "lead": _lead_summary(lead)}

    # ---------- рассылки ----------

    async def prepare_broadcast(self, audience: str, recipient_ids: list[int], text: str,
                                order_id: int | None, ctx: TurnContext) -> dict:
        text = text.strip()
        if not text:
            raise ToolError("Пустой текст сообщения.")
        if len(text) > MAX_MESSAGE_CHARS:
            raise ToolError(f"Текст длиннее {MAX_MESSAGE_CHARS} символов — сократите.")
        ids = list(dict.fromkeys(recipient_ids))
        if not ids:
            raise ToolError("Не указаны получатели.")
        if len(ids) > MAX_RECIPIENTS:
            raise ToolError(f"Больше {MAX_RECIPIENTS} получателей за раз — разбейте рассылку.")
        if order_id is not None and await self.db.get_order(order_id) is None:
            raise ToolError(f"Заявки №{order_id} нет.")

        skipped: dict[str, list[int]] = {"unknown": [], "no_consent": []}
        if audience == "leads":
            found = {r["lead_id"]: r for r in await self.db.leads.by_ids(ids)}
            skipped["no_telegram"] = [i for i in ids if i in found and found[i]["tg_user_id"] is None]
        else:
            found = {r["customer_id"]: r for r in await self.db.customers_by_ids(ids)}
            skipped["blocked_bot"] = [i for i in ids if i in found and found[i]["is_blocked"]]
        skipped["unknown"] = [i for i in ids if i not in found]
        skipped["no_consent"] = [i for i in ids if i in found and found[i]["contact_consent"] is False]
        excluded = {i for group in skipped.values() for i in group}
        recipients = [i for i in ids if i not in excluded]
        if not recipients:
            raise ToolError(f"Ни одного получателя не осталось: {skipped}")

        broadcast_id = await self.db.create_broadcast(ctx.chat_id, audience, text, recipients, order_id)
        ctx.broadcast_ids.append(broadcast_id)
        return {
            "broadcast_id": broadcast_id,
            "status": "ждёт подтверждения менеджера",
            "recipients": len(recipients),
            "languages": dict(Counter(found[i]["lang"] for i in recipients)),
            "skipped": {k: v for k, v in skipped.items() if v},
        }
