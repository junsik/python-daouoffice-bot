"""Tests for the polling engine: baseline, dedup, dispatch, own-message skip."""

from __future__ import annotations

import asyncio
import logging

import pytest

from daouoffice.client import ChatHistoryItem, ChatRoomItem
from daouoffice.engine import BotEngine, _apply_log_level
from daouoffice.state import MemoryCursorStore


async def _poll(engine):
    """Step the engine one cycle and await the rooms it dispatched.
    Rooms are scheduled concurrently now (cross-room parallel); tests
    need the quiescence barrier to assert deterministically."""
    await engine._poll_once()
    await engine._join()


class FakeClient:
    """Minimal stand-in for BotClient; history is mutable between polls."""

    def __init__(self, history: list[ChatHistoryItem]) -> None:
        self.history = history
        self.user_id = "BOT"
        self.sent: list[tuple[str, str, str | None]] = []
        self.read: list[str] = []
        self.read_rooms: list[str] = []

    def get_rooms(self) -> list[ChatRoomItem]:
        return [ChatRoomItem(roomId="r1", roomType="GROUP", unreadMessageCount=1)]

    def get_chat_history(self, room_id: str, *, offset: int = 20):
        return self.history

    def send_message(self, room_id: str, content: str, *, reply_to=None) -> str:
        self.sent.append((room_id, content, reply_to))
        return "cmid"

    def mark_read(self, message_id, room_id) -> None:
        self.read.append(str(message_id))
        self.read_rooms.append(room_id)


def _msg(user_id: str, text: str, mid: int) -> ChatHistoryItem:
    return ChatHistoryItem(
        chatRoomId="r1",
        chatMessageId=mid,
        sender={"platformUserId": user_id, "platformUserName": "Tester"},
        contents={"message": {"text": text}},
    )


async def _echo(m):
    return f"re: {m.message_text}"


@pytest.mark.asyncio
async def test_poll_failure_backs_off(monkeypatch) -> None:
    class Boom:
        user_id = "BOT"

        def get_rooms(self):
            raise RuntimeError("server down")

    engine = BotEngine(Boom(), _echo, poll_interval=5)
    delays: list[float] = []

    async def fake_sleep(d):
        delays.append(d)
        if len(delays) >= 3:  # let it fail a few times then stop
            engine.stop()

    monkeypatch.setattr("daouoffice.engine.asyncio.sleep", fake_sleep)
    await engine.start()

    # Backoff grows on consecutive failures (not a flat poll_interval).
    assert delays[0] >= 5
    assert delays[1] > delays[0]
    assert delays[2] > delays[1]


@pytest.mark.asyncio
async def test_first_poll_sets_baseline_without_replay() -> None:
    client = FakeClient([_msg("USER", "old1", 1), _msg("USER", "old2", 2)])
    engine = BotEngine(client, _echo)

    await _poll(engine)  # first contact → baseline only

    assert client.sent == []  # backlog not replayed
    assert client.read == ["2"]  # room marked read up to latest
    assert client.read_rooms == ["r1"]  # read is registered against the room


@pytest.mark.asyncio
async def test_new_message_dispatched_once() -> None:
    client = FakeClient([_msg("USER", "old", 1)])
    engine = BotEngine(client, _echo)
    await _poll(engine)  # baseline = 1

    client.history = [_msg("USER", "old", 1), _msg("USER", "hello", 2)]
    await _poll(engine)  # only id 2 is new
    assert client.sent == [("r1", "re: hello", "2")]  # threaded to msg 2

    await _poll(engine)  # same history → no repeat
    assert client.sent == [("r1", "re: hello", "2")]


@pytest.mark.asyncio
async def test_file_only_message_is_delivered_with_attachments() -> None:
    """A file-only message has empty text but a non-empty attachmentList —
    it must reach the handler (regression: it used to be dropped)."""
    seen: list = []

    async def capture(m):
        seen.append(m)

    client = FakeClient([_msg("USER", "old", 1)])
    engine = BotEngine(client, capture)
    await _poll(engine)  # baseline = 1

    file_item = ChatHistoryItem(
        chatRoomId="r1",
        chatMessageId=2,
        sender={"platformUserId": "USER", "platformUserName": "Tester"},
        contents={
            "message": {"text": ""},
            "attachmentList": [{"fileName": "report.pdf", "fileSize": 123}],
        },
    )
    client.history = [_msg("USER", "old", 1), file_item]
    await _poll(engine)

    assert len(seen) == 1
    assert seen[0].message_text == ""
    assert seen[0].attachments == [{"fileName": "report.pdf", "fileSize": 123}]


@pytest.mark.asyncio
async def test_truly_empty_message_is_still_dropped() -> None:
    """No text and no attachments (system/member-left notice) → not delivered."""
    seen: list = []

    async def capture(m):
        seen.append(m)

    client = FakeClient([_msg("USER", "old", 1)])
    engine = BotEngine(client, capture)
    await _poll(engine)

    empty_item = ChatHistoryItem(
        chatRoomId="r1",
        chatMessageId=2,
        sender={"platformUserId": "USER", "platformUserName": "Tester"},
        contents={"message": {"text": ""}},
    )
    client.history = [_msg("USER", "old", 1), empty_item]
    await _poll(engine)
    assert seen == []


@pytest.mark.asyncio
async def test_skips_own_messages_but_advances_baseline() -> None:
    client = FakeClient([_msg("USER", "old", 1)])
    engine = BotEngine(client, _echo)
    await _poll(engine)

    client.history = [_msg("BOT", "my own reply", 2)]
    await _poll(engine)
    assert client.sent == []  # own message not handled

    client.history = [_msg("USER", "next", 3)]
    await _poll(engine)
    assert client.sent == [("r1", "re: next", "3")]  # baseline moved past 2


@pytest.mark.asyncio
async def test_at_least_once_retries_until_success_and_keeps_order() -> None:
    client = FakeClient([_msg("USER", "old", 1)])
    seen: list[str] = []

    async def fail_A_once(m):
        seen.append(m.message_text)
        if m.message_text == "A" and seen.count("A") == 1:
            raise RuntimeError("transient")
        return f"ok: {m.message_text}"

    engine = BotEngine(client, fail_A_once)
    await _poll(engine)  # baseline = 1

    client.history = [_msg("USER", "old", 1), _msg("USER", "A", 2), _msg("USER", "B", 3)]

    await _poll(engine)  # A fails once → blocked, B not reached
    assert client.sent == []

    await _poll(engine)  # A succeeds, then B succeeds (order preserved)
    assert client.sent == [("r1", "ok: A", "2"), ("r1", "ok: B", "3")]


@pytest.mark.asyncio
async def test_at_least_once_poison_message_is_skipped() -> None:
    client = FakeClient([_msg("USER", "old", 1)])

    async def always_fail_A(m):
        if m.message_text == "A":
            raise RuntimeError("poison")
        return f"ok: {m.message_text}"

    engine = BotEngine(client, always_fail_A, max_attempts=2)
    await _poll(engine)  # baseline = 1
    client.history = [_msg("USER", "old", 1), _msg("USER", "A", 2), _msg("USER", "B", 3)]

    await _poll(engine)  # A attempt 1 → blocked
    await _poll(engine)  # A attempt 2 → poison, skip; B delivered
    assert client.sent == [("r1", "ok: B", "3")]


@pytest.mark.asyncio
async def test_burst_not_stranded_after_badge_cleared() -> None:
    # Regression: a rapid burst arriving between get_chat_history and
    # mark_read gets its unread badge cleared by the bot's own mark_read.
    # The engine must still drain it — gating on the cursor vs. the room's
    # latest message id, not on the (self-cleared) unread badge.
    class BadgeRaceClient(FakeClient):
        def get_rooms(self):
            latest = self.history[-1].chatMessageId if self.history else 0
            # unread=0: the bot already "read" the room; only latestMessage
            # reveals there is still something past the cursor.
            return [
                ChatRoomItem(
                    roomId="r1",
                    roomType="GROUP",
                    unreadMessageCount=0,
                    latestMessage={"chatMessageId": latest},
                )
            ]

    client = BadgeRaceClient([_msg("USER", "1", 1)])
    # Establish a baseline at id 1 (first contact uses the unread path).
    client.get_rooms = lambda: [  # type: ignore[method-assign]
        ChatRoomItem(roomId="r1", roomType="GROUP", unreadMessageCount=1)
    ]
    engine = BotEngine(client, _echo)
    await _poll(engine)
    assert client.sent == []  # baseline only

    # Restore the badge-cleared room view and deliver a burst (2,3,4,5).
    del client.get_rooms
    client.history = [_msg("USER", str(n), n) for n in (1, 2, 3, 4, 5)]
    await _poll(engine)

    # All four are dispatched in order despite unreadMessageCount == 0.
    assert client.sent == [
        ("r1", "re: 2", "2"),
        ("r1", "re: 3", "3"),
        ("r1", "re: 4", "4"),
        ("r1", "re: 5", "5"),
    ]

    await _poll(engine)  # caught up → nothing repeats
    assert len(client.sent) == 4


@pytest.mark.asyncio
async def test_handler_swallowing_errors_is_the_fire_and_forget_escape_hatch() -> None:
    # Delivery is always at-least-once; "fire-and-forget" is expressed by a
    # handler that never raises (so it never counts as failed / retried).
    client = FakeClient([_msg("USER", "old", 1)])
    calls: list[str] = []

    async def never_fails(m):
        calls.append(m.message_text)
        try:
            raise RuntimeError("ignored on purpose")
        except Exception:
            return None  # swallow → treated as handled

    engine = BotEngine(client, never_fails)
    await _poll(engine)  # baseline = 1

    client.history = [_msg("USER", "old", 1), _msg("USER", "A", 2)]
    await _poll(engine)
    await _poll(engine)  # nothing new → not retried

    assert calls == ["A"]  # processed exactly once
    assert "2" in client.read  # room cleared


@pytest.mark.asyncio
async def test_markdown_flag_renders_reply_else_verbatim() -> None:
    async def md(m):
        return "**hi** _there_"

    client = FakeClient([_msg("USER", "old", 1)])
    engine = BotEngine(client, md, markdown=True)
    await _poll(engine)  # baseline = 1
    client.history = [_msg("USER", "old", 1), _msg("USER", "ping", 2)]
    await _poll(engine)
    assert client.sent == [("r1", "<b>hi</b> <i>there</i>", "2")]

    plain = FakeClient([_msg("USER", "old", 1)])
    engine2 = BotEngine(plain, md)  # markdown off (default)
    await _poll(engine2)
    plain.history = [_msg("USER", "old", 1), _msg("USER", "ping", 2)]
    await _poll(engine2)
    assert plain.sent == [("r1", "**hi** _there_", "2")]  # verbatim


@pytest.mark.asyncio
async def test_conversation_content_not_logged_at_info_but_is_at_debug(caplog) -> None:
    client = FakeClient([_msg("USER", "old", 1)])
    engine = BotEngine(client, _echo)
    await _poll(engine)  # baseline = 1

    client.history = [_msg("USER", "old", 1), _msg("USER", "top secret body", 2)]
    with caplog.at_level(logging.INFO, logger="daouoffice.engine"):
        await _poll(engine)
    assert "top secret body" not in caplog.text  # privacy by default

    client.history.append(_msg("USER", "another secret", 3))
    with caplog.at_level(logging.DEBUG, logger="daouoffice.engine"):
        await _poll(engine)
    assert "another secret" in caplog.text  # visible only when opted into DEBUG


@pytest.mark.asyncio
async def test_read_ack_logged_at_debug_not_info(caplog) -> None:
    client = FakeClient([_msg("USER", "hi", 1)])
    engine = BotEngine(client, _echo)

    with caplog.at_level(logging.INFO, logger="daouoffice.engine"):
        await _poll(engine)  # first contact → marks read
    assert "Read ack" not in caplog.text  # per-cycle chatter, not INFO
    assert client.read == ["1"]  # the ack did happen

    caplog.clear()
    with caplog.at_level(logging.DEBUG, logger="daouoffice.engine"):
        client.history = [_msg("USER", "hi", 1), _msg("USER", "more", 2)]
        await _poll(engine)
    assert "Read ack [r1] up to 2" in caplog.text


def test_daou_log_level_env_scopes_package_logger_and_validates(monkeypatch) -> None:
    pkg = logging.getLogger("daouoffice")
    prev = pkg.level
    try:
        monkeypatch.setenv("DAOU_LOG_LEVEL", "warning")  # case-insensitive
        _apply_log_level()
        assert pkg.level == logging.WARNING

        pkg.setLevel(prev)
        monkeypatch.setenv("DAOU_LOG_LEVEL", "LOUD")  # invalid → ignored
        _apply_log_level()
        assert pkg.level == prev

        monkeypatch.delenv("DAOU_LOG_LEVEL", raising=False)  # unset → no-op
        _apply_log_level()
        assert pkg.level == prev
    finally:
        pkg.setLevel(prev)



class _TwoRoomClient:
    """Two rooms; r1's handler blocks on an event, r2 is fast."""

    def __init__(self) -> None:
        self.user_id = "BOT"
        self.sent: list[tuple[str, str, str | None]] = []
        self.read: list[str] = []

    def get_rooms(self):
        return [
            ChatRoomItem(roomId="r1", roomType="GROUP", unreadMessageCount=1),
            ChatRoomItem(roomId="r2", roomType="GROUP", unreadMessageCount=1),
        ]

    def get_chat_history(self, room_id: str, *, offset: int = 20):
        return [
            ChatHistoryItem(
                chatRoomId=room_id,
                chatMessageId=1,
                sender={"platformUserId": "U", "platformUserName": "T"},
                contents={"message": {"text": room_id}},
            )
        ]

    def send_message(self, room_id: str, content: str, *, reply_to=None) -> str:
        self.sent.append((room_id, content, reply_to))
        return "cmid"

    def mark_read(self, message_id, room_id) -> None:
        self.read.append(str(message_id))


async def _until(pred, *, interval: float = 0.01):
    while not pred():
        await asyncio.sleep(interval)


@pytest.mark.asyncio
async def test_slow_room_does_not_block_other_rooms_or_poll() -> None:
    """A slow room must not stall the poll call or other rooms (cross-room
    parallel), and a room is never handled concurrently with itself."""
    client = _TwoRoomClient()
    gate = asyncio.Event()
    started: list[str] = []

    async def handler(m):
        started.append(m.room_id)
        if m.room_id == "r1":
            await gate.wait()  # r1 hangs until released
        return f"re: {m.message_text}"

    # Preset cursors so id=1 is dispatched (not swallowed as first-contact
    # baseline) — the concurrency behaviour is what is under test here.
    cursors = MemoryCursorStore()
    cursors.set("r1", 0)
    cursors.set("r2", 0)
    engine = BotEngine(client, handler, cursors=cursors)

    # Schedules both rooms; must return at once even though r1 hangs.
    await asyncio.wait_for(engine._poll_once(), timeout=1.0)

    # r2 (fast) completes while r1 is still blocked → not head-of-line blocked.
    await asyncio.wait_for(
        _until(lambda: ("r2", "re: r2", "1") in client.sent), timeout=1.0
    )
    assert not any(s[0] == "r1" for s in client.sent)  # r1 still in flight

    # A re-poll while r1's handler is in flight must NOT start it again.
    await engine._poll_once()
    assert started.count("r1") == 1

    gate.set()
    await engine._join()
    assert ("r1", "re: r1", "1") in client.sent
