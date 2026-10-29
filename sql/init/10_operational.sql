-- Операционная база Telegram-бота: сюда бот пишет лиды, заявки и сообщения, отсюда их забирает ETL.
-- Скрипт идемпотентный: при первом старте контейнера он создаёт схему, а на уже работающей
-- базе его можно запустить ещё раз как миграцию (см. README, «Обновление схемы»).
\connect handyman

CREATE OR REPLACE FUNCTION set_updated_at() RETURNS trigger AS $$
BEGIN
    NEW.updated_at := now();
    RETURN NEW;
END
$$ LANGUAGE plpgsql;

------------------------------------------------------------------ CRM: мастера
-- Мастера — основные клиенты сервиса. Лид — потенциальный мастер: пришёл в бота сам
-- или добавлен менеджером. Вся воронка — статус лида и история в lead_events.
CREATE TABLE IF NOT EXISTS leads (
    lead_id              SERIAL PRIMARY KEY,
    tg_user_id           BIGINT UNIQUE,                 -- нет у лидов, добавленных вручную
    full_name            TEXT NOT NULL,
    username             TEXT,
    phone                TEXT,
    lang                 TEXT NOT NULL DEFAULT 'ru' CHECK (lang IN ('ru', 'en', 'hy')),
    source               TEXT NOT NULL DEFAULT 'bot' CHECK (source IN ('bot', 'manual', 'referral')),
    categories           TEXT[] NOT NULL DEFAULT '{}',  -- специализации: коды из categories.code
    districts            TEXT[] NOT NULL DEFAULT '{}',  -- районы Еревана, где готов работать
    status               TEXT NOT NULL DEFAULT 'new'
                         CHECK (status IN ('new', 'contacted', 'negotiation', 'registration',
                                           'connected', 'refused')),
    refusal_reason       TEXT CHECK (refusal_reason IN ('conditions', 'price', 'few_orders',
                                                        'complex_registration', 'unclear_value',
                                                        'missing_feature', 'other')),
    refusal_comment      TEXT,
    -- согласие на напоминания и новости: NULL — не спрашивали, FALSE — попросил не писать (/stop)
    contact_consent      BOOLEAN,
    -- версия сценария общения: конверсию сравниваем между сопоставимыми когортами одной версии
    script_version       TEXT NOT NULL DEFAULT 'v1',
    last_contact_at      TIMESTAMP,
    next_contact_at      TIMESTAMP,                     -- когда нужен следующий контакт
    follow_up_reason     TEXT CHECK (follow_up_reason IN ('first_contact', 'send_info', 'call',
                                                          'decide_later', 'no_response',
                                                          'finish_registration', 'check_activity')),
    auto_reminders       SMALLINT NOT NULL DEFAULT 0,  -- сколько напоминаний бот отправил сам
    registration_done_at TIMESTAMP,                     -- анкета заполнена, ждёт одобрения
    connected_at         TIMESTAMP,
    first_payment_at     TIMESTAMP,
    created_at           TIMESTAMP NOT NULL DEFAULT now(),
    updated_at           TIMESTAMP NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS leads_next_contact_idx ON leads (next_contact_at)
    WHERE next_contact_at IS NOT NULL;
CREATE INDEX IF NOT EXISTS leads_status_idx ON leads (status);

-- История взаимодействий с лидом: смены статусов, контакты, сообщения, задачи, заметки
CREATE TABLE IF NOT EXISTS lead_events (
    event_id    SERIAL PRIMARY KEY,
    lead_id     INTEGER NOT NULL REFERENCES leads,
    event_type  TEXT NOT NULL CHECK (event_type IN ('created', 'status', 'contact', 'message_in',
                                                    'message_out', 'follow_up', 'note', 'payment')),
    from_status TEXT,
    to_status   TEXT,
    text        TEXT,
    created_by  BIGINT NOT NULL DEFAULT 0,           -- chat id менеджера; 0 — система
    via         TEXT NOT NULL CHECK (via IN ('lead', 'manager', 'agent', 'airflow', 'system')),
    created_at  TIMESTAMP NOT NULL DEFAULT now(),
    updated_at  TIMESTAMP NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS lead_events_lead_idx ON lead_events (lead_id);

------------------------------------------------------------------ заявки заказчиков
CREATE TABLE IF NOT EXISTS categories (
    category_id   SMALLINT PRIMARY KEY,
    code          TEXT NOT NULL UNIQUE,          -- ключ для текстов бота: cat_<code>
    category_name TEXT NOT NULL,
    updated_at    TIMESTAMP NOT NULL DEFAULT now()
);

-- Каталог услуг. Цена базовая и необязательная: итоговую сумму указывает мастер.
CREATE TABLE IF NOT EXISTS products (
    product_id   SMALLINT PRIMARY KEY,
    product_name TEXT NOT NULL,
    category_id  SMALLINT NOT NULL REFERENCES categories,
    unit_price   NUMERIC(12, 2),
    discontinued BOOLEAN NOT NULL DEFAULT FALSE,
    updated_at   TIMESTAMP NOT NULL DEFAULT now()
);

-- Заказчик = пользователь Telegram. customer_id совпадает с chat id личного чата с ботом.
CREATE TABLE IF NOT EXISTS customers (
    customer_id     BIGINT PRIMARY KEY,
    contact_name    TEXT NOT NULL,
    username        TEXT,
    phone           TEXT,
    lang            TEXT NOT NULL DEFAULT 'en' CHECK (lang IN ('ru', 'en', 'hy')),
    city            TEXT NOT NULL DEFAULT 'Yerevan',
    district        TEXT,                           -- район из последней заявки
    is_blocked      BOOLEAN NOT NULL DEFAULT FALSE, -- заблокировал бота: рассылки его пропускают
    contact_consent BOOLEAN,                        -- FALSE — попросил не присылать рассылки
    created_at      TIMESTAMP NOT NULL DEFAULT now(),
    updated_at      TIMESTAMP NOT NULL DEFAULT now()
);
ALTER TABLE customers ADD COLUMN IF NOT EXISTS contact_consent BOOLEAN;

-- Подключённый мастер — лид в статусе connected; получает заявки в боте.
CREATE TABLE IF NOT EXISTS masters (
    master_id  BIGINT PRIMARY KEY,               -- Telegram user id
    lead_id    INTEGER REFERENCES leads,
    full_name  TEXT NOT NULL,
    username   TEXT,
    is_active  BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT now(),
    updated_at TIMESTAMP NOT NULL DEFAULT now()
);
ALTER TABLE masters ADD COLUMN IF NOT EXISTS lead_id INTEGER REFERENCES leads;

CREATE TABLE IF NOT EXISTS orders (
    order_id       SERIAL PRIMARY KEY,
    customer_id    BIGINT NOT NULL REFERENCES customers,
    master_id      BIGINT REFERENCES masters,
    category_id    SMALLINT NOT NULL REFERENCES categories,
    description    TEXT NOT NULL,
    photo_file_id  TEXT,
    city           TEXT NOT NULL,
    district       TEXT,
    address        TEXT NOT NULL,
    contact_method TEXT NOT NULL CHECK (contact_method IN ('telegram', 'whatsapp', 'phone')),
    phone          TEXT,
    status         TEXT NOT NULL DEFAULT 'new'
                   CHECK (status IN ('new', 'assigned', 'done', 'cancelled')),
    order_date     TIMESTAMP NOT NULL DEFAULT now(),
    assigned_at    TIMESTAMP,
    completed_at   TIMESTAMP,
    cancelled_at   TIMESTAMP,
    freight        NUMERIC(12, 2) NOT NULL DEFAULT 0,  -- стоимость выезда
    updated_at     TIMESTAMP NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS orders_status_idx ON orders (status);
CREATE INDEX IF NOT EXISTS orders_customer_idx ON orders (customer_id);

-- Что сделано по заявке; заполняет мастер при закрытии.
CREATE TABLE IF NOT EXISTS order_details (
    order_id   INTEGER NOT NULL REFERENCES orders,
    product_id SMALLINT NOT NULL REFERENCES products,
    unit_price NUMERIC(12, 2) NOT NULL,
    quantity   SMALLINT NOT NULL DEFAULT 1 CHECK (quantity > 0),
    discount   NUMERIC(4, 3) NOT NULL DEFAULT 0 CHECK (discount >= 0 AND discount < 1),
    updated_at TIMESTAMP NOT NULL DEFAULT now(),
    PRIMARY KEY (order_id, product_id)
);

------------------------------------------------------------------ рассылки
-- Рассылка, подготовленная агентом, — заказчикам или мастерам (лидам).
-- Уходит только после подтверждения менеджером.
CREATE TABLE IF NOT EXISTS broadcasts (
    broadcast_id  SERIAL PRIMARY KEY,
    created_by    BIGINT NOT NULL,              -- chat id менеджера
    audience      TEXT NOT NULL DEFAULT 'customers' CHECK (audience IN ('customers', 'leads')),
    text          TEXT NOT NULL,
    recipient_ids BIGINT[] NOT NULL,            -- customer_id или lead_id, по audience
    order_id      INTEGER REFERENCES orders,
    status        TEXT NOT NULL DEFAULT 'pending'
                  CHECK (status IN ('pending', 'sent', 'cancelled')),
    created_at    TIMESTAMP NOT NULL DEFAULT now(),
    decided_at    TIMESTAMP,
    updated_at    TIMESTAMP NOT NULL DEFAULT now()
);
-- миграция с первой версии, где рассылки были только заказчикам
ALTER TABLE broadcasts ADD COLUMN IF NOT EXISTS audience TEXT NOT NULL DEFAULT 'customers'
    CHECK (audience IN ('customers', 'leads'));
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_name = 'broadcasts' AND column_name = 'customer_ids') THEN
        ALTER TABLE broadcasts RENAME COLUMN customer_ids TO recipient_ids;
    END IF;
END
$$;

-- Сообщения заказчикам: из рассылок агента и уведомления о заявке.
-- Сообщения мастерам-лидам пишутся в lead_events (message_out) — это история CRM.
CREATE TABLE IF NOT EXISTS message_log (
    message_id   SERIAL PRIMARY KEY,
    broadcast_id INTEGER REFERENCES broadcasts,
    customer_id  BIGINT NOT NULL REFERENCES customers,
    order_id     INTEGER REFERENCES orders,
    source       TEXT NOT NULL CHECK (source IN ('agent', 'system')),
    text         TEXT NOT NULL,
    status       TEXT NOT NULL CHECK (status IN ('sent', 'failed')),
    error        TEXT,
    created_at   TIMESTAMP NOT NULL DEFAULT now(),
    updated_at   TIMESTAMP NOT NULL DEFAULT now()
);

DO $$
DECLARE
    t TEXT;
BEGIN
    FOREACH t IN ARRAY ARRAY['leads', 'lead_events', 'categories', 'products', 'customers',
                             'masters', 'orders', 'order_details', 'broadcasts', 'message_log']
    LOOP
        EXECUTE format('DROP TRIGGER IF EXISTS %1$s_updated_at ON %1$s', t);
        EXECUTE format('CREATE TRIGGER %1$s_updated_at BEFORE UPDATE ON %1$s '
                       'FOR EACH ROW EXECUTE FUNCTION set_updated_at()', t);
    END LOOP;
END
$$;

-- Мастера из первой версии (без CRM) становятся лидами
INSERT INTO leads (tg_user_id, full_name, username, status, connected_at, created_at)
SELECT m.master_id, m.full_name, m.username,
       CASE WHEN m.is_active THEN 'connected' ELSE 'registration' END,
       CASE WHEN m.is_active THEN m.created_at END,
       m.created_at
FROM masters m
WHERE m.lead_id IS NULL
ON CONFLICT (tg_user_id) DO NOTHING;
UPDATE masters m SET lead_id = l.lead_id
FROM leads l
WHERE l.tg_user_id = m.master_id AND m.lead_id IS NULL;

-- Категории совпадают с кнопками бота (app/texts.py, CATEGORIES)
INSERT INTO categories (category_id, code, category_name) VALUES
    (1, 'plumbing',     'Сантехника'),
    (2, 'electrical',   'Электрика'),
    (3, 'installation', 'Установка и монтаж'),
    (4, 'furniture',    'Сборка мебели'),
    (5, 'repair',       'Мелкий ремонт'),
    (6, 'appliances',   'Бытовая техника'),
    (7, 'other',        'Другое')
ON CONFLICT (category_id) DO NOTHING;

INSERT INTO products (product_id, product_name, category_id) VALUES
    (101, 'Устранение протечки',            1),
    (102, 'Замена смесителя',               1),
    (103, 'Установка сантехники',           1),
    (104, 'Прочие сантехнические работы',   1),
    (201, 'Замена розетки или выключателя', 2),
    (202, 'Установка светильника',          2),
    (203, 'Поиск и устранение неисправности', 2),
    (204, 'Прочие электромонтажные работы', 2),
    (301, 'Навес полок, карнизов, ТВ',      3),
    (302, 'Установка дверей и замков',      3),
    (303, 'Прочий монтаж',                  3),
    (401, 'Сборка корпусной мебели',        4),
    (402, 'Сборка кухни',                   4),
    (403, 'Ремонт мебели',                  4),
    (501, 'Мелкий ремонт',                  5),
    (601, 'Подключение техники',            6),
    (602, 'Ремонт бытовой техники',         6),
    (701, 'Другие работы',                  7)
ON CONFLICT (product_id) DO NOTHING;

GRANT CONNECT ON DATABASE handyman TO agent_ro;
GRANT USAGE ON SCHEMA public TO agent_ro;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO agent_ro;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO agent_ro;
