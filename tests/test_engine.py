"""Tests for the polling engine: message normalization and dispatch."""

from __future__ import annotations

import pytest

from daouoffice.client import ChatHistoryItem, ChatRoomItem
from daouoffice.engine import BotEngine


class FakeClient:
    """Minimal stand-in for BotClient used by the engine."""

    def __init__(self, history: list[ChatHistoryItem]) -> None:
        self._history = history
        self.user_id = "BOT"
        self.sent: list[tuple[str, str]] = []
        self.read: list[str] = []

    def get_rooms(self) -> list[ChatRoomItem]:
        return [ChatRoomItem(roomId="r1", roomType="GROUP", unreadMessageCount=1)]

    def get_chat_history(self, room_id: str, *, offset: int = 20) -> list[ChatHistoryItem]:
        return self._history

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


@pytest.mark.asyncio
async def test_dispatch_replies_and_marks_read() -> None:
    client = FakeClient([_msg("USER", "hello", 1)])
    seen = []

    async def on_message(m):
        seen.append(m.message_text)
        return "pong"

    engine = BotEngine(client, on_message)
    await engine._poll_once()

    assert seen == ["hello"]
    assert client.sent == [("r1", "pong")]
    assert client.read == ["1"]


@pytest.mark.asyncio
async def test_skips_own_messages() -> None:
    client = FakeClient([_msg("BOT", "from myself", 2)])
    called = False

    async def on_message(m):
        nonlocal called
        called = True
        return "x"

    engine = BotEngine(client, on_message)
    await engine._poll_once()

    assert called is False
    assert client.sent == []


@pytest.mark.asyncio
async def test_none_reply_still_marks_read() -> None:
    client = FakeClient([_msg("USER", "noop", 3)])

    async def on_message(m):
        return None

    engine = BotEngine(client, on_message)
    await engine._poll_once()

    assert client.sent == []
    assert client.read == ["3"]
