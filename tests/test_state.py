"""Tests for cursor persistence and restart-resume behavior."""

from __future__ import annotations

import pytest

from daouoffice.client import ChatHistoryItem, ChatRoomItem
from daouoffice.engine import BotEngine
from daouoffice.state import FileCursorStore, MemoryCursorStore


def test_memory_store_roundtrip() -> None:
    s = MemoryCursorStore()
    assert s.get("r1") is None
    s.set("r1", 7)
    assert s.get("r1") == 7


def test_file_store_persists_across_instances(tmp_path) -> None:
    s1 = FileCursorStore(base_dir=tmp_path)
    s1.set("r1", 42)
    # A fresh instance (simulating a process restart) reloads from disk.
    s2 = FileCursorStore(base_dir=tmp_path)
    assert s2.get("r1") == 42


def test_file_store_tolerates_garbage(tmp_path) -> None:
    (tmp_path / ".daoubot").mkdir()
    (tmp_path / ".daoubot" / "cursors.json").write_text("not json", encoding="utf-8")
    assert FileCursorStore(base_dir=tmp_path).get("r1") is None


class _FakeClient:
    def __init__(self, history):
        self.history = history
        self.user_id = "BOT"
        self.sent: list[tuple[str, str]] = []

    def get_rooms(self):
        return [ChatRoomItem(roomId="r1", roomType="GROUP", unreadMessageCount=1)]

    def get_chat_history(self, room_id, *, offset=20):
        return self.history

    def send_message(self, room_id, content):
        self.sent.append((room_id, content))
        return "cmid"

    def mark_read(self, message_id):
        pass


def _msg(mid: int) -> ChatHistoryItem:
    return ChatHistoryItem(
        chatRoomId="r1",
        chatMessageId=mid,
        sender={"platformUserId": "USER", "platformUserName": "T"},
        contents={"message": {"text": f"m{mid}"}},
    )


async def _echo(m):
    return m.message_text


@pytest.mark.asyncio
async def test_engine_resumes_after_restart(tmp_path) -> None:
    client = _FakeClient([_msg(1), _msg(2)])

    # Run 1: first contact → baseline at 2, nothing dispatched, cursor saved.
    engine1 = BotEngine(client, _echo, cursors=FileCursorStore(base_dir=tmp_path))
    await engine1._poll_once()
    assert client.sent == []

    # "Restart": brand-new engine + store reading the same file.
    client.history = [_msg(2), _msg(3)]  # id 3 arrived during downtime
    engine2 = BotEngine(client, _echo, cursors=FileCursorStore(base_dir=tmp_path))
    await engine2._poll_once()
    # Resumes from cursor 2 → handles only 3, does NOT replay 1/2 as backlog.
    assert client.sent == [("r1", "m3")]
