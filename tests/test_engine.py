"""Tests for the polling engine: baseline, dedup, dispatch, own-message skip."""

from __future__ import annotations

import pytest

from daouoffice.client import ChatHistoryItem, ChatRoomItem
from daouoffice.engine import BotEngine


class FakeClient:
    """Minimal stand-in for BotClient; history is mutable between polls."""

    def __init__(self, history: list[ChatHistoryItem]) -> None:
        self.history = history
        self.user_id = "BOT"
        self.sent: list[tuple[str, str]] = []
        self.read: list[str] = []

    def get_rooms(self) -> list[ChatRoomItem]:
        return [ChatRoomItem(roomId="r1", roomType="GROUP", unreadMessageCount=1)]

    def get_chat_history(self, room_id: str, *, offset: int = 20):
        return self.history

    def send_message(self, room_id: str, content: str) -> str:
        self.sent.append((room_id, content))
        return "cmid"

    def mark_read(self, message_id) -> None:
        self.read.append(str(message_id))


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

    await engine._poll_once()  # first contact → baseline only

    assert client.sent == []  # backlog not replayed
    assert client.read == ["2"]  # room marked read up to latest


@pytest.mark.asyncio
async def test_new_message_dispatched_once() -> None:
    client = FakeClient([_msg("USER", "old", 1)])
    engine = BotEngine(client, _echo)
    await engine._poll_once()  # baseline = 1

    client.history = [_msg("USER", "old", 1), _msg("USER", "hello", 2)]
    await engine._poll_once()  # only id 2 is new
    assert client.sent == [("r1", "re: hello")]

    await engine._poll_once()  # same history → no repeat
    assert client.sent == [("r1", "re: hello")]


@pytest.mark.asyncio
async def test_skips_own_messages_but_advances_baseline() -> None:
    client = FakeClient([_msg("USER", "old", 1)])
    engine = BotEngine(client, _echo)
    await engine._poll_once()

    client.history = [_msg("BOT", "my own reply", 2)]
    await engine._poll_once()
    assert client.sent == []  # own message not handled

    client.history = [_msg("USER", "next", 3)]
    await engine._poll_once()
    assert client.sent == [("r1", "re: next")]  # baseline moved past 2


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
    await engine._poll_once()  # baseline = 1

    client.history = [_msg("USER", "old", 1), _msg("USER", "A", 2), _msg("USER", "B", 3)]

    await engine._poll_once()  # A fails once → blocked, B not reached
    assert client.sent == []

    await engine._poll_once()  # A succeeds, then B succeeds (order preserved)
    assert client.sent == [("r1", "ok: A"), ("r1", "ok: B")]


@pytest.mark.asyncio
async def test_at_least_once_poison_message_is_skipped() -> None:
    client = FakeClient([_msg("USER", "old", 1)])

    async def always_fail_A(m):
        if m.message_text == "A":
            raise RuntimeError("poison")
        return f"ok: {m.message_text}"

    engine = BotEngine(client, always_fail_A, max_attempts=2)
    await engine._poll_once()  # baseline = 1
    client.history = [_msg("USER", "old", 1), _msg("USER", "A", 2), _msg("USER", "B", 3)]

    await engine._poll_once()  # A attempt 1 → blocked
    await engine._poll_once()  # A attempt 2 → poison, skip; B delivered
    assert client.sent == [("r1", "ok: B")]


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
    await engine._poll_once()
    assert client.sent == []  # baseline only

    # Restore the badge-cleared room view and deliver a burst (2,3,4,5).
    del client.get_rooms
    client.history = [_msg("USER", str(n), n) for n in (1, 2, 3, 4, 5)]
    await engine._poll_once()

    # All four are dispatched in order despite unreadMessageCount == 0.
    assert client.sent == [
        ("r1", "re: 2"),
        ("r1", "re: 3"),
        ("r1", "re: 4"),
        ("r1", "re: 5"),
    ]

    await engine._poll_once()  # caught up → nothing repeats
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
    await engine._poll_once()  # baseline = 1

    client.history = [_msg("USER", "old", 1), _msg("USER", "A", 2)]
    await engine._poll_once()
    await engine._poll_once()  # nothing new → not retried

    assert calls == ["A"]  # processed exactly once
    assert "2" in client.read  # room cleared
