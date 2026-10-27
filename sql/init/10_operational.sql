-- Операционная база Telegram-бота: сюда бот пишет заявки, отсюда их забирает ETL.
\connect handyman

CREATE OR REPLACE FUNCTION set_updated_at() RETURNS trigger AS $$
BEGIN
    NEW.updated_at := now();
    RETURN NEW;
END
$$ LANGUAGE plpgsql;

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
    customer_id  BIGINT PRIMARY KEY,
    contact_name TEXT NOT NULL,
    username     TEXT,
    phone        TEXT,
    lang         TEXT NOT NULL DEFAULT 'en' CHECK (lang IN ('ru', 'en', 'hy')),
    city         TEXT NOT NULL DEFAULT 'Yerevan',
    district     TEXT,                           -- район из последней заявки
    is_blocked   BOOLEAN NOT NULL DEFAULT FALSE, -- заблокировал бота: рассылки его пропускают
    created_at   TIMESTAMP NOT NULL DEFAULT now(),
    updated_at   TIMESTAMP NOT NULL DEFAULT now()
);

-- Мастер тоже пользователь Telegram; попадает сюда после одобрения менеджером.
CREATE TABLE IF NOT EXISTS masters (
    master_id  BIGINT PRIMARY KEY,
    full_name  TEXT NOT NULL,
    username   TEXT,
    is_active  BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT now(),
    updated_at TIMESTAMP NOT NULL DEFAULT now()
);

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

-- Рассылка, подготовленная агентом. Уходит только после подтверждения менеджером.
CREATE TABLE IF NOT EXISTS broadcasts (
    broadcast_id SERIAL PRIMARY KEY,
    created_by   BIGINT NOT NULL,               -- chat id менеджера
    text         TEXT NOT NULL,
    customer_ids BIGINT[] NOT NULL,
    order_id     INTEGER REFERENCES orders,
    status       TEXT NOT NULL DEFAULT 'pending'
                 CHECK (status IN ('pending', 'sent', 'cancelled')),
    created_at   TIMESTAMP NOT NULL DEFAULT now(),
    decided_at   TIMESTAMP,
    updated_at   TIMESTAMP NOT NULL DEFAULT now()
);

-- Каждое сообщение заказчику: из рассылок агента и системные уведомления о заявке.
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
    FOREACH t IN ARRAY ARRAY['categories', 'products', 'customers', 'masters', 'orders',
                             'order_details', 'broadcasts', 'message_log']
    LOOP
        EXECUTE format('DROP TRIGGER IF EXISTS %1$s_updated_at ON %1$s', t);
        EXECUTE format('CREATE TRIGGER %1$s_updated_at BEFORE UPDATE ON %1$s '
                       'FOR EACH ROW EXECUTE FUNCTION set_updated_at()', t);
    END LOOP;
END
$$;

-- Категории совпадают с кнопками бота (bot/texts.py, CATEGORIES)
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
