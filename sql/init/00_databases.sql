-- Выполняется один раз при первом старте контейнера postgres-data
-- (docker-entrypoint-initdb.d). База handyman создаётся из POSTGRES_DB.

CREATE DATABASE mrr;
CREATE DATABASE stg;
CREATE DATABASE dwh;

-- Роль только для чтения: под ней агент выполняет свои SQL-запросы.
-- Пароль для локального запуска; в проде замените.
CREATE ROLE agent_ro LOGIN PASSWORD 'agent_ro';
