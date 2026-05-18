"""DaouOffice Messenger Bot — REST polling engine.

This is the single polling implementation used by :class:`daouoffice.DaouBot`.
It periodically lists rooms and, per room with unread messages, dispatches only
messages newer than the last one it has handled (tracked by ``chatMessageId``).

On first contact with a room the existing backlog is **not** replayed — a
baseline is set so the bot only reacts to messages that arrive while it is
running. The bot's own messages are skipped via the identity resolved at login.

Real-time WebSocket/STOMP delivery is experimental and lives in
``ws_handler.py``; the polling engine is the supported path.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable

from daouoffice.client import BotClient, NewMessage

logger = logging.getLogger(__name__)

POLL_INTERVAL = 5

OnMessageCallback = Callable[[NewMessage], Awaitable[str | None]]
"""Async callback: receives a NewMessage, returns a reply string or None."""


class BotEngine:
    """REST polling bot engine.

    Args:
        client: A logged-in :class:`BotClient`.
        on_message: Async callback invoked per inbound message.
        poll_interval: Seconds between poll cycles.
    """

    def __init__(
        self,
        client: BotClient,
        on_message: OnMessageCallback,
        *,
        poll_interval: int = POLL_INTERVAL,
    ) -> None:
        self._client = client
        self._on_message = on_message
        self._poll_interval = poll_interval
        self._running = False
        # room_id -> highest chatMessageId already handled (baseline)
        self._seen: dict[str, int] = {}

    async def start(self) -> None:
        """Run the poll loop until :meth:`stop` is called."""
        logger.info("Starting bot engine (REST polling, interval=%ss)", self._poll_interval)
        self._running = True
        while self._running:
            try:
                await self._poll_once()
            except Exception:
                logger.exception("Poll cycle failed")
            await asyncio.sleep(self._poll_interval)

    def stop(self) -> None:
        self._running = False

    # -- internals ------------------------------------------------------

    async def _poll_once(self) -> None:
        rooms = await asyncio.to_thread(self._client.get_rooms)
        for room in rooms:
            if room.unreadMessageCount > 0:
                await self._handle_room(room.roomId, room.roomType)

    @staticmethod
    def _mid(item) -> int | None:
        try:
            return int(item.chatMessageId)
        except (TypeError, ValueError):
            return None

    async def _handle_room(self, room_id: str, room_type: str) -> None:
        try:
            history = await asyncio.to_thread(self._client.get_chat_history, room_id, offset=20)
        except Exception:
            logger.exception("Failed to fetch history for %s", room_id)
            return
        if not history:
            return

        ids = [m for m in (self._mid(it) for it in history) if m is not None]
        latest = history[-1].chatMessageId

        baseline = self._seen.get(room_id)
        if baseline is None:
            # First time we see this room: don't replay the backlog.
            self._seen[room_id] = max(ids, default=0)
            logger.info(
                "Room %s: baseline at %s (%d backlog message(s) skipped)",
                room_id,
                self._seen[room_id],
                len(history),
            )
            await self._mark_read(latest)
            return

        handled = baseline
        for item in history:
            mid = self._mid(item)
            if mid is not None and mid <= baseline:
                continue  # already handled in a previous cycle
            if mid is not None:
                handled = max(handled, mid)
            msg = self._to_message(item, room_type)
            if msg is None:
                continue
            if msg.sender_user_id == self._client.user_id:
                continue  # skip our own messages
            await self._dispatch(msg)

        self._seen[room_id] = handled
        await self._mark_read(latest)

    async def _mark_read(self, message_id) -> None:
        try:
            await asyncio.to_thread(self._client.mark_read, message_id)
        except Exception:
            logger.exception("mark_read failed for %s", message_id)

    def _to_message(self, item, room_type: str) -> NewMessage | None:
        sender = item.sender or {}
        text = (item.contents or {}).get("message", {}).get("text", "")
        if not text:
            return None
        return NewMessage(
            room_id=item.chatRoomId,
            room_type=room_type,
            sender_user_id=str(sender.get("platformUserId", "")),
            sender_name=sender.get("platformUserName", ""),
            message_text=text,
            message_id=str(item.chatMessageId),
            created_at=item.createdAt,
        )

    async def _dispatch(self, msg: NewMessage) -> None:
        logger.info("[%s] %s: %s", msg.room_id, msg.sender_name, msg.message_text[:80])
        try:
            reply = await self._on_message(msg)
            if reply:
                await asyncio.to_thread(self._client.send_message, msg.room_id, reply)
                logger.info("Replied to [%s]", msg.room_id)
        except Exception:
            logger.exception("Handler failed for [%s]", msg.room_id)
