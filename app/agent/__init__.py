import logging

import asyncpg

from ..config import Config
from ..db import Database
from .agent import ManagerAgent, Reply
from .tools import AgentTools

log = logging.getLogger(__name__)

__all__ = ["ManagerAgent", "Reply", "create_agent"]


async def create_agent(config: Config, db: Database) -> ManagerAgent | None:
    """None — если нет ключа Claude API: бот тогда работает без агента."""
    if not config.agent_enabled:
        log.warning("ANTHROPIC_API_KEY не задан: агент выключен, бот работает без него")
        return None
    operational = await asyncpg.create_pool(config.agent_database_url, min_size=1, max_size=3)
    dwh = None
    if config.agent_dwh_url:
        try:
            dwh = await asyncpg.create_pool(config.agent_dwh_url, min_size=1, max_size=3)
        except (OSError, asyncpg.PostgresError):
            log.warning("Нет подключения к DWH: агент будет работать только с базой бота", exc_info=True)
    tools = AgentTools(db, operational, dwh)
    return ManagerAgent(tools, model=config.agent_model, effort=config.agent_effort)
