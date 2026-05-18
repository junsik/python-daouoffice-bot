"""DaouOffice Messenger SDK — high-level :class:`DaouBot`.

Example::

    import asyncio
    from daouoffice import DaouBot, NewMessage

    async def on_message(msg: NewMessage) -> str | None:
        if "안녕" in msg.message_text:
            return f"안녕하세요, {msg.sender_name}님!"
        return None

    async def main():
        bot = DaouBot(
            login_id="my-bot",
            password="...",                          # or env DAOU_PASSWORD
            base_url="https://acme.daouoffice.com",  # or env DAOU_BASE_URL
            company_id="11000000000",                # or env DAOU_COMPANY_ID
            prompt_func=on_message,
        )
        await bot.run_forever()

    asyncio.run(main())

The SDK does one thing: talk to DaouOffice messenger. It deliberately does
**not** bundle an LLM — wire whatever you want inside ``prompt_func``. See
``examples/bot-assistant`` for a minimal LLM integration.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable

from daouoffice.client import BotClient, NewMessage
from daouoffice.engine import AT_LEAST_ONCE, POLL_INTERVAL, BotEngine
from daouoffice.state import CursorStore, FileCursorStore

logger = logging.getLogger(__name__)

PromptFunc = Callable[[NewMessage], Awaitable[str | None] | str | None]


class DaouBot:
    """High-level DaouOffice messenger bot.

    Args:
        login_id: Bot account login id.
        password: Bot account password.
        base_url: Tenant URL (or env ``DAOU_BASE_URL``).
        company_id: Tenant company id (or env ``DAOU_COMPANY_ID``).
        prompt_func: Callback ``(NewMessage) -> str | None`` (sync or async).
            Return a string to reply, ``None`` for no reply. If omitted, the
            bot only reads/marks messages and never replies.
        poll_interval: Seconds between poll cycles.
        cursor_store: Where the processed-message cursor is persisted.
            Defaults to a :class:`~daouoffice.state.FileCursorStore`
            (``.daoubot/cursors.json``) so a restart resumes where it left
            off. Pass :class:`~daouoffice.state.MemoryCursorStore` to opt out.
        delivery: ``"at_least_once"`` (default) or ``"at_most_once"`` — see
            :class:`~daouoffice.engine.BotEngine`.
        max_attempts: poison-message guard for at-least-once delivery.
    """

    def __init__(
        self,
        login_id: str,
        password: str,
        *,
        base_url: str | None = None,
        company_id: str | None = None,
        prompt_func: PromptFunc | None = None,
        poll_interval: int = POLL_INTERVAL,
        cursor_store: CursorStore | None = None,
        delivery: str = AT_LEAST_ONCE,
        max_attempts: int = 5,
    ) -> None:
        self._client = BotClient(login_id, password, base_url=base_url, company_id=company_id)
        self._prompt_func = prompt_func
        self._engine = BotEngine(
            self._client,
            self._on_message,
            poll_interval=poll_interval,
            cursors=cursor_store or FileCursorStore(),
            delivery=delivery,
            max_attempts=max_attempts,
        )

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
        return await asyncio.to_thread(self._client.send_message, room_id, content)

    # -- internal -------------------------------------------------------

    async def _on_message(self, msg: NewMessage) -> str | None:
        if self._prompt_func is None:
            return None
        result = self._prompt_func(msg)
        if asyncio.iscoroutine(result):
            return await result
        return result  # type: ignore[return-value]
