"""Агент менеджера на Claude API: цикл tool use с инструментами из tools.py.
Один диалог на чат менеджера; история только дописывается, а не редактируется."""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone

import anthropic

from .prompt import SYSTEM_PROMPT
from .tools import AgentTools, ToolError, TurnContext

log = logging.getLogger(__name__)

MAX_STEPS = 15              # вызовов модели на один вопрос менеджера
MAX_HISTORY = 80            # сообщений в диалоге, после этого начинаем новый
SESSION_IDLE_SECONDS = 2 * 60 * 60
MAX_TOKENS = 16_000

# Модели, у которых есть серверный fallback при отказе классификаторов
FALLBACK_MODELS = {"claude-opus-5-5", "claude-opus-5", "claude-fable-5-1", "claude-sonnet-5-5"}
FALLBACK_BETA = "server-side-fallback-2026-07-01"


@dataclass
class Reply:
    text: str
    broadcast_ids: list[int] = field(default_factory=list)


@dataclass
class Session:
    messages: list = field(default_factory=list)
    notes: list[str] = field(default_factory=list)  # события между репликами (итоги рассылок)
    last_used: float = field(default_factory=time.monotonic)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


class ManagerAgent:
    def __init__(self, tools: AgentTools, model: str, effort: str,
                 client: anthropic.AsyncAnthropic | None = None):
        self.tools = tools
        self.model = model
        self.effort = effort
        self.client = client or anthropic.AsyncAnthropic()
        self.sessions: dict[int, Session] = {}

    def reset(self, chat_id: int) -> None:
        self.sessions.pop(chat_id, None)

    def add_note(self, chat_id: int, note: str) -> None:
        """Модель узнает об этом из начала следующего сообщения менеджера."""
        session = self.sessions.get(chat_id)
        if session is not None:
            session.notes.append(note)

    def _session(self, chat_id: int) -> tuple[Session, bool]:
        session = self.sessions.get(chat_id)
        expired = session is not None and (
            time.monotonic() - session.last_used > SESSION_IDLE_SECONDS
            or len(session.messages) > MAX_HISTORY
        )
        if session is None or expired:
            notes = session.notes if session else []
            session = self.sessions[chat_id] = Session(notes=notes)
        return session, expired

    async def ask(self, chat_id: int, text: str) -> Reply:
        session, restarted = self._session(chat_id)
        async with session.lock:
            session.last_used = time.monotonic()
            reply = await self._turn(session, chat_id, text)
            if restarted:
                reply.text = "(Начал новый диалог: прошлый был слишком давно или слишком длинный.)\n\n" + reply.text
            return reply

    async def _turn(self, session: Session, chat_id: int, text: str) -> Reply:
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        header = [f"[Сейчас {now}]"] + [f"[Система: {n}]" for n in session.notes]
        session.notes.clear()
        session.messages.append({"role": "user", "content": "\n".join(header) + "\n\n" + text})

        ctx = TurnContext(chat_id=chat_id)
        for _ in range(MAX_STEPS):
            try:
                response = await self._create(session.messages)
            except anthropic.RateLimitError:
                return Reply("Claude сейчас перегружен запросами, попробуйте через минуту.", ctx.broadcast_ids)
            except anthropic.APIStatusError as e:
                log.exception("Ошибка Claude API")
                return Reply(f"Ошибка Claude API ({e.status_code}): {e.message}", ctx.broadcast_ids)
            except anthropic.APIConnectionError:
                log.exception("Нет связи с Claude API")
                return Reply("Не удалось связаться с Claude API. Проверьте интернет и ключ.", ctx.broadcast_ids)

            # ответ целиком, вместе с thinking-блоками: история должна только дописываться
            session.messages.append({"role": "assistant", "content": response.content})
            answer = "\n\n".join(b.text for b in response.content if b.type == "text").strip()

            if response.stop_reason == "tool_use":
                session.messages.append({"role": "user", "content": await self._run_tools(response, ctx)})
                continue
            if response.stop_reason == "pause_turn":
                continue
            if response.stop_reason == "refusal":
                return Reply("Модель отказалась выполнять этот запрос. Переформулируйте, пожалуйста.",
                             ctx.broadcast_ids)
            if response.stop_reason == "max_tokens":
                answer += "\n\n(Ответ обрезан по длине.)"
            return Reply(answer or "Готово.", ctx.broadcast_ids)

        return Reply("Не уложился в отведённое число шагов. Попробуйте задать вопрос конкретнее.",
                     ctx.broadcast_ids)

    async def _create(self, messages: list):
        params = dict(
            model=self.model,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            tools=self.tools.definitions,
            messages=messages,
            output_config={"effort": self.effort},
            # кешируем системный промпт, инструменты и историю диалога
            cache_control={"type": "ephemeral"},
        )
        if self.model in FALLBACK_MODELS:
            # при отказе классификатора запрос сам переиграется на рекомендованной модели
            return await self.client.beta.messages.create(**params, betas=[FALLBACK_BETA],
                                                          fallbacks="default")
        return await self.client.beta.messages.create(**params)

    async def _run_tools(self, response, ctx: TurnContext) -> list[dict]:
        results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            try:
                content = await self.tools.execute(block.name, block.input, ctx)
                results.append({"type": "tool_result", "tool_use_id": block.id, "content": content})
            except ToolError as e:
                results.append({"type": "tool_result", "tool_use_id": block.id,
                                "content": str(e), "is_error": True})
            except Exception as e:
                log.exception("Инструмент %s упал", block.name)
                results.append({"type": "tool_result", "tool_use_id": block.id,
                                "content": f"Внутренняя ошибка инструмента: {e}", "is_error": True})
        # все результаты одним сообщением — иначе модель перестаёт вызывать инструменты параллельно
        return results
