"""Доступ к операционной базе бота (PostgreSQL). Схема — sql/init/10_operational.sql."""

from decimal import Decimal

import asyncpg

# Полная карточка заявки: всё, что нужно для сообщений мастерам, менеджерам и заказчику
ORDER_CARD_SQL = """
    SELECT o.*, c.code AS category_code,
           cu.contact_name, cu.username AS customer_username, cu.lang AS customer_lang,
           m.full_name AS master_name, m.username AS master_username
    FROM orders o
    JOIN categories c USING (category_id)
    JOIN customers cu USING (customer_id)
    LEFT JOIN masters m USING (master_id)
"""


class Database:
    def __init__(self, dsn: str):
        self.dsn = dsn
        self.pool: asyncpg.Pool | None = None

    async def connect(self) -> None:
        self.pool = await asyncpg.create_pool(self.dsn, min_size=1, max_size=5)

    async def close(self) -> None:
        if self.pool:
            await self.pool.close()

    # ---------- заказчики ----------

    async def get_lang(self, user_id: int) -> str | None:
        return await self.pool.fetchval("SELECT lang FROM customers WHERE customer_id = $1", user_id)

    async def save_customer(self, user_id: int, full_name: str, username: str | None,
                            lang: str | None = None) -> None:
        """Создаёт заказчика при первом обращении и обновляет имя, username и язык."""
        await self.pool.execute(
            """
            INSERT INTO customers (customer_id, contact_name, username, lang)
            VALUES ($1, $2, $3, COALESCE($4, 'en'))
            ON CONFLICT (customer_id) DO UPDATE SET
                contact_name = EXCLUDED.contact_name,
                username = EXCLUDED.username,
                lang = COALESCE($4, customers.lang),
                is_blocked = FALSE
            """,
            user_id, full_name, username, lang,
        )

    async def mark_blocked(self, customer_id: int) -> None:
        await self.pool.execute(
            "UPDATE customers SET is_blocked = TRUE WHERE customer_id = $1 AND NOT is_blocked",
            customer_id,
        )

    # ---------- заявки ----------

    async def add_order(self, data: dict) -> int:
        async with self.pool.acquire() as conn, conn.transaction():
            await conn.execute(
                """
                UPDATE customers SET district = $2, phone = COALESCE($3, phone), city = $4
                WHERE customer_id = $1
                """,
                data["customer_id"], data["district"], data["phone"], data["city"],
            )
            return await conn.fetchval(
                """
                INSERT INTO orders (customer_id, category_id, description, photo_file_id, city,
                                    district, address, contact_method, phone)
                VALUES ($1, (SELECT category_id FROM categories WHERE code = $2), $3, $4, $5,
                        $6, $7, $8, $9)
                RETURNING order_id
                """,
                data["customer_id"], data["category"], data["description"],
                data["photo_file_id"], data["city"], data["district"], data["address"],
                data["contact_method"], data["phone"],
            )

    async def get_order(self, order_id: int) -> dict | None:
        row = await self.pool.fetchrow(ORDER_CARD_SQL + " WHERE o.order_id = $1", order_id)
        return dict(row) if row else None

    async def customer_orders(self, customer_id: int, limit: int = 10) -> list[dict]:
        rows = await self.pool.fetch(
            ORDER_CARD_SQL + " WHERE o.customer_id = $1 ORDER BY o.order_id DESC LIMIT $2",
            customer_id, limit,
        )
        return [dict(r) for r in rows]

    async def cancel_order(self, order_id: int, customer_id: int) -> bool:
        """Заказчик может отменить заявку, пока её не взял мастер."""
        result = await self.pool.execute(
            """
            UPDATE orders SET status = 'cancelled', cancelled_at = now()
            WHERE order_id = $1 AND customer_id = $2 AND status = 'new'
            """,
            order_id, customer_id,
        )
        return result.endswith(" 1")

    async def open_orders(self, limit: int = 20) -> list[dict]:
        rows = await self.pool.fetch(
            ORDER_CARD_SQL + " WHERE o.status = 'new' ORDER BY o.order_id LIMIT $1", limit
        )
        return [dict(r) for r in rows]

    async def master_orders(self, master_id: int) -> list[dict]:
        rows = await self.pool.fetch(
            ORDER_CARD_SQL + " WHERE o.master_id = $1 AND o.status = 'assigned' ORDER BY o.order_id",
            master_id,
        )
        return [dict(r) for r in rows]

    async def take_order(self, order_id: int, master_id: int) -> bool:
        # условие на статус делает взятие атомарным: два мастера не возьмут одну заявку
        result = await self.pool.execute(
            """
            UPDATE orders SET master_id = $2, status = 'assigned', assigned_at = now()
            WHERE order_id = $1 AND status = 'new'
            """,
            order_id, master_id,
        )
        return result.endswith(" 1")

    async def release_order(self, order_id: int, master_id: int) -> bool:
        result = await self.pool.execute(
            """
            UPDATE orders SET master_id = NULL, status = 'new', assigned_at = NULL
            WHERE order_id = $1 AND master_id = $2 AND status = 'assigned'
            """,
            order_id, master_id,
        )
        return result.endswith(" 1")

    async def complete_order(self, order_id: int, master_id: int, product_id: int,
                             price: Decimal, freight: Decimal) -> bool:
        async with self.pool.acquire() as conn, conn.transaction():
            result = await conn.execute(
                """
                UPDATE orders SET status = 'done', completed_at = now(), freight = $3
                WHERE order_id = $1 AND master_id = $2 AND status = 'assigned'
                """,
                order_id, master_id, freight,
            )
            if not result.endswith(" 1"):
                return False
            await conn.execute(
                """
                INSERT INTO order_details (order_id, product_id, unit_price, quantity)
                VALUES ($1, $2, $3, 1)
                ON CONFLICT (order_id, product_id) DO UPDATE SET unit_price = EXCLUDED.unit_price
                """,
                order_id, product_id, price,
            )
            return True

    async def services(self, category_code: str) -> list[dict]:
        rows = await self.pool.fetch(
            """
            SELECT p.product_id, p.product_name FROM products p
            JOIN categories c USING (category_id)
            WHERE c.code = $1 AND NOT p.discontinued
            ORDER BY p.product_id
            """,
            category_code,
        )
        return [dict(r) for r in rows]

    # ---------- мастера ----------

    async def get_master(self, user_id: int) -> dict | None:
        row = await self.pool.fetchrow("SELECT * FROM masters WHERE master_id = $1", user_id)
        return dict(row) if row else None

    async def request_master(self, user_id: int, full_name: str, username: str | None) -> None:
        """Заявка в мастера: запись появляется неактивной, активирует её менеджер."""
        await self.pool.execute(
            """
            INSERT INTO masters (master_id, full_name, username, is_active) VALUES ($1, $2, $3, FALSE)
            ON CONFLICT (master_id) DO UPDATE SET
                full_name = EXCLUDED.full_name, username = EXCLUDED.username
            """,
            user_id, full_name, username,
        )

    async def set_master_active(self, user_id: int, active: bool) -> dict | None:
        row = await self.pool.fetchrow(
            "UPDATE masters SET is_active = $2 WHERE master_id = $1 RETURNING *", user_id, active
        )
        return dict(row) if row else None

    async def active_master_ids(self) -> list[int]:
        rows = await self.pool.fetch("SELECT master_id FROM masters WHERE is_active")
        return [r["master_id"] for r in rows]

    # ---------- сообщения заказчикам и рассылки агента ----------

    async def log_message(self, customer_id: int, text: str, status: str, source: str,
                          order_id: int | None = None, broadcast_id: int | None = None,
                          error: str | None = None) -> None:
        await self.pool.execute(
            """
            INSERT INTO message_log (broadcast_id, customer_id, order_id, source, text, status, error)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            """,
            broadcast_id, customer_id, order_id, source, text, status, error,
        )

    async def create_broadcast(self, created_by: int, text: str, customer_ids: list[int],
                               order_id: int | None) -> int:
        return await self.pool.fetchval(
            """
            INSERT INTO broadcasts (created_by, text, customer_ids, order_id)
            VALUES ($1, $2, $3, $4) RETURNING broadcast_id
            """,
            created_by, text, customer_ids, order_id,
        )

    async def get_broadcast(self, broadcast_id: int) -> dict | None:
        row = await self.pool.fetchrow("SELECT * FROM broadcasts WHERE broadcast_id = $1", broadcast_id)
        return dict(row) if row else None

    async def decide_broadcast(self, broadcast_id: int, status: str) -> dict | None:
        """Переводит рассылку из pending в sent/cancelled. Возвращает её, если перевод удался —
        так повторное нажатие кнопки не отправит сообщения второй раз."""
        row = await self.pool.fetchrow(
            """
            UPDATE broadcasts SET status = $2, decided_at = now()
            WHERE broadcast_id = $1 AND status = 'pending'
            RETURNING *
            """,
            broadcast_id, status,
        )
        return dict(row) if row else None

    async def customers_by_ids(self, customer_ids: list[int]) -> list[dict]:
        rows = await self.pool.fetch(
            "SELECT customer_id, contact_name, lang, is_blocked FROM customers "
            "WHERE customer_id = ANY($1::bigint[])",
            customer_ids,
        )
        return [dict(r) for r in rows]
