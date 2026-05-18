"""DaouOffice Messenger Bot — REST polling engine.

This is the single polling implementation used by :class:`daouoffice.DaouBot`.
It periodically lists rooms and, per room with unread messages, dispatches only
messages newer than the last one it has handled (tracked by ``chatMessageId``).

On first contact with a room the existing backlog is **not** replayed — a
baseline is set so the bot only reacts to messages that arrive while it is
running. The bot's own messages are skipped via the identity resolved at login.

Polling is the only delivery mechanism. A WebSocket/STOMP endpoint
(``GET /ws/pc``) was observed in the traffic capture but its flow was never
validated, so it is intentionally not implemented (see docs/04-websocket.md).
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable

from daouoffice.client import BotClient, NewMessage, parse_mentions
from daouoffice.state import CursorStore, MemoryCursorStore

logger = logging.getLogger(__name__)

POLL_INTERVAL = 5

OnMessageCallback = Callable[[NewMessage], Awaitable[str | None]]
"""Async callback: receives a NewMessage, returns a reply string or None."""


class BotEngine:
    """REST polling bot engine.

    Delivery is **at-least-once** (the message-delivery industry standard):
    a message is re-delivered until its handler returns without raising,
    processed in order per room. This is not configurable — make handlers
    idempotent if a duplicate reply would matter. For fire-and-forget, have
    the handler swallow its own errors (it then never "fails", so it is not
    retried).

    Args:
        client: A logged-in :class:`BotClient`.
        on_message: Async callback invoked per inbound message.
        poll_interval: Seconds between poll cycles.
        cursors: Where to persist the per-room processed cursor. Defaults to
            an in-memory store (not durable across restarts); pass a
            :class:`~daouoffice.state.FileCursorStore` to resume after restart.
        max_attempts: give up on a single message after this many failed
            handler attempts and move on (poison-message guard).
    """

    def __init__(
        self,
        client: BotClient,
        on_message: OnMessageCallback,
        *,
        poll_interval: int = POLL_INTERVAL,
        cursors: CursorStore | None = None,
        max_attempts: int = 5,
    ) -> None:
        self._client = client
        self._on_message = on_message
        self._poll_interval = poll_interval
        self._running = False
        self._max_attempts = max_attempts
        # room_id -> highest chatMessageId already handled
        self._cursors: CursorStore = cursors or MemoryCursorStore()
        # "room_id:mid" -> failed handler attempts
        self._attempts: dict[str, int] = {}

    async def start(self) -> None:
        """Run the poll loop until :meth:`stop` is called."""
        logger.info("Starting bot engine (REST polling, interval=%ss)", self._poll_interval)
        self._running = True
        failures = 0
        while self._running:
            try:
                await self._poll_once()
                failures = 0
            except Exception:
                failures += 1
                logger.exception("Poll cycle failed (consecutive=%d)", failures)
            # Exponential backoff on sustained failure (cap 5 min) so a
            # misconfigured/clearly-down server is not hammered every interval.
            delay = self._poll_interval
            if failures:
                delay = min(self._poll_interval * (2 ** min(failures, 6)), 300)
            await asyncio.sleep(delay)

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

        baseline = self._cursors.get(room_id)
        if baseline is None:
            # First time we ever see this room: don't replay the backlog.
            start_at = max(ids, default=0)
            self._cursors.set(room_id, start_at)
            logger.info(
                "Room %s: baseline at %s (%d backlog message(s) skipped)",
                room_id,
                start_at,
                len(history),
            )
            await self._mark_read(latest)
            return

        # New messages, oldest first (ordered processing).
        new_items = sorted(
            (
                (mid, item)
                for item in history
                if (mid := self._mid(item)) is not None and mid > baseline
            ),
            key=lambda pair: pair[0],
        )

        handled = baseline
        blocked = False
        for mid, item in new_items:
            msg = self._to_message(item, room_type)
            dispatchable = msg is not None and msg.sender_user_id != self._client.user_id
            if not dispatchable:
                handled = mid  # own / no-text: nothing to deliver, ack it
                continue

            # Only advance the cursor once the handler succeeds (at-least-once).
            if await self._dispatch(msg):
                handled = mid
                self._attempts.pop(f"{room_id}:{mid}", None)
                continue
            key = f"{room_id}:{mid}"
            self._attempts[key] = self._attempts.get(key, 0) + 1
            if self._attempts[key] >= self._max_attempts:
                logger.error(
                    "Giving up on message %s in %s after %d attempts (poison)",
                    mid,
                    room_id,
                    self._attempts[key],
                )
                self._attempts.pop(key, None)
                handled = mid  # skip poison message and keep going
                continue
            blocked = True  # retry this one next cycle; preserve order
            break

        if handled != baseline:
            self._cursors.set(room_id, handled)

        # Read receipts: clear the room only when nothing is pending retry,
        # otherwise leave it unread so the failed message is polled again.
        if not blocked:
            await self._mark_read(latest)
        elif handled != baseline:
            await self._mark_read(handled)

    async def _mark_read(self, message_id) -> None:
        try:
            await asyncio.to_thread(self._client.mark_read, message_id)
        except Exception:
            logger.exception("mark_read failed for %s", message_id)

    def _to_message(self, item, room_type: str) -> NewMessage | None:
        sender = item.sender or {}
        raw = (item.contents or {}).get("message", {}).get("text", "")
        if not raw:
            return None
        clean, mentions, mention_all = parse_mentions(raw)
        return NewMessage(
            room_id=item.chatRoomId,
            room_type=room_type,
            sender_user_id=str(sender.get("platformUserId", "")),
            sender_name=sender.get("platformUserName", ""),
            message_text=clean,
            message_id=str(item.chatMessageId),
            created_at=item.createdAt,
            raw_text=raw,
            mentions=mentions,
            mentions_me=self._client.user_id in mentions,
            mention_all=mention_all,
        )

    async def _dispatch(self, msg: NewMessage) -> bool:
        """Run the handler and send any reply. Returns True on success."""
        logger.info("[%s] %s: %s", msg.room_id, msg.sender_name, msg.message_text[:80])
        try:
            reply = await self._on_message(msg)
            if reply:
                await asyncio.to_thread(self._client.send_message, msg.room_id, reply)
                logger.info("Replied to [%s]", msg.room_id)
            return True
        except Exception:
            logger.exception("Handler failed for [%s]", msg.room_id)
            return False
