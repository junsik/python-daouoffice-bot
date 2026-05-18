"""Tests for the polling engine: baseline, dedup, dispatch, own-message skip."""

from __future__ import annotations

import pytest

from daouoffice.client import ChatHistoryItem, ChatRoomItem
from daouoffice.engine import AT_LEAST_ONCE, BotEngine


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


def test_default_delivery_is_at_least_once() -> None:
    assert BotEngine(FakeClient([]), _echo)._delivery == AT_LEAST_ONCE


def test_invalid_delivery_rejected() -> None:
    with pytest.raises(ValueError, match="delivery"):
        BotEngine(FakeClient([]), _echo, delivery="bogus")


class _Flaky:
    """Fails the first `fail_times` calls for a given text, then succeeds."""

    def __init__(self, fail_times: int) -> None:
        self.fail_times = fail_times
        self.calls: list[str] = []

    async def __call__(self, m):
        self.calls.append(m.message_text)
        if self.calls.count(m.message_text) <= self.fail_times:
            raise RuntimeError("transient")
        return f"ok: {m.message_text}"


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
async def test_at_most_once_does_not_retry() -> None:
    client = FakeClient([_msg("USER", "old", 1)])
    handler = _Flaky(fail_times=99)  # always fails
    engine = BotEngine(client, handler, delivery="at_most_once")
    await engine._poll_once()  # baseline = 1

    client.history = [_msg("USER", "old", 1), _msg("USER", "A", 2)]
    await engine._poll_once()  # A dispatched, fails, but advanced anyway
    await engine._poll_once()  # nothing new → not retried

    assert handler.calls == ["A"]  # called exactly once, message lost
    assert "2" in client.read  # room cleared (fire-and-forget)
