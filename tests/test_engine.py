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
async def test_handler_error_does_not_block_mark_read() -> None:
    client = FakeClient([_msg("USER", "old", 1)])
    engine = BotEngine(client, _echo)
    await engine._poll_once()

    async def boom(_m):
        raise RuntimeError("handler fail")

    engine._on_message = boom
    client.history = [_msg("USER", "trigger", 2)]
    await engine._poll_once()
    assert "2" in client.read  # still marked read
