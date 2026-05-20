"""Per-room message routing.

A DaouOffice bot account is just a member of rooms — anyone can add it to any
room, and there is no per-room "install" step. So the safe default is an
*allowlist*: handle the rooms you explicitly registered, ignore the rest.

:class:`RoomRouter` is callable, so pass it straight to ``DaouBot`` as
``on_message``::

    router = RoomRouter()

    @router.room("11000303036")
    async def standup(msg): ...

    @router.room_type("SINGLE")
    async def dm(msg): return f"안녕하세요, {msg.sender_name}님"

    @router.default                       # optional catch-all
    async def fallback(msg): return None

    bot = DaouBot(..., on_message=router)

Resolution order: exact ``room_id`` → ``room_type`` → default → ``None``
(no reply). With no default, unregistered rooms are silently ignored.
"""

from __future__ import annotations

import asyncio
import logging
import re
from collections.abc import Awaitable, Callable, Iterable

from daouoffice.client import NewMessage

logger = logging.getLogger(__name__)

Handler = Callable[[NewMessage], Awaitable[str | None] | str | None]


def only_when_mentioned(fn: Handler, *, include_all: bool = True) -> Handler:
    """Wrap a handler so it runs only when the bot is mentioned.

    The declarative gate for noisy group rooms (the equivalent of subscribing
    to Slack's ``app_mention`` instead of ``message``). Composable with a bare
    ``on_message`` or any :class:`RoomRouter` registration; intentionally not
    a global engine knob — the policy lives at the handler, where it varies.

    Args:
        fn: The handler to gate.
        include_all: Also pass through an ``@ALL`` / mention-everyone message.
    """

    async def gated(msg: NewMessage) -> str | None:
        if not (msg.mentions_me or (include_all and msg.mention_all)):
            return None
        result = fn(msg)
        if asyncio.iscoroutine(result):
            return await result
        return result  # type: ignore[return-value]

    return gated


# Letters (case-insensitive), Hangul syllables, digits, and underscore.
# Used as the "word" class for alias boundary lookbehind/lookahead so
# `@디티` matches "@디티 누구야" but not "@디티봇" or "@디티는".
_ALIAS_WORD = r"[A-Za-z가-힣ㄱ-ㆎ0-9_]"


def only_when_addressed(
    fn: Handler,
    *,
    aliases: Iterable[str] = (),
    include_all: bool = True,
) -> Handler:
    """Wrap a handler so it runs only when the bot is addressed.

    Superset of :func:`only_when_mentioned`: the wrapped handler runs when

    * the bot is @-mentioned (``mentions_me``, token-bound to the bot's
      user_id), or
    * ``include_all`` is set and the message has an ``@ALL`` mention, or
    * any element of ``aliases`` appears in ``message_text`` as ``@<alias>``
      with non-word boundaries on each side (so ``@디티`` matches
      ``"@디티 누구야"`` but not ``"@디티봇"`` or ``"@디티는"``).

    Matching is case-insensitive. With ``aliases=()`` this behaves
    identically to :func:`only_when_mentioned`.

    The alias path is text-only — no server check that ``@<alias>``
    really addresses *this* bot, so don't gate privileged actions on it.
    It is a way for people to call the bot, not a permission.
    """
    aliases_t = tuple(a for a in aliases if a)
    alias_re: re.Pattern[str] | None = None
    if aliases_t:
        alts = "|".join(re.escape(a) for a in aliases_t)
        alias_re = re.compile(
            rf"(?<!{_ALIAS_WORD})@(?:{alts})(?!{_ALIAS_WORD})",
            re.IGNORECASE,
        )

    async def gated(msg: NewMessage) -> str | None:
        addressed = (
            msg.mentions_me
            or (include_all and msg.mention_all)
            or (alias_re is not None and alias_re.search(msg.message_text) is not None)
        )
        if not addressed:
            return None
        result = fn(msg)
        if asyncio.iscoroutine(result):
            return await result
        return result  # type: ignore[return-value]

    return gated


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
