"""DaouOffice Messenger SDK — high-level :class:`DaouBot`.

Example::

    import asyncio
    from daouoffice import DaouBot

    async def main():
        bot = DaouBot(
            login_id="my-bot",
            password="...",                          # or env DAOU_PASSWORD
            base_url="https://acme.daouoffice.com",  # or env DAOU_BASE_URL
            company_id="11000000000",                # or env DAOU_COMPANY_ID
        )
        await bot.run_forever()

    asyncio.run(main())

Configuration is never hard-coded: ``base_url``, ``company_id``, and the LLM
backend settings can all come from constructor arguments or environment
variables. Use the ``daoubot discover`` CLI to look up ``company_id`` and your
bot account's user id.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable

from daouoffice.client import BotClient, NewMessage
from daouoffice.engine import POLL_INTERVAL, BotEngine
from daouoffice.llm_handler import SYSTEM_PROMPT, BackendRegistry, BaseLlmBackend

logger = logging.getLogger(__name__)

PromptFunc = Callable[[NewMessage], Awaitable[str | None] | str | None]


class DaouBot:
    """High-level DaouOffice messenger bot.

    Message handling precedence: ``prompt_func`` → ``!``-prefixed command →
    LLM backend → no reply.

    Args:
        login_id: Bot account login id.
        password: Bot account password.
        base_url: Tenant URL (or env ``DAOU_BASE_URL``).
        company_id: Tenant company id (or env ``DAOU_COMPANY_ID``).
        system_prompt: System prompt for the LLM backend.
        prompt_func: Callback ``(NewMessage) -> str | None`` (sync or async).
            Return a string to reply, ``None`` to fall through.
        poll_interval: Seconds between poll cycles.
        llm: Backend id — ``"api"`` (default), ``"claude-cli"``, ``"ollama"``,
            ``"hermes-cli"``, ``"cli:<command>"``, or ``"none"`` to disable.
        llm_model: Model name for the ``api`` backend.
    """

    def __init__(
        self,
        login_id: str,
        password: str,
        *,
        base_url: str | None = None,
        company_id: str | None = None,
        system_prompt: str = SYSTEM_PROMPT,
        prompt_func: PromptFunc | None = None,
        poll_interval: int = POLL_INTERVAL,
        llm: str = "api",
        llm_model: str = "claude-sonnet-4-5",
    ) -> None:
        self._client = BotClient(
            login_id, password, base_url=base_url, company_id=company_id
        )
        self._prompt_func = prompt_func
        self._engine = BotEngine(
            self._client, self._on_message, poll_interval=poll_interval
        )

        self._llm: BaseLlmBackend | None = None
        if llm and llm != "none":
            self._llm = BackendRegistry.resolve(llm)
            if llm == "api" and llm_model:
                self._llm._model = llm_model  # type: ignore[attr-defined]
            logger.info("LLM backend: %s", llm)
        else:
            logger.info("LLM disabled")

    @property
    def client(self) -> BotClient:
        """The underlying REST client (logged in after :meth:`start`)."""
        return self._client

    def set_prompt_func(self, func: PromptFunc | None) -> None:
        """Set/replace the message handler callback."""
        self._prompt_func = func

    async def start(self) -> None:
        """Log in and start the polling engine (runs until stopped)."""
        await asyncio.to_thread(self._client.login)
        await self._engine.start()

    async def stop(self) -> None:
        self._engine.stop()
        await asyncio.to_thread(self._client.logout)

    async def run_forever(self) -> None:
        """Start the bot and run until cancelled (Ctrl-C)."""
        try:
            await self.start()
        except (KeyboardInterrupt, asyncio.CancelledError):
            pass
        finally:
            await self.stop()

    async def send_message(self, room_id: str, content: str) -> str:
        return await asyncio.to_thread(
            self._client.send_message, room_id, content
        )

    # -- internal -------------------------------------------------------

    async def _on_message(self, msg: NewMessage) -> str | None:
        if self._prompt_func is not None:
            result = self._prompt_func(msg)
            if asyncio.iscoroutine(result):
                return await result
            return result  # type: ignore[return-value]

        if msg.message_text.startswith("!"):
            return f"알겠습니다. {msg.message_text[1:].strip()}"

        if self._llm is not None:
            return await self._llm.generate(
                msg.message_text, context=f"sender={msg.sender_name}"
            )
        return None
