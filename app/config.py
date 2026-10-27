import os
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from dotenv import load_dotenv


@dataclass(frozen=True)
class Config:
    bot_token: str
    manager_chat_ids: list[int]
    database_url: str
    # агент читает данные под ролью только для чтения
    agent_database_url: str
    agent_dwh_url: str
    agent_model: str
    agent_effort: str
    default_city: str
    visit_fee: Decimal
    currency: str

    @property
    def agent_enabled(self) -> bool:
        return bool(os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_AUTH_TOKEN"))


def _ids(raw: str) -> list[int]:
    try:
        return [int(x) for x in raw.replace(";", ",").split(",") if x.strip()]
    except ValueError:
        raise SystemExit("MANAGER_CHAT_IDS должен содержать числа через запятую.")


def load_config(require_token: bool = True) -> Config:
    load_dotenv()

    token = os.getenv("BOT_TOKEN", "").strip()
    if require_token and not token:
        raise SystemExit("BOT_TOKEN не задан. Скопируйте .env.example в .env и заполните его.")

    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        raise SystemExit("DATABASE_URL не задан: нужна строка подключения к базе бота (PostgreSQL).")

    try:
        visit_fee = Decimal(os.getenv("VISIT_FEE", "0") or "0")
    except InvalidOperation:
        raise SystemExit("VISIT_FEE должен быть числом.")

    effort = os.getenv("AGENT_EFFORT", "medium").strip()
    if effort not in ("low", "medium", "high", "xhigh", "max"):
        raise SystemExit("AGENT_EFFORT: low, medium, high, xhigh или max.")

    return Config(
        bot_token=token,
        # OWNER_CHAT_IDS — имя из первой версии бота, поддерживаем для совместимости
        manager_chat_ids=_ids(os.getenv("MANAGER_CHAT_IDS") or os.getenv("OWNER_CHAT_IDS", "")),
        database_url=database_url,
        agent_database_url=os.getenv("AGENT_DATABASE_URL", "").strip() or database_url,
        agent_dwh_url=os.getenv("AGENT_DWH_URL", "").strip(),
        agent_model=os.getenv("AGENT_MODEL", "claude-opus-5-5").strip(),
        agent_effort=effort,
        default_city=os.getenv("DEFAULT_CITY", "Yerevan").strip(),
        visit_fee=visit_fee,
        currency=os.getenv("CURRENCY", "AMD").strip(),
    )
