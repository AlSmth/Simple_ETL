"""CRM: лиды — потенциальные и подключённые мастера. Каждое изменение пишется в lead_events,
поэтому история взаимодействий и время на каждом этапе восстанавливаются из базы."""

from datetime import datetime, timedelta

import asyncpg

YEREVAN_OFFSET = timedelta(hours=4)  # в базе время в UTC, людям показываем ереванское

MAX_AUTO_REMINDERS = 2               # больше двух напоминаний подряд — уже спам
AUTO_REMINDER_INTERVAL = timedelta(days=3)
FIRST_REMINDER_AFTER = timedelta(days=1)
DECIDE_LATER_AFTER = timedelta(days=3)

STAGE_ORDER = ("new", "contacted", "negotiation", "registration", "connected")

# Лид, которому бот напоминает сам: пришёл через бота, не закончил анкету и не просил не писать
AUTO_REMINDER_SQL = """
    source = 'bot' AND tg_user_id IS NOT NULL AND status IN ('new', 'registration')
    AND registration_done_at IS NULL AND follow_up_reason = 'finish_registration'
    AND contact_consent IS DISTINCT FROM FALSE AND auto_reminders < {max}
""".format(max=MAX_AUTO_REMINDERS)


def utcnow() -> datetime:
    return datetime.utcnow()


def to_local(ts: datetime | None) -> datetime | None:
    return ts + YEREVAN_OFFSET if ts else None


def from_local(ts: datetime) -> datetime:
    return ts - YEREVAN_OFFSET


class Leads:
    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    # ---------- чтение ----------

    async def get(self, lead_id: int) -> dict | None:
        row = await self.pool.fetchrow("SELECT * FROM leads WHERE lead_id = $1", lead_id)
        return dict(row) if row else None

    async def by_tg(self, tg_user_id: int) -> dict | None:
        row = await self.pool.fetchrow("SELECT * FROM leads WHERE tg_user_id = $1", tg_user_id)
        return dict(row) if row else None

    async def by_ids(self, lead_ids: list[int]) -> list[dict]:
        rows = await self.pool.fetch("SELECT * FROM leads WHERE lead_id = ANY($1::int[])", lead_ids)
        return [dict(r) for r in rows]

    async def recent_events(self, lead_id: int, limit: int = 5) -> list[dict]:
        rows = await self.pool.fetch(
            "SELECT * FROM lead_events WHERE lead_id = $1 ORDER BY event_id DESC LIMIT $2",
            lead_id, limit,
        )
        return [dict(r) for r in rows]

    async def funnel_counts(self) -> dict[str, int]:
        rows = await self.pool.fetch("SELECT status, count(*) AS n FROM leads GROUP BY status")
        return {r["status"]: r["n"] for r in rows}

    async def due_tasks(self, until: datetime, limit: int = 20) -> list[dict]:
        """Задачи менеджера: лиды, которым пора написать до момента until.
        Тех, кому бот напомнит сам, сюда не берём."""
        rows = await self.pool.fetch(
            f"""
            SELECT * FROM leads
            WHERE next_contact_at <= $1 AND status <> 'refused' AND NOT ({AUTO_REMINDER_SQL})
            ORDER BY next_contact_at
            LIMIT $2
            """,
            until, limit,
        )
        return [dict(r) for r in rows]

    async def count_due(self, until: datetime) -> int:
        return await self.pool.fetchval(
            f"""
            SELECT count(*) FROM leads
            WHERE next_contact_at <= $1 AND status <> 'refused' AND NOT ({AUTO_REMINDER_SQL})
            """,
            until,
        )

    # ---------- история ----------

    @staticmethod
    async def _event(conn, lead_id: int, event_type: str, *, via: str, actor: int = 0,
                     text: str | None = None, from_status: str | None = None,
                     to_status: str | None = None) -> None:
        await conn.execute(
            """
            INSERT INTO lead_events (lead_id, event_type, from_status, to_status, text, created_by, via)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            """,
            lead_id, event_type, from_status, to_status, text, actor, via,
        )

    async def note(self, lead_id: int, text: str, *, via: str, actor: int = 0,
                   event_type: str = "note") -> None:
        await self._event(self.pool, lead_id, event_type, via=via, actor=actor, text=text)

    async def _update(self, lead_id: int, fields: dict, *, via: str, actor: int = 0,
                      event: tuple[str, str | None] | None = None) -> dict | None:
        """Обновляет поля лида; смена статуса и переданное событие пишутся в историю."""
        async with self.pool.acquire() as conn, conn.transaction():
            old = await conn.fetchrow("SELECT * FROM leads WHERE lead_id = $1 FOR UPDATE", lead_id)
            if old is None:
                return None
            if fields:
                sets = ", ".join(f"{k} = ${i}" for i, k in enumerate(fields, start=2))
                row = await conn.fetchrow(
                    f"UPDATE leads SET {sets} WHERE lead_id = $1 RETURNING *",
                    lead_id, *fields.values(),
                )
            else:
                row = old
            if "status" in fields and fields["status"] != old["status"]:
                await self._event(conn, lead_id, "status", via=via, actor=actor,
                                  from_status=old["status"], to_status=fields["status"])
            if event:
                await self._event(conn, lead_id, event[0], via=via, actor=actor, text=event[1])
            return dict(row)

    # ---------- воронка в боте ----------

    async def ensure_bot_lead(self, tg_user_id: int, full_name: str, username: str | None,
                              lang: str, script_version: str) -> dict:
        """Мастер нажал «Я мастер»: создаём лида или обновляем имя и язык у существующего."""
        async with self.pool.acquire() as conn, conn.transaction():
            row = await conn.fetchrow(
                """
                INSERT INTO leads (tg_user_id, full_name, username, lang, source, script_version,
                                   next_contact_at, follow_up_reason)
                VALUES ($1, $2, $3, $4, 'bot', $5, now() + $6::interval, 'finish_registration')
                ON CONFLICT (tg_user_id) DO NOTHING
                RETURNING *
                """,
                tg_user_id, full_name, username, lang, script_version, FIRST_REMINDER_AFTER,
            )
            if row is not None:
                await self._event(conn, row["lead_id"], "created", via="lead", to_status="new",
                                  text="Пришёл в бота сам")
                return dict(row)
            row = await conn.fetchrow(
                """
                UPDATE leads SET full_name = $2, username = $3, lang = $4
                WHERE tg_user_id = $1 RETURNING *
                """,
                tg_user_id, full_name, username, lang,
            )
            return dict(row)

    async def start_registration(self, lead: dict) -> dict:
        fields = {"next_contact_at": utcnow() + FIRST_REMINDER_AFTER,
                  "follow_up_reason": "finish_registration"}
        if lead["status"] not in ("connected",):
            fields["status"] = "registration"
        # отказавшийся раньше начал заново — причина отказа больше не актуальна
        if lead["status"] == "refused":
            fields.update(refusal_reason=None, refusal_comment=None, registration_done_at=None)
        return await self._update(lead["lead_id"], fields, via="lead")

    async def save_registration(self, lead_id: int, *, full_name: str, phone: str,
                                categories: list[str], districts: list[str], consent: bool) -> dict:
        # анкета готова — теперь задача у менеджера: одобрить подключение
        return await self._update(
            lead_id,
            {"full_name": full_name, "phone": phone, "categories": categories,
             "districts": districts, "contact_consent": consent,
             "registration_done_at": utcnow(), "next_contact_at": utcnow(),
             "follow_up_reason": "finish_registration"},
            via="lead", event=("note", "Анкета заполнена, ждёт одобрения"),
        )

    async def request_info(self, lead_id: int) -> dict:
        return await self._update(
            lead_id, {"next_contact_at": utcnow(), "follow_up_reason": "send_info"},
            via="lead", event=("message_in", "Просит подробности о сервисе"),
        )

    async def decide_later(self, lead_id: int) -> dict:
        return await self._update(
            lead_id, {"next_contact_at": utcnow() + DECIDE_LATER_AFTER, "follow_up_reason": "decide_later"},
            via="lead", event=("message_in", "Подумает и вернётся позже"),
        )

    async def set_consent(self, tg_user_id: int, consent: bool) -> None:
        lead = await self.by_tg(tg_user_id)
        if lead and lead["contact_consent"] is not consent:
            await self._update(lead["lead_id"], {"contact_consent": consent}, via="lead",
                               event=("note", "Согласие на сообщения: " + ("да" if consent else "нет")))

    # ---------- действия менеджера (кнопки в боте и агент) ----------

    async def connect(self, lead_id: int, *, actor: int, via: str = "manager") -> dict | None:
        """Подключение: лид становится мастером и начинает получать заявки."""
        async with self.pool.acquire() as conn, conn.transaction():
            lead = await conn.fetchrow("SELECT * FROM leads WHERE lead_id = $1 FOR UPDATE", lead_id)
            if lead is None or lead["tg_user_id"] is None or lead["status"] == "connected":
                return None
            row = await conn.fetchrow(
                """
                UPDATE leads SET status = 'connected', connected_at = now(),
                                 next_contact_at = NULL, follow_up_reason = NULL
                WHERE lead_id = $1 RETURNING *
                """,
                lead_id,
            )
            await conn.execute(
                """
                INSERT INTO masters (master_id, lead_id, full_name, username) VALUES ($1, $2, $3, $4)
                ON CONFLICT (master_id) DO UPDATE SET
                    lead_id = EXCLUDED.lead_id, full_name = EXCLUDED.full_name,
                    username = EXCLUDED.username, is_active = TRUE
                """,
                lead["tg_user_id"], lead_id, lead["full_name"], lead["username"],
            )
            await self._event(conn, lead_id, "status", via=via, actor=actor,
                              from_status=lead["status"], to_status="connected")
            return dict(row)

    async def refuse(self, lead_id: int, reason: str, *, via: str, actor: int = 0,
                     comment: str | None = None) -> dict | None:
        lead = await self._update(
            lead_id,
            {"status": "refused", "refusal_reason": reason, "refusal_comment": comment,
             "next_contact_at": None, "follow_up_reason": None},
            via=via, actor=actor,
        )
        # отказавшийся мастер больше не получает заявки
        if lead and lead["tg_user_id"]:
            await self.pool.execute("UPDATE masters SET is_active = FALSE WHERE master_id = $1",
                                    lead["tg_user_id"])
        return lead

    async def contacted(self, lead_id: int, *, via: str, actor: int = 0,
                        text: str | None = None) -> dict | None:
        lead = await self.get(lead_id)
        if lead is None:
            return None
        fields = {"last_contact_at": utcnow(), "next_contact_at": None, "follow_up_reason": None}
        if lead["status"] == "new":
            fields["status"] = "contacted"
        return await self._update(lead_id, fields, via=via, actor=actor,
                                  event=("contact", text or "Менеджер связался"))

    async def set_status(self, lead_id: int, status: str, *, via: str, actor: int = 0) -> dict | None:
        return await self._update(lead_id, {"status": status}, via=via, actor=actor)

    async def schedule(self, lead_id: int, at: datetime, reason: str | None, *, via: str,
                       actor: int = 0) -> dict | None:
        lead = await self.get(lead_id)
        if lead is None:
            return None
        reason = reason or lead["follow_up_reason"] or "call"
        return await self._update(lead_id, {"next_contact_at": at, "follow_up_reason": reason},
                                  via=via, actor=actor,
                                  event=("follow_up", f"{reason} на {to_local(at):%d.%m %H:%M}"))

    async def clear_next(self, lead_id: int, *, via: str, actor: int = 0) -> dict | None:
        return await self._update(lead_id, {"next_contact_at": None, "follow_up_reason": None},
                                  via=via, actor=actor, event=("follow_up", "Следующий контакт не нужен"))

    async def mark_paid(self, lead_id: int, *, via: str, actor: int = 0) -> dict | None:
        lead = await self.get(lead_id)
        if lead is None or lead["first_payment_at"]:
            return lead
        return await self._update(lead_id, {"first_payment_at": utcnow()}, via=via, actor=actor,
                                  event=("payment", "Первая оплата"))

    async def add_manual(self, *, full_name: str, phone: str | None, username: str | None,
                         categories: list[str], districts: list[str], source: str,
                         script_version: str, actor: int, via: str,
                         next_contact_at: datetime | None, follow_up_reason: str | None,
                         note: str | None) -> dict:
        async with self.pool.acquire() as conn, conn.transaction():
            row = await conn.fetchrow(
                """
                INSERT INTO leads (full_name, phone, username, categories, districts, source,
                                   script_version, next_contact_at, follow_up_reason)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                RETURNING *
                """,
                full_name, phone, username, categories, districts, source, script_version,
                next_contact_at, follow_up_reason if next_contact_at else None,
            )
            await self._event(conn, row["lead_id"], "created", via=via, actor=actor,
                              to_status="new", text=note or "Добавлен менеджером")
            return dict(row)

    # ---------- автонапоминания бота ----------

    async def claim_auto_reminders(self, limit: int = 50) -> list[dict]:
        """Забирает лидов, которым пора напомнить, и сразу сдвигает следующий контакт.
        После последнего напоминания задача переходит менеджеру (no_response)."""
        rows = await self.pool.fetch(
            f"""
            UPDATE leads SET
                auto_reminders = auto_reminders + 1,
                last_contact_at = now(),
                next_contact_at = now() + $2::interval,
                follow_up_reason = CASE WHEN auto_reminders + 1 >= $1
                                        THEN 'no_response' ELSE 'finish_registration' END
            WHERE lead_id IN (
                SELECT lead_id FROM leads
                WHERE {AUTO_REMINDER_SQL} AND next_contact_at <= now()
                ORDER BY next_contact_at
                LIMIT $3
                FOR UPDATE SKIP LOCKED
            )
            RETURNING *
            """,
            MAX_AUTO_REMINDERS, AUTO_REMINDER_INTERVAL, limit,
        )
        return [dict(r) for r in rows]

    async def log_outgoing(self, lead_id: int, text: str, *, via: str, actor: int = 0,
                           delivered: bool = True) -> None:
        event_text = text if delivered else f"Не доставлено: {text}"
        await self._event(self.pool, lead_id, "message_out", via=via, actor=actor, text=event_text)
        if delivered:
            await self.pool.execute("UPDATE leads SET last_contact_at = now() WHERE lead_id = $1", lead_id)
