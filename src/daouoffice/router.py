"""Per-room message routing.

A DaouOffice bot account is just a member of rooms — anyone can add it to any
room, and there is no per-room "install" step. So the safe default is an
*allowlist*: handle the rooms you explicitly registered, ignore the rest.

:class:`RoomRouter` is callable, so pass it straight to ``DaouBot`` as
``prompt_func``::

    router = RoomRouter()

    @router.room("11000303036")
    async def standup(msg): ...

    @router.room_type("SINGLE")
    async def dm(msg): return f"안녕하세요, {msg.sender_name}님"

    @router.default                       # optional catch-all
    async def fallback(msg): return None

    bot = DaouBot(..., prompt_func=router)

Resolution order: exact ``room_id`` → ``room_type`` → default → ``None``
(no reply). With no default, unregistered rooms are silently ignored.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable

from daouoffice.client import NewMessage

logger = logging.getLogger(__name__)

Handler = Callable[[NewMessage], Awaitable[str | None] | str | None]


class RoomRouter:
    """Allowlist-by-default dispatcher keyed by room id / room type."""

    def __init__(self, *, default: Handler | None = None) -> None:
        self._by_room: dict[str, Handler] = {}
        self._by_type: dict[str, Handler] = {}
        self._default: Handler | None = default

    # -- registration (callable or decorator) ---------------------------

    def add_room(self, room_id: str, handler: Handler) -> None:
        self._by_room[room_id] = handler

    def add_room_type(self, room_type: str, handler: Handler) -> None:
        self._by_type[room_type.upper()] = handler

    def set_default(self, handler: Handler) -> None:
        self._default = handler

    def room(self, room_id: str) -> Callable[[Handler], Handler]:
        """Decorator: register a handler for one room id."""

        def deco(fn: Handler) -> Handler:
            self.add_room(room_id, fn)
            return fn

        return deco

    def room_type(self, room_type: str) -> Callable[[Handler], Handler]:
        """Decorator: register a handler for a room type (SINGLE/GROUP)."""

        def deco(fn: Handler) -> Handler:
            self.add_room_type(room_type, fn)
            return fn

        return deco

    def default(self, fn: Handler) -> Handler:
        """Decorator: register the catch-all handler."""
        self.set_default(fn)
        return fn

    # -- dispatch -------------------------------------------------------

    def resolve(self, msg: NewMessage) -> Handler | None:
        return (
            self._by_room.get(msg.room_id)
            or self._by_type.get((msg.room_type or "").upper())
            or self._default
        )

    async def __call__(self, msg: NewMessage) -> str | None:
        handler = self.resolve(msg)
        if handler is None:
            logger.debug("no handler for room %s — ignored", msg.room_id)
            return None
        result = handler(msg)
        if asyncio.iscoroutine(result):
            return await result
        return result  # type: ignore[return-value]
