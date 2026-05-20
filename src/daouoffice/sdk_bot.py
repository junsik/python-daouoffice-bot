"""DaouOffice Messenger SDK — high-level :class:`DaouBot`.

A bot is a background daemon. Onboard once with ``daoubot login`` (writes
``~/.daoubot/profile.yaml`` — tenant, identity, session token and the
password, so it re-authenticates unattended). Then the bot just runs:

    import asyncio
    from daouoffice import DaouBot, NewMessage

    async def on_message(msg: NewMessage) -> str | None:
        if "안녕" in msg.message_text:
            return f"안녕하세요, {msg.sender_name}님!"
        return None

    async def main():
        bot = DaouBot(on_message=on_message)   # resolves from profile.yaml
        await bot.run_forever()

    asyncio.run(main())

The session token lives ~30 minutes. For unattended operation set
``DAOU_PASSWORD`` (e.g. a systemd ``EnvironmentFile``) so the bot
re-authenticates itself indefinitely; the refreshed token is written back to
the profile. Without a password the bot runs until the token expires and then
stops with a clear error (the password is deliberately never stored on disk).

Any connection value may be overridden by an explicit argument or a ``DAOU_*``
environment variable (precedence: argument > env > profile).

The SDK does one thing: talk to DaouOffice messenger. It deliberately does
**not** bundle an LLM — call whatever you want inside ``on_message``.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import signal
from collections.abc import Awaitable, Callable

from daouoffice.client import BotClient, DaouAuthError, DaouConfigError, NewMessage
from daouoffice.config import load_settings
from daouoffice.engine import POLL_INTERVAL, BotEngine
from daouoffice.profile import Profile, load_profile, save_profile
from daouoffice.state import CursorStore, FileCursorStore

logger = logging.getLogger(__name__)

#: A message handler: ``(NewMessage) -> str | None`` (sync or async).
#: Return a string to reply, ``None`` for no reply.
MessageHandler = Callable[[NewMessage], Awaitable[str | None] | str | None]


def _build_client(
    *,
    base_url: str | None,
    company_id: str | None,
    login_id: str | None,
    password: str | None,
    base_dir: str | os.PathLike[str] | None = None,
    app_config: str | os.PathLike[str] | None = None,
) -> BotClient:
    """Resolve connection (arg > env > app config > profile) and build a client.

    With a password the client re-authenticates on its own (the background
    case); the fresh token is persisted to the profile after every login.
    Without a password it runs on the saved profile token until it expires.

    ``base_dir`` relocates the profile from ``~/.daoubot/`` to
    ``<base_dir>/.daoubot/`` (read *and* write), so independent instances on
    one machine can keep separate sessions. ``app_config`` (or
    ``DAOU_APP_CONFIG`` env) points at an operator YAML whose
    ``daouoffice:`` section provides connection values — the SDK reads it
    only, never writes back, so the operator's commented file stays intact
    and SDK-managed tokens stay in the profile.
    """
    s = load_settings(
        base_url=base_url,
        company_id=company_id,
        login_id=login_id,
        password=password,
        app_config=app_config,
    )
    prof = load_profile(base_dir)

    def _persist(c: BotClient) -> None:
        if c.identity is None:
            return
        save_profile(
            Profile(
                base_url=s.base_url,
                company_id=c.identity.company_id,
                company_uuid=c.identity.company_uuid,
                company_domain=c.identity.company_domain,
                login_id=c.identity.login_id,
                user_id=c.identity.user_id,
                name=c.identity.name,
                access_token=c.access_token,
                refresh_token=c.refresh_token,
                password=c._password or (prof.password if prof else ""),
            ),
            base_dir,
        )

    if s.password:
        return BotClient(
            s.login_id,
            s.password,
            base_url=s.base_url,
            company_id=s.company_id,
            on_auth=_persist,
        )
    if prof and prof.access_token:
        return BotClient.from_token(
            s.base_url,
            prof.access_token,
            refresh_token=prof.refresh_token,
            on_auth=_persist,
        )
    raise DaouConfigError(
        "No credentials and no saved session. Run `daoubot login` first, "
        "or set DAOU_PASSWORD (e.g. a systemd EnvironmentFile) for "
        "unattended operation."
    )


class DaouBot:
    """High-level DaouOffice messenger bot (background daemon).

    All connection settings (including the password) resolve from
    ``daoubot login``'s ``~/.daoubot/profile.yaml``, overridable by an
    explicit argument, a ``DAOU_*`` environment variable, or an operator
    app config (``app_config``/``DAOU_APP_CONFIG``). Precedence:
    argument > env > app config > profile. The persisted password lets
    the daemon re-authenticate unattended when the token expires.

    Args:
        base_url / company_id / login_id / password: connection overrides;
            normally resolved from the profile (login_id) / env, so a bot is
            just ``DaouBot(on_message=...)``.
        app_config: path to an operator YAML whose ``daouoffice:`` section
            provides connection values (``base_url`` / ``company_id`` /
            ``login_id`` / ``password``) — read-only, never overwritten by
            the SDK, so an app's own commented config file (e.g. an
            ``agent.yaml``) can carry the SDK connection alongside its own
            settings without ``daoubot login``. Also picked up from the
            ``DAOU_APP_CONFIG`` env var.
        base_dir: relocate the profile *and* the default cursor store from
            ``~/.daoubot/`` to ``<base_dir>/.daoubot/``. Give each instance
            on one machine a different ``base_dir`` to run them concurrently
            without session/cursor races. Ignored if an explicit
            ``cursor_store`` is passed.
        on_message: the message handler ``(NewMessage) -> str | None`` (sync
            or async); ``None`` reply = no reply. Omit to only read/mark.
            Pass a :class:`~daouoffice.RoomRouter` for per-room dispatch.
        poll_interval: seconds between poll cycles.
        cursor_store: where the processed-message cursor is persisted; default
            :class:`~daouoffice.state.FileCursorStore` (resume after restart).
        max_attempts: poison-message guard (delivery is always at-least-once).
        markdown: render replies from Markdown to the chat's HTML subset
            (``**bold**``/``*italic*``/numbered + bullet lists; the only
            styles the chat honors). Off by default — replies sent verbatim.
        client: advanced/internal — use a pre-built :class:`BotClient`.
    """

    def __init__(
        self,
        *,
        base_url: str | None = None,
        company_id: str | None = None,
        login_id: str | None = None,
        password: str | None = None,
        on_message: MessageHandler | None = None,
        poll_interval: int = POLL_INTERVAL,
        cursor_store: CursorStore | None = None,
        max_attempts: int = 5,
        markdown: bool = False,
        client: BotClient | None = None,
        base_dir: str | os.PathLike[str] | None = None,
        app_config: str | os.PathLike[str] | None = None,
    ) -> None:
        self._client = client or _build_client(
            base_url=base_url,
            company_id=company_id,
            login_id=login_id,
            password=password,
            base_dir=base_dir,
            app_config=app_config,
        )
        self._handler = on_message
        self._engine = BotEngine(
            self._client,
            self._invoke_handler,
            poll_interval=poll_interval,
            cursors=cursor_store or FileCursorStore(base_dir),
            max_attempts=max_attempts,
            markdown=markdown,
        )

    @property
    def client(self) -> BotClient:
        """The underlying REST client (authenticated after :meth:`start`)."""
        return self._client

    def set_handler(self, on_message: MessageHandler | None) -> None:
        """Set/replace the message handler."""
        self._handler = on_message

    async def start(self) -> None:
        """Authenticate and run the polling engine until stopped.

        With credentials the bot logs in and thereafter re-authenticates
        itself on token expiry (background case). Token-only (a saved
        profile, no password) validates the token; once it expires there is
        nothing to recover from, so it stops with a clear error directing the
        operator to set ``DAOU_PASSWORD``.
        """
        if self._client._can_relogin():
            await asyncio.to_thread(self._client.login)
        else:
            await asyncio.to_thread(self._resolve_identity)
        await self._engine.start()

    def _resolve_identity(self) -> None:
        try:
            self._client.identity = self._client.whoami()
        except Exception as e:
            raise DaouAuthError(
                "Saved session token is invalid or expired. Set DAOU_PASSWORD "
                "for unattended re-authentication, or run `daoubot login`."
            ) from e

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
