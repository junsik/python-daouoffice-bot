"""DaouOffice Messenger SDK — high-level :class:`DaouBot`.

Example::

    import asyncio
    import os
    from daouoffice import DaouBot, NewMessage

    async def on_message(msg: NewMessage) -> str | None:
        if "안녕" in msg.message_text:
            return f"안녕하세요, {msg.sender_name}님!"
        return None

    async def main():
        bot = DaouBot(
            base_url=os.environ["DAOU_BASE_URL"],
            company_id=os.environ["DAOU_COMPANY_ID"],
            login_id=os.environ["DAOU_LOGIN_ID"],
            password=os.environ["DAOU_PASSWORD"],
            on_message=on_message,
        )
        await bot.run_forever()

    asyncio.run(main())

The SDK does one thing: talk to DaouOffice messenger. It deliberately does
**not** bundle an LLM — call whatever you want inside ``on_message``. See
``examples/bot-assistant`` for a minimal LLM integration.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import signal
from collections.abc import Awaitable, Callable

from daouoffice.client import BotClient, NewMessage
from daouoffice.config import load_settings
from daouoffice.engine import POLL_INTERVAL, BotEngine
from daouoffice.state import CursorStore, FileCursorStore

logger = logging.getLogger(__name__)

#: A message handler: ``(NewMessage) -> str | None`` (sync or async).
#: Return a string to reply, ``None`` for no reply.
MessageHandler = Callable[[NewMessage], Awaitable[str | None] | str | None]


class DaouBot:
    """High-level DaouOffice messenger bot.

    Args:
        login_id: Bot account login id.
        password: Bot account password.
        base_url: Tenant URL (or env ``DAOU_BASE_URL``).
        company_id: Tenant company id (or env ``DAOU_COMPANY_ID``).
        on_message: The message handler — ``(NewMessage) -> str | None``
            (sync or async). Return a string to reply, ``None`` for no reply.
            If omitted, the bot only reads/marks messages and never replies.
            Pass a :class:`~daouoffice.RoomRouter` here for per-room dispatch.
        poll_interval: Seconds between poll cycles.
        cursor_store: Where the processed-message cursor is persisted.
            Defaults to a :class:`~daouoffice.state.FileCursorStore`
            (``.daoubot/cursors.json``) so a restart resumes where it left
            off. Pass :class:`~daouoffice.state.MemoryCursorStore` to opt out.
        max_attempts: poison-message guard — give up on a message after this
            many failed handler attempts (delivery is always at-least-once;
            see :class:`~daouoffice.engine.BotEngine`).
    """

    def __init__(
        self,
        login_id: str,
        password: str,
        *,
        base_url: str | None = None,
        company_id: str | None = None,
        on_message: MessageHandler | None = None,
        poll_interval: int = POLL_INTERVAL,
        cursor_store: CursorStore | None = None,
        max_attempts: int = 5,
    ) -> None:
        self._client = BotClient(login_id, password, base_url=base_url, company_id=company_id)
        self._handler = on_message
        self._engine = BotEngine(
            self._client,
            self._invoke_handler,
            poll_interval=poll_interval,
            cursors=cursor_store or FileCursorStore(),
            max_attempts=max_attempts,
        )

    @classmethod
    def from_env(
        cls,
        *,
        on_message: MessageHandler | None = None,
        poll_interval: int = POLL_INTERVAL,
        cursor_store: CursorStore | None = None,
        max_attempts: int = 5,
        **overrides: str,
    ) -> DaouBot:
        """Build a bot from env / profile (see :func:`daouoffice.load_settings`).

        A terse shortcut for production/CLI use. ``overrides`` may pass any of
        ``base_url``/``company_id``/``login_id``/``password`` explicitly;
        everything else comes from ``DAOU_*`` env vars or
        ``.daoubot/profile.json``. (Examples construct ``DaouBot`` explicitly
        instead, so the required settings are visible in the code.)
        """
        s = load_settings(**overrides)
        return cls(
            s.login_id,
            s.password,
            base_url=s.base_url,
            company_id=s.company_id,
            on_message=on_message,
            poll_interval=poll_interval,
            cursor_store=cursor_store,
            max_attempts=max_attempts,
        )

    @property
    def client(self) -> BotClient:
        """The underlying REST client (logged in after :meth:`start`)."""
        return self._client

    def set_handler(self, on_message: MessageHandler | None) -> None:
        """Set/replace the message handler."""
        self._handler = on_message

    async def start(self) -> None:
        """Log in and start the polling engine (runs until stopped)."""
        await asyncio.to_thread(self._client.login)
        await self._engine.start()

    async def stop(self) -> None:
        self._engine.stop()
        await asyncio.to_thread(self._client.logout)

    async def run_forever(self) -> None:
        """Run until SIGINT/SIGTERM (Ctrl-C, ``systemctl stop``) or error.

        Installs signal handlers for a graceful shutdown (logout) — important
        under systemd, which stops services with SIGTERM. Falls back to plain
        cancellation where signal handlers are unavailable (e.g. Windows).
        """
        loop = asyncio.get_running_loop()
        stop = asyncio.Event()
        installed: list[signal.Signals] = []
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, stop.set)
                installed.append(sig)
            except (NotImplementedError, AttributeError, ValueError):
                pass  # not supported on this platform/loop

        runner = asyncio.ensure_future(self.start())
        waiter = asyncio.ensure_future(stop.wait())
        try:
            await asyncio.wait({runner, waiter}, return_when=asyncio.FIRST_COMPLETED)
            if runner.done():
                runner.result()  # surface start()/login errors to the caller
        except (KeyboardInterrupt, asyncio.CancelledError):
            pass
        finally:
            self._engine.stop()
            for fut in (runner, waiter):
                if not fut.done():
                    fut.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await fut
            for sig in installed:
                loop.remove_signal_handler(sig)
            await self.stop()

    async def send_message(self, room_id: str, content: str) -> str:
        return await asyncio.to_thread(self._client.send_message, room_id, content)

    async def send_file(self, room_id: str, path: str, content: str = "") -> str:
        """Upload a file (e.g. a generated newsletter .md/.html) to a room."""
        return await asyncio.to_thread(self._client.send_file, room_id, path, content)

    # -- internal -------------------------------------------------------

    async def _invoke_handler(self, msg: NewMessage) -> str | None:
        if self._handler is None:
            return None
        result = self._handler(msg)
        if asyncio.iscoroutine(result):
            return await result
        return result  # type: ignore[return-value]
